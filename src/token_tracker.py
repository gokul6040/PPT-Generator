"""Append one Excel row per LLM call (input/output tokens from API usage)."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import TOKEN_USAGE_XLSX
from src.session_context import get_bound_session

_EXCEL_HEADERS = ("Date", "Time", "Session ID", "Input tokens", "Output tokens")
_SESSION_ID_KEY = "token_session_id"
_fallback_state: dict[str, Any] = {}


def _session_state() -> dict[str, Any]:
    bound = get_bound_session()
    if bound is not None:
        return bound
    return _fallback_state


def ensure_session_initialized() -> None:
    """Assign a session id so Excel rows from one visit can be grouped."""
    state = _session_state()
    if not state.get(_SESSION_ID_KEY):
        state[_SESSION_ID_KEY] = uuid.uuid4().hex[:8]


def reset_session_id() -> None:
    """New session id after Clear chat."""
    _session_state()[_SESSION_ID_KEY] = uuid.uuid4().hex[:8]


def _append_excel_row(prompt_tokens: int, completion_tokens: int) -> None:
    input_tokens = max(0, int(prompt_tokens or 0))
    output_tokens = max(0, int(completion_tokens or 0))
    if input_tokens == 0 and output_tokens == 0:
        return

    ensure_session_initialized()
    session_id = str(_session_state().get(_SESSION_ID_KEY, ""))

    path = Path(TOKEN_USAGE_XLSX)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    row = (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        session_id,
        input_tokens,
        output_tokens,
    )

    if path.exists():
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        worksheet = workbook.active
        existing = (
            [worksheet.cell(1, col).value for col in range(1, worksheet.max_column + 1)]
            if worksheet.max_row >= 1
            else []
        )
        if existing != list(_EXCEL_HEADERS):
            worksheet.delete_rows(1, worksheet.max_row)
            worksheet.append(list(_EXCEL_HEADERS))
    else:
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Token usage"
        worksheet.append(list(_EXCEL_HEADERS))

    worksheet.append(list(row))
    workbook.save(path)


def record_usage(prompt_tokens: int, completion_tokens: int) -> None:
    """Log one LLM call to Excel immediately."""
    _append_excel_row(prompt_tokens, completion_tokens)
