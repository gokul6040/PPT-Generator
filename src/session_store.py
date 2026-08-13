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
