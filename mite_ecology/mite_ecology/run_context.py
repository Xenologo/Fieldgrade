from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, Optional


_run_id_var: ContextVar[Optional[str]] = ContextVar("mite_run_id", default=None)
_trace_id_var: ContextVar[Optional[str]] = ContextVar("mite_trace_id", default=None)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    trace_id: str

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


def _env_run_id() -> Optional[str]:
    return (os.environ.get("FG_RUN_ID") or os.environ.get("FIELDGRADE_RUN_ID") or "").strip() or None


def _env_trace_id() -> Optional[str]:
    return (os.environ.get("FG_TRACE_ID") or os.environ.get("FIELDGRADE_TRACE_ID") or "").strip() or None


def _new_id() -> str:
    return uuid.uuid4().hex


def get_run_id(*, create: bool = True) -> str:
    rid = _run_id_var.get() or _env_run_id()
    if rid:
        return rid
    if not create:
        raise RuntimeError("run_id is not set")
    rid = _new_id()
    _run_id_var.set(rid)
    return rid


def get_trace_id(*, create: bool = True) -> str:
    tid = _trace_id_var.get() or _env_trace_id()
    if tid:
        return tid
    if not create:
        raise RuntimeError("trace_id is not set")
    tid = _new_id()
    _trace_id_var.set(tid)
    return tid


def current(*, create: bool = True) -> RunContext:
    return RunContext(run_id=get_run_id(create=create), trace_id=get_trace_id(create=create))


@contextmanager
def run_context(*, run_id: Optional[str] = None, trace_id: Optional[str] = None) -> Iterator[RunContext]:
    """Temporarily set run/trace IDs for the current context.

    This is primarily for in-process pipelines and tests.
    """
    rid = (run_id or "").strip() or None
    tid = (trace_id or "").strip() or None

    tok_r = _run_id_var.set(rid)
    tok_t = _trace_id_var.set(tid)
    try:
        yield current(create=True)
    finally:
        _run_id_var.reset(tok_r)
        _trace_id_var.reset(tok_t)
