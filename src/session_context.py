"""Thread-local session binding for token tracking outside Streamlit."""
from __future__ import annotations

from typing import Any, Callable

_session_getter: Callable[[], dict[str, Any]] | None = None


def bind_session_getter(getter: Callable[[], dict[str, Any]] | None) -> None:
    global _session_getter
    _session_getter = getter


def get_bound_session() -> dict[str, Any] | None:
    if _session_getter is None:
        return None
    return _session_getter()
