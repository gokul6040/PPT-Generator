"""FastAPI backend for TurnB Case Study PPT Agent — powers the React chat UI."""
from __future__ import annotations

import traceback
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.chat_service import (
    clear_session,
    get_download,
    handle_message,
    handle_upload,
    session_to_api,
)
from src.session_store import create_session, get_session

app = FastAPI(title="TurnB PPT Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class MessageRequest(BaseModel):
    session_id: str
    message: str


class SessionRequest(BaseModel):
    session_id: str


def _require_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.bind()
    return session


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat/session")
def create_chat_session() -> dict[str, Any]:
    session = create_session()
    session.bind()
    return session_to_api(session)


@app.get("/chat/session/{session_id}")
def get_chat_session(session_id: str) -> dict[str, Any]:
    session = _require_session(session_id)
    return session_to_api(session)


@app.post("/chat/message")
def post_message(body: MessageRequest) -> dict[str, Any]:
    session = _require_session(body.session_id)
    try:
        handle_message(session, body.message)
        return session_to_api(session)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat/upload")
async def post_upload(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    session = _require_session(session_id)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        handle_upload(session, file.filename or "upload", raw)
        return session_to_api(session)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat/clear")
def post_clear(body: SessionRequest) -> dict[str, Any]:
    session = _require_session(body.session_id)
    clear_session(session)
    return session_to_api(session)


@app.get("/chat/download")
def download_ppt(session_id: str, blob_name: str) -> Response:
    session = _require_session(session_id)
    try:
        data, fname = get_download(session, blob_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return Response(
        content=data,
        media_type=PPTX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
