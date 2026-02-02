"""Tests for the Agent Gateway (Memite registry, loader, and invocation API)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from fieldgrade_ui.agent_gateway import (
    create_gateway,
    EchoMemite,
    GatewayAPI,
    GatewayConfig,
    Memite,
    MemiteEntry,
    MemiteLoader,
    MemiteRegistry,
    MemiteResult,
    NoopMemite,
)


# ---------------------------------------------------------------------------
# MemiteRegistry tests
# ---------------------------------------------------------------------------

def test_registry_register_from_dict_valid():
    registry = MemiteRegistry()
    entry = registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "test::example::v1",
            "kind": "tool",
            "io": {"inputs": [], "outputs": []},
            "constraints": {"determinism": "strict"},
        }
    )
    assert entry.memite_id == "test::example::v1"
    assert entry.is_valid
    assert entry.kind == "tool"
    assert entry.determinism == "strict"


def test_registry_register_from_dict_invalid():
    registry = MemiteRegistry()
    entry = registry.register_from_dict(
        studspec={"studspec": "1.0"}  # missing required fields
    )
    assert not entry.is_valid
    assert len(entry.validation_issues) > 0


def test_registry_get_and_list():
    registry = MemiteRegistry()
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "a::b::v1",
            "kind": "tool",
            "io": {"inputs": [], "outputs": []},
            "constraints": {"determinism": "strict"},
        }
    )
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "c::d::v1",
            "kind": "backend",
            "io": {"inputs": [], "outputs": []},
            "constraints": {"determinism": "bounded"},
        }
    )
    
    assert registry.get("a::b::v1") is not None
    assert registry.get("nonexistent") is None
    assert len(registry.list_all()) == 2
    assert len(registry.list_by_kind("tool")) == 1
    assert len(registry.list_by_kind("backend")) == 1


def test_registry_list_valid_filters_invalid():
    registry = MemiteRegistry()
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "valid::one::v1",
            "kind": "tool",
            "io": {"inputs": [], "outputs": []},
            "constraints": {"determinism": "strict"},
        }
    )
    registry.register_from_dict(studspec={"studspec": "1.0"})  # invalid
    
    assert len(registry.list_all()) == 2
    assert len(registry.list_valid()) == 1


# ---------------------------------------------------------------------------
# MemiteLoader tests
# ---------------------------------------------------------------------------

def test_loader_loads_builtin_memites():
    registry, loader, _ = create_gateway()
    
    echo = loader.load("builtin::echo::v1")
    assert echo is not None
    assert isinstance(echo, EchoMemite)
    
    noop = loader.load("builtin::noop::v1")
    assert noop is not None
    assert isinstance(noop, NoopMemite)


def test_loader_returns_none_for_unknown():
    registry = MemiteRegistry()
    loader = MemiteLoader(registry)
    assert loader.load("nonexistent::memite::v1") is None


def test_loader_caches_instances():
    registry, loader, _ = create_gateway()
    
    echo1 = loader.load("builtin::echo::v1")
    echo2 = loader.load("builtin::echo::v1")
    assert echo1 is echo2  # same instance


# ---------------------------------------------------------------------------
# GatewayAPI tests
# ---------------------------------------------------------------------------

def test_gateway_invoke_echo():
    _, _, api = create_gateway()
    
    result = api.invoke("builtin::echo::v1", {"data": "hello"})
    assert result.ok
    assert result.outputs["echo"] == {"data": "hello"}
    assert result.duration_ms >= 0


def test_gateway_invoke_noop():
    _, _, api = create_gateway()
    
    result = api.invoke("builtin::noop::v1", {})
    assert result.ok
    assert result.outputs == {}


def test_gateway_invoke_unknown_memite():
    _, _, api = create_gateway()
    
    result = api.invoke("nonexistent::memite::v1", {})
    assert not result.ok
    assert "memite_not_found" in (result.error or "")


def test_gateway_kill_switch():
    _, _, api = create_gateway()
    
    assert not api.is_killed()
    api.kill()
    assert api.is_killed()
    
    result = api.invoke("builtin::echo::v1", {"data": "test"})
    assert not result.ok
    assert result.error == "gateway_killed"
    
    api.reset_kill_switch()
    assert not api.is_killed()
    
    result = api.invoke("builtin::echo::v1", {"data": "test"})
    assert result.ok


def test_gateway_records_invocations():
    _, _, api = create_gateway()
    
    api.invoke("builtin::echo::v1", {"x": 1})
    api.invoke("builtin::noop::v1", {})
    
    invocations = api.list_invocations()
    assert len(invocations) == 2
    assert invocations[0].memite_id == "builtin::echo::v1"
    assert invocations[1].memite_id == "builtin::noop::v1"


def test_gateway_validates_missing_inputs():
    registry = MemiteRegistry()
    registry.register_from_dict(
        studspec={
            "studspec": "1.0",
            "memite_id": "test::required_input::v1",
            "kind": "tool",
            "io": {
                "inputs": [{"name": "required_field", "schema": "any"}],
                "outputs": [],
            },
            "constraints": {"determinism": "strict"},
        },
        loader_class="fieldgrade_ui.agent_gateway.NoopMemite",
    )
    loader = MemiteLoader(registry)
    api = GatewayAPI(registry, loader)
    
    result = api.invoke("test::required_input::v1", {})  # missing required_field
    assert result.ok  # still executes, but with warning
    assert any("missing_inputs" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Built-in Memite tests
# ---------------------------------------------------------------------------

def test_echo_memite():
    echo = EchoMemite()
    assert echo.memite_id == "builtin::echo::v1"
    
    result = echo.invoke({"a": 1, "b": 2}, context={"trace_id": "t1"})
    assert result.ok
    assert result.outputs["echo"] == {"a": 1, "b": 2}
    assert result.outputs["context"] == {"trace_id": "t1"}


def test_noop_memite():
    noop = NoopMemite()
    assert noop.memite_id == "builtin::noop::v1"
    
    result = noop.invoke({"ignored": True})
    assert result.ok
    assert result.outputs == {}


# ---------------------------------------------------------------------------
# Integration test: full create_gateway flow
# ---------------------------------------------------------------------------

def test_create_gateway_registers_builtins():
    registry, loader, api = create_gateway()
    
    # Check builtins are registered
    assert registry.get("builtin::echo::v1") is not None
    assert registry.get("builtin::noop::v1") is not None
    
    # Check they're loadable and invocable
    result = api.invoke("builtin::echo::v1", {"test": True})
    assert result.ok
