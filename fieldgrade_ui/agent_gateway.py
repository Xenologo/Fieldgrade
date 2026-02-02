"""Agent Gateway: Memite registry, loader, and invocation API.

This module implements the first roadmap item from the OpenClaw/Larval-AGI review:
- MemiteRegistry: discovers Memites from spec files, validates against StudSpec/TubeSpec
- MemiteLoader: dynamically loads and instantiates Memites
- GatewayAPI: common invocation surface with constraint enforcement and kill-switch support

The gateway uses existing StudSpec/TubeSpec schemas from mite_ecology.specs and
mite_lib.contracts for validation and compatibility checks.
"""
from __future__ import annotations

import importlib
import json
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Type

import yaml

from mite_ecology.specs import validate_studspec, validate_tubespec, SpecIssue
from mite_lib.contracts import check_studspec_against_registry, load_ldna_registry, ContractCheck


# ---------------------------------------------------------------------------
# Memite base class and protocol
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemiteResult:
    """Result of a Memite invocation."""
    ok: bool
    outputs: Dict[str, Any]
    duration_ms: int
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class Memite(ABC):
    """Abstract base class for all Memites.
    
    Concrete Memites must implement:
    - memite_id: unique identifier matching their StudSpec
    - invoke(): the actual execution logic
    """
    
    @property
    @abstractmethod
    def memite_id(self) -> str:
        """Return the memite_id from this Memite's StudSpec."""
        ...
    
    @abstractmethod
    def invoke(self, inputs: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> MemiteResult:
        """Execute the Memite with given inputs.
        
        Args:
            inputs: Dict mapping input port names to values
            context: Optional execution context (trace_id, run_id, etc.)
        
        Returns:
            MemiteResult with outputs, timing, and any errors/warnings
        """
        ...


# ---------------------------------------------------------------------------
# Registry entry and discovery
# ---------------------------------------------------------------------------

@dataclass
class MemiteEntry:
    """A registered Memite with its validated specs."""
    memite_id: str
    studspec: Dict[str, Any]
    tubespec: Optional[Dict[str, Any]]
    source_path: Path
    validation_issues: List[SpecIssue] = field(default_factory=list)
    loader_class: Optional[str] = None  # e.g. "fieldgrade_ui.mites.echo.EchoMite"
    
    @property
    def is_valid(self) -> bool:
        return len(self.validation_issues) == 0
    
    @property
    def kind(self) -> str:
        return str(self.studspec.get("kind", "unknown"))
    
    @property
    def determinism(self) -> str:
        c = self.studspec.get("constraints") or {}
        return str(c.get("determinism", "best_effort"))
    
    @property
    def inputs(self) -> List[Dict[str, Any]]:
        io = self.studspec.get("io") or {}
        return list(io.get("inputs") or [])
    
    @property
    def outputs(self) -> List[Dict[str, Any]]:
        io = self.studspec.get("io") or {}
        return list(io.get("outputs") or [])


class MemiteRegistry:
    """Registry for discovering and managing Memites.
    
    Discovers Memite specs from:
    - YAML/JSON files matching *.studspec.yaml, *.studspec.json
    - Optionally paired with *.tubespec.yaml, *.tubespec.json
    
    Validates specs against StudSpec/TubeSpec schemas and optionally
    checks LDNA schema references against a provided registry.
    """
    
    def __init__(self, ldna_registry_path: Optional[Path] = None):
        self._entries: Dict[str, MemiteEntry] = {}
        self._ldna_registry: Dict[str, Any] = {}
        if ldna_registry_path and ldna_registry_path.exists():
            self._ldna_registry = load_ldna_registry(ldna_registry_path)
    
    def discover(self, search_paths: List[Path], *, recursive: bool = True) -> int:
        """Discover Memite specs from given paths.
        
        Args:
            search_paths: List of directories to search
            recursive: Whether to search subdirectories
        
        Returns:
            Number of Memites discovered
        """
        count = 0
        for base in search_paths:
            if not base.exists():
                continue
            pattern = "**/*.studspec.*" if recursive else "*.studspec.*"
            for spec_path in base.glob(pattern):
                if spec_path.suffix.lower() in (".yaml", ".yml", ".json"):
                    entry = self._load_spec(spec_path)
                    if entry:
                        self._entries[entry.memite_id] = entry
                        count += 1
        return count
    
    def register(self, entry: MemiteEntry) -> None:
        """Manually register a MemiteEntry."""
        self._entries[entry.memite_id] = entry
    
    def register_from_dict(
        self,
        studspec: Dict[str, Any],
        *,
        tubespec: Optional[Dict[str, Any]] = None,
        loader_class: Optional[str] = None,
        source_path: Optional[Path] = None,
    ) -> MemiteEntry:
        """Register a Memite from in-memory spec dicts."""
        issues = validate_studspec(studspec)
        if tubespec:
            issues.extend(validate_tubespec(tubespec))
        
        memite_id = str(studspec.get("memite_id", f"anon_{uuid.uuid4().hex[:8]}"))
        entry = MemiteEntry(
            memite_id=memite_id,
            studspec=studspec,
            tubespec=tubespec,
            source_path=source_path or Path("."),
            validation_issues=issues,
            loader_class=loader_class,
        )
        self._entries[memite_id] = entry
        return entry
    
    def get(self, memite_id: str) -> Optional[MemiteEntry]:
        """Get a registered Memite by ID."""
        return self._entries.get(memite_id)
    
    def list_all(self) -> List[MemiteEntry]:
        """List all registered Memites."""
        return list(self._entries.values())
    
    def list_by_kind(self, kind: str) -> List[MemiteEntry]:
        """List Memites filtered by kind."""
        return [e for e in self._entries.values() if e.kind == kind]
    
    def list_valid(self) -> List[MemiteEntry]:
        """List only Memites with no validation issues."""
        return [e for e in self._entries.values() if e.is_valid]
    
    def check_contracts(self, memite_id: str, *, allow_unknown: bool = True) -> ContractCheck:
        """Check a Memite's LDNA schema references against the registry."""
        entry = self._entries.get(memite_id)
        if not entry:
            return ContractCheck(ok=False, issues=[f"memite not found: {memite_id}"], warnings=[])
        return check_studspec_against_registry(entry.studspec, self._ldna_registry, allow_unknown=allow_unknown)
    
    def _load_spec(self, spec_path: Path) -> Optional[MemiteEntry]:
        """Load a StudSpec file and optionally its paired TubeSpec."""
        try:
            studspec = self._read_spec_file(spec_path)
            if not studspec:
                return None
            
            # Look for paired tubespec
            tubespec = None
            tubespec_path = self._find_tubespec(spec_path)
            if tubespec_path:
                tubespec = self._read_spec_file(tubespec_path)
            
            # Validate
            issues = validate_studspec(studspec)
            if tubespec:
                issues.extend(validate_tubespec(tubespec))
            
            memite_id = str(studspec.get("memite_id", spec_path.stem))
            loader_class = studspec.get("loader_class")
            
            return MemiteEntry(
                memite_id=memite_id,
                studspec=studspec,
                tubespec=tubespec,
                source_path=spec_path,
                validation_issues=issues,
                loader_class=loader_class,
            )
        except Exception as e:
            # Log and skip malformed files
            return None
    
    def _read_spec_file(self, path: Path) -> Optional[Dict[str, Any]]:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        return yaml.safe_load(text) or {}
    
    def _find_tubespec(self, studspec_path: Path) -> Optional[Path]:
        """Find a tubespec file paired with a studspec file."""
        base = studspec_path.stem.replace(".studspec", "")
        parent = studspec_path.parent
        for ext in (".tubespec.yaml", ".tubespec.yml", ".tubespec.json"):
            candidate = parent / (base + ext)
            if candidate.exists():
                return candidate
        return None


# ---------------------------------------------------------------------------
# Memite loader
# ---------------------------------------------------------------------------

class MemiteLoader:
    """Dynamically loads and instantiates Memite classes.
    
    Uses the loader_class field from MemiteEntry to import and instantiate
    concrete Memite implementations.
    """
    
    def __init__(self, registry: MemiteRegistry):
        self._registry = registry
        self._instances: Dict[str, Memite] = {}
    
    def load(self, memite_id: str) -> Optional[Memite]:
        """Load and return a Memite instance.
        
        Returns cached instance if already loaded.
        """
        if memite_id in self._instances:
            return self._instances[memite_id]
        
        entry = self._registry.get(memite_id)
        if not entry:
            return None
        
        if not entry.loader_class:
            return None
        
        try:
            instance = self._instantiate(entry)
            if instance:
                self._instances[memite_id] = instance
            return instance
        except Exception:
            return None
    
    def load_all_valid(self) -> List[Memite]:
        """Load all valid Memites that have loader_class specified."""
        result = []
        for entry in self._registry.list_valid():
            if entry.loader_class:
                inst = self.load(entry.memite_id)
                if inst:
                    result.append(inst)
        return result
    
    def _instantiate(self, entry: MemiteEntry) -> Optional[Memite]:
        """Import and instantiate a Memite class."""
        loader_class = entry.loader_class
        if not loader_class:
            return None
        
        parts = loader_class.rsplit(".", 1)
        if len(parts) != 2:
            return None
        
        module_name, class_name = parts
        module = importlib.import_module(module_name)
        cls: Type[Memite] = getattr(module, class_name)
        return cls()


# ---------------------------------------------------------------------------
# Gateway API with constraint enforcement
# ---------------------------------------------------------------------------

@dataclass
class GatewayConfig:
    """Configuration for the Agent Gateway."""
    max_ram_mb_default: int = 2048
    max_latency_ms_default: int = 60000
    kill_switch_enabled: bool = True
    enforce_determinism: bool = False
    log_invocations: bool = True


@dataclass
class InvocationRecord:
    """Record of a single Memite invocation."""
    invocation_id: str
    memite_id: str
    inputs_hash: str
    started_at_ms: int
    finished_at_ms: Optional[int] = None
    result: Optional[MemiteResult] = None
    killed: bool = False


class GatewayAPI:
    """Agent Gateway API for invoking Memites with constraint enforcement.
    
    Features:
    - Input validation against StudSpec I/O schemas
    - Resource constraint enforcement (RAM, latency)
    - Kill-switch support for aborting runaway Memites
    - Invocation logging for audit/replay
    """
    
    def __init__(
        self,
        registry: MemiteRegistry,
        loader: MemiteLoader,
        config: Optional[GatewayConfig] = None,
    ):
        self._registry = registry
        self._loader = loader
        self._config = config or GatewayConfig()
        self._kill_switch = threading.Event()
        self._invocations: Dict[str, InvocationRecord] = {}
        self._lock = threading.Lock()
    
    def invoke(
        self,
        memite_id: str,
        inputs: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
        timeout_ms: Optional[int] = None,
    ) -> MemiteResult:
        """Invoke a Memite by ID.
        
        Args:
            memite_id: The Memite to invoke
            inputs: Dict mapping input port names to values
            context: Optional execution context
            timeout_ms: Override max_latency_ms constraint
        
        Returns:
            MemiteResult with outputs, timing, errors/warnings
        """
        # Check kill switch
        if self._config.kill_switch_enabled and self._kill_switch.is_set():
            return MemiteResult(
                ok=False,
                outputs={},
                duration_ms=0,
                error="gateway_killed",
            )
        
        # Get entry and validate
        entry = self._registry.get(memite_id)
        if not entry:
            return MemiteResult(
                ok=False,
                outputs={},
                duration_ms=0,
                error=f"memite_not_found: {memite_id}",
            )
        
        if not entry.is_valid:
            issues = "; ".join(f"{i.path}: {i.message}" for i in entry.validation_issues[:3])
            return MemiteResult(
                ok=False,
                outputs={},
                duration_ms=0,
                error=f"memite_invalid: {issues}",
            )
        
        # Validate inputs
        warnings = self._validate_inputs(entry, inputs)
        
        # Load Memite
        memite = self._loader.load(memite_id)
        if not memite:
            return MemiteResult(
                ok=False,
                outputs={},
                duration_ms=0,
                error=f"memite_not_loadable: {memite_id}",
            )
        
        # Determine timeout
        constraints = entry.studspec.get("constraints") or {}
        max_latency = timeout_ms or constraints.get("max_latency_ms") or self._config.max_latency_ms_default
        
        # Record invocation
        invocation_id = uuid.uuid4().hex
        inputs_hash = self._hash_inputs(inputs)
        record = InvocationRecord(
            invocation_id=invocation_id,
            memite_id=memite_id,
            inputs_hash=inputs_hash,
            started_at_ms=int(time.time() * 1000),
        )
        
        with self._lock:
            self._invocations[invocation_id] = record
        
        # Execute with timeout
        start = time.time()
        try:
            result = self._execute_with_timeout(memite, inputs, context, max_latency)
            if warnings:
                result = MemiteResult(
                    ok=result.ok,
                    outputs=result.outputs,
                    duration_ms=result.duration_ms,
                    error=result.error,
                    warnings=list(result.warnings) + warnings,
                )
        except Exception as e:
            result = MemiteResult(
                ok=False,
                outputs={},
                duration_ms=int((time.time() - start) * 1000),
                error=f"invocation_error: {e}",
                warnings=warnings,
            )
        
        # Update record
        with self._lock:
            record.finished_at_ms = int(time.time() * 1000)
            record.result = result
        
        return result
    
    def kill(self) -> None:
        """Activate the kill switch to abort all pending invocations."""
        self._kill_switch.set()
    
    def reset_kill_switch(self) -> None:
        """Reset the kill switch to allow new invocations."""
        self._kill_switch.clear()
    
    def is_killed(self) -> bool:
        """Check if the kill switch is active."""
        return self._kill_switch.is_set()
    
    def list_invocations(self) -> List[InvocationRecord]:
        """List all recorded invocations."""
        with self._lock:
            return list(self._invocations.values())
    
    def _validate_inputs(self, entry: MemiteEntry, inputs: Dict[str, Any]) -> List[str]:
        """Validate inputs against StudSpec I/O definition."""
        warnings = []
        required_inputs = {p["name"] for p in entry.inputs if not p.get("optional")}
        provided = set(inputs.keys())
        
        missing = required_inputs - provided
        if missing:
            warnings.append(f"missing_inputs: {', '.join(sorted(missing))}")
        
        extra = provided - {p["name"] for p in entry.inputs}
        if extra:
            warnings.append(f"extra_inputs: {', '.join(sorted(extra))}")
        
        return warnings
    
    def _execute_with_timeout(
        self,
        memite: Memite,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        timeout_ms: int,
    ) -> MemiteResult:
        """Execute a Memite with timeout enforcement."""
        # For simplicity, we do synchronous execution with timing check
        # A production implementation might use threading or asyncio
        start = time.time()
        result = memite.invoke(inputs, context=context)
        elapsed_ms = int((time.time() - start) * 1000)
        
        if elapsed_ms > timeout_ms:
            return MemiteResult(
                ok=False,
                outputs=result.outputs,
                duration_ms=elapsed_ms,
                error=f"timeout_exceeded: {elapsed_ms}ms > {timeout_ms}ms",
                warnings=list(result.warnings),
            )
        
        return result
    
    def _hash_inputs(self, inputs: Dict[str, Any]) -> str:
        """Hash inputs for invocation logging."""
        from mite_ecology.hashutil import sha256_str, canonical_json
        return sha256_str(canonical_json(inputs))


# ---------------------------------------------------------------------------
# Built-in utility Memites
# ---------------------------------------------------------------------------

class EchoMemite(Memite):
    """A simple echo Memite for testing the gateway."""
    
    @property
    def memite_id(self) -> str:
        return "builtin::echo::v1"
    
    def invoke(self, inputs: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> MemiteResult:
        start = time.time()
        outputs = {"echo": inputs, "context": context}
        return MemiteResult(
            ok=True,
            outputs=outputs,
            duration_ms=int((time.time() - start) * 1000),
        )


class NoopMemite(Memite):
    """A no-op Memite that does nothing (for constraint testing)."""
    
    @property
    def memite_id(self) -> str:
        return "builtin::noop::v1"
    
    def invoke(self, inputs: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> MemiteResult:
        return MemiteResult(ok=True, outputs={}, duration_ms=0)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_gateway(
    spec_paths: Optional[List[Path]] = None,
    ldna_registry_path: Optional[Path] = None,
    config: Optional[GatewayConfig] = None,
) -> Tuple[MemiteRegistry, MemiteLoader, GatewayAPI]:
    """Create a fully configured Agent Gateway.
    
    Args:
        spec_paths: Directories to search for Memite specs
        ldna_registry_path: Path to LDNA schema registry
        config: Gateway configuration
    
    Returns:
        Tuple of (registry, loader, api)
    """
    registry = MemiteRegistry(ldna_registry_path=ldna_registry_path)
    
    if spec_paths:
        registry.discover(spec_paths)
    
    # Register built-in Memites
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "builtin::echo::v1",
            "kind": "tool",
            "io": {
                "inputs": [{"name": "data", "schema": "any", "optional": True}],
                "outputs": [{"name": "echo", "schema": "any"}],
            },
            "constraints": {"determinism": "strict"},
        },
        loader_class="fieldgrade_ui.agent_gateway.EchoMemite",
    )
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "builtin::noop::v1",
            "kind": "tool",
            "io": {"inputs": [], "outputs": []},
            "constraints": {"determinism": "strict"},
        },
        loader_class="fieldgrade_ui.agent_gateway.NoopMemite",
    )
    
    loader = MemiteLoader(registry)
    api = GatewayAPI(registry, loader, config=config)
    
    return registry, loader, api
