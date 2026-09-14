"""In-memory chat session registry for API mode."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.chat_service import ChatSession

_lock = threading.Lock()
_sessions: dict[str, ChatSession] = {}


def get_session(session_id: str) -> ChatSession | None:
    with _lock:
        return _sessions.get(session_id)


def save_session(session: ChatSession) -> None:
    with _lock:
        _sessions[session.session_id] = session


def create_session() -> ChatSession:
    from src.chat_service import new_session

    session = new_session()
    save_session(session)
    return session


def delete_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


# ── Keyed sessions (Teams bot) ─────────────────────────────────────────────
# Maps a stable external identity (Teams AAD object id) to a session id so a
# user's conversation survives across turns. In-memory only: a container
# restart drops every mapping and users start a fresh session.
_keyed: dict[str, str] = {}


def get_session_by_key(key: str) -> ChatSession:
    """Return the session bound to `key`, creating one if absent or evicted."""
    with _lock:
        session_id = _keyed.get(key)
        if session_id:
            existing = _sessions.get(session_id)
            if existing:
                return existing

    session = create_session()
    with _lock:
        _keyed[key] = session.session_id
    return session


def reset_session_by_key(key: str) -> ChatSession:
    """Drop the session bound to `key` and hand back a fresh one."""
    with _lock:
        session_id = _keyed.pop(key, None)
        if session_id:
            _sessions.pop(session_id, None)
    return get_session_by_key(key)
