"""Microsoft Teams bot adapter.

Fronts the same pipeline as the React chat UI: every Teams turn resolves to a
`ChatSession` and is handed to `chat_service.handle_message` / `handle_upload`,
so nothing in the generation path is duplicated here.

Personal scope only. Files arrive as Teams file-download attachments and go back
out through a file consent card, which drops the deck into the user's OneDrive.

Sessions live in memory (see `session_store`), so a container restart resets
every conversation. Acceptable for the pilot; revisit with a durable store.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import traceback
from typing import Any

import httpx
from botbuilder.core import CardFactory, TurnContext
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ActivityTypes, Attachment
from fastapi import APIRouter, Request, Response

from src.chat_service import (
    can_show_action_buttons,
    get_download,
    handle_message,
    handle_upload,
)
from src.session_store import get_session_by_key, reset_session_by_key

# ── Teams content types ────────────────────────────────────────────────────
CONTENT_TYPE_FILE_DOWNLOAD_INFO = "application/vnd.microsoft.teams.file.download.info"
CONTENT_TYPE_FILE_CONSENT = "application/vnd.microsoft.teams.card.file.consent"
CONTENT_TYPE_FILE_INFO = "application/vnd.microsoft.teams.card.file.info"

# Canonical action text — must match frontend/src/lib/actions.ts and the
# intent routing in src/agent_controller.py.
CHAT_ACTIONS = {
    "REVIEW": "Review content",
    "GENERATE": "Generate",
    "GENERATE_ANYWAY": "Generate anyway",
}

RESET_COMMANDS = {"/clear", "/reset", "/new"}
HELP_COMMANDS = {"/help", "help"}

GREETING = (
    "Hi — I turn rough project content into TurnB case-study decks.\n\n"
    "Send me a document (.docx, .pdf, .txt) or just paste your project details "
    "and I'll review what you have, flag what's missing, and build the slides.\n\n"
    "Type `/clear` to start over, `/help` for commands."
)

HELP_TEXT = (
    "**Commands**\n"
    "- `/clear` — start a fresh session (keeps your uploaded template)\n"
    "- `/help` — show this\n\n"
    "**Tips**\n"
    "- Attach a .pptx with few words and I'll treat it as your slide template\n"
    "- Attach a .docx/.pdf/.txt and I'll read it as case-study content\n"
    "- Say *Generate anyway* to build a deck despite missing sections"
)

MAX_TEAMS_TEXT = 2800  # Teams truncates long messages; split before that.


# ── Configuration ──────────────────────────────────────────────────────────
class _BotConfig:
    """Read by ConfigurationBotFrameworkAuthentication via attribute lookup."""

    APP_ID = os.getenv("MICROSOFT_APP_ID", "").strip()
    APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "").strip()
    APP_TYPE = os.getenv("MICROSOFT_APP_TYPE", "MultiTenant").strip() or "MultiTenant"
    APP_TENANTID = os.getenv("MICROSOFT_APP_TENANT_ID", "").strip()


def is_configured() -> bool:
    """True when bot credentials are present. Local Emulator use needs none."""
    return bool(_BotConfig.APP_ID) or os.getenv("TEAMS_BOT_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )


# ── Rendering helpers ──────────────────────────────────────────────────────
def _split_review_items(items: Any) -> list[str]:
    """Mirror splitReviewItems in frontend/src/components/ChatMessage.tsx."""
    out: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text:
            continue
        if " - " in text:
            out.extend(p.strip() for p in re.split(r"\s+-\s+", text) if p.strip())
        else:
            out.append(text)
    return out


def _render_review(review: dict) -> str:
    lines = ["**I've reviewed your content. Here's what I found:**", ""]

    coverage = review.get("section_coverage") or review.get("section_status") or {}
    status_bits: list[str] = []
    title_status = str(review.get("title_status") or "").strip()
    if title_status:
        status_bits.append(f"Title: {title_status}")
    if coverage:
        for key, label in (
            ("problem_statement", "Problem"),
            ("design_implementation", "Design"),
            ("impact", "Impact"),
        ):
            status_bits.append(f"{label}: {coverage.get(key, 'weak')}")
    if status_bits:
        lines += ["  ·  ".join(status_bits), ""]

    for heading, key in (
        ("Available / Strong", "available_strong"),
        ("Missing / Weak", "missing_weak"),
        ("Questions", "questions_to_user"),
    ):
        items = _split_review_items(review.get(key))
        if not items:
            continue
        lines.append(f"**{heading}**")
        lines += [f"- {item}" for item in items]
        lines.append("")

    note = str(review.get("impact_note") or "").strip()
    if note:
        lines.append(f"**Impact note:** {note}")

    return "\n".join(lines).strip()


def _chunk(text: str, limit: int = MAX_TEAMS_TEXT) -> list[str]:
    """Split on paragraph boundaries so long reviews survive Teams' limit."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _actions_card() -> Attachment:
    return CardFactory.adaptive_card(
        {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "What would you like to do?",
                    "weight": "Bolder",
                    "wrap": True,
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Review Content",
                    "data": {"action": "REVIEW"},
                },
                {
                    "type": "Action.Submit",
                    "title": "Generate PPT",
                    "data": {"action": "GENERATE"},
                },
                {
                    "type": "Action.Submit",
                    "title": "Generate Anyway",
                    "data": {"action": "GENERATE_ANYWAY"},
                },
            ],
        }
    )


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Read a field whether the SDK handed us a typed object or a raw dict."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _user_key(activity: Activity) -> str:
    sender = activity.from_property
    aad_id = getattr(sender, "aad_object_id", None)
    if aad_id:
        return f"aad:{aad_id}"
    return f"{activity.channel_id}:{getattr(sender, 'id', 'unknown')}"


def _file_attachments(activity: Activity) -> list[Attachment]:
    return [
        att
        for att in (activity.attachments or [])
        if att.content_type == CONTENT_TYPE_FILE_DOWNLOAD_INFO
    ]


async def _download_teams_file(attachment: Attachment) -> tuple[str, bytes]:
    """Fetch an inbound Teams attachment via its pre-authenticated URL."""
    content = attachment.content or {}
    url = _attr(content, "downloadUrl", "download_url")
    if not url:
        raise ValueError("Attachment has no downloadUrl")
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.get(url)
        response.raise_for_status()
        return attachment.name or "upload", response.content


async def _upload_to_teams(upload_url: str, data: bytes) -> None:
    """PUT the deck to the OneDrive location Teams handed back on consent."""
    headers = {"Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        response = await client.put(upload_url, content=data, headers=headers)
        response.raise_for_status()


def _consent_card(file_name: str, size: int, blob_name: str) -> Attachment:
    return Attachment(
        content_type=CONTENT_TYPE_FILE_CONSENT,
        name=file_name,
        content={
            "description": "Save this deck to your OneDrive",
            "sizeInBytes": size,
            "acceptContext": {"blob_name": blob_name, "file_name": file_name},
            "declineContext": {"file_name": file_name},
        },
    )


def _file_info_card(upload_info: Any) -> Attachment:
    return Attachment(
        content_type=CONTENT_TYPE_FILE_INFO,
        name=_attr(upload_info, "name", "file_name"),
        content_url=_attr(upload_info, "content_url", "contentUrl"),
        content={
            "uniqueId": _attr(upload_info, "unique_id", "uniqueId"),
            "fileType": _attr(upload_info, "file_type", "fileType"),
        },
    )


# ── Session bridge (runs off the event loop) ───────────────────────────────
def _run_message(session, text: str) -> None:
    session.bind()
    handle_message(session, text)


def _run_upload(session, name: str, raw: bytes) -> None:
    session.bind()
    handle_upload(session, name, raw)


def _load_download(session, blob_name: str, file_name: str | None) -> tuple[bytes, str]:
    session.bind()
    return get_download(session, blob_name, file_name)


# ── Bot ────────────────────────────────────────────────────────────────────
class TurnBTeamsBot(TeamsActivityHandler):
    """Bridges Teams turns onto the existing chat_service pipeline."""

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(GREETING)

    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity
        key = _user_key(activity)
        text = self._resolve_text(turn_context)
        lowered = text.lower()

        if lowered in RESET_COMMANDS:
            reset_session_by_key(key)
            await turn_context.send_activity(
                "Cleared. Send new content whenever you're ready."
            )
            return
        if lowered in HELP_COMMANDS:
            await turn_context.send_activity(HELP_TEXT)
            return

        session = get_session_by_key(key)
        attachments = _file_attachments(activity)

        for attachment in attachments:
            await self._send_typing(turn_context)
            try:
                name, raw = await _download_teams_file(attachment)
            except Exception as exc:
                traceback.print_exc()
                label = attachment.name or "that file"
                await turn_context.send_activity(
                    f"Couldn't read **{label}** — {exc}"
                )
                continue
            start = len(session.messages)
            await asyncio.to_thread(_run_upload, session, name, raw)
            await self._flush(turn_context, session, start)

        if text:
            await self._send_typing(turn_context)
            if self._is_generate(text):
                await turn_context.send_activity(
                    "Working on your deck — this usually takes a minute or two."
                )
            start = len(session.messages)
            await asyncio.to_thread(_run_message, session, text)
            await self._flush(turn_context, session, start)
        elif not attachments:
            await turn_context.send_activity(
                "Send me your project content or attach a document to get started."
            )
            return

        if can_show_action_buttons(session):
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[_actions_card()])
            )

    async def on_teams_file_consent_accept(
        self, turn_context: TurnContext, file_consent_card_response
    ):
        context = _attr(file_consent_card_response, "context", default={}) or {}
        upload_info = _attr(file_consent_card_response, "upload_info", "uploadInfo")
        upload_url = _attr(upload_info, "upload_url", "uploadUrl")
        blob_name = _attr(context, "blob_name")
        file_name = _attr(context, "file_name")

        if not upload_url or not blob_name:
            await turn_context.send_activity(
                "Couldn't complete the upload — the file details were missing."
            )
            return

        session = get_session_by_key(_user_key(turn_context.activity))
        try:
            data, resolved = await asyncio.to_thread(
                _load_download, session, blob_name, file_name
            )
            await _upload_to_teams(upload_url, data)
        except Exception as exc:
            traceback.print_exc()
            await turn_context.send_activity(f"Upload failed — {exc}")
            return

        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                text=f"Saved **{resolved}** to your OneDrive.",
                attachments=[_file_info_card(upload_info)],
            )
        )

    async def on_teams_file_consent_decline(
        self, turn_context: TurnContext, file_consent_card_response
    ):
        await turn_context.send_activity(
            "No problem — the deck is still available in the PPT Agent tab."
        )

    # ── internals ──────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_text(turn_context: TurnContext) -> str:
        activity = turn_context.activity
        value = activity.value if isinstance(activity.value, dict) else None
        if value:
            action = str(value.get("action") or "").upper()
            if action in CHAT_ACTIONS:
                return CHAT_ACTIONS[action]
        try:
            text = TurnContext.remove_recipient_mention(activity) or ""
        except Exception:
            text = activity.text or ""
        return text.strip()

    @staticmethod
    def _is_generate(text: str) -> bool:
        return text.strip().lower().startswith("generate")

    @staticmethod
    async def _send_typing(turn_context: TurnContext) -> None:
        try:
            await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        except Exception:
            pass

    async def _flush(self, turn_context: TurnContext, session, start_index: int) -> None:
        """Relay assistant messages appended since start_index back to Teams."""
        for msg in session.messages[start_index:]:
            if msg.get("role") != "assistant":
                continue

            if msg.get("msg_type") == "review" and msg.get("review"):
                for chunk in _chunk(_render_review(msg["review"])):
                    await turn_context.send_activity(chunk)
                continue

            content = (msg.get("content") or "").strip()
            if content:
                for chunk in _chunk(content):
                    await turn_context.send_activity(chunk)

            blob_name = msg.get("download_blob")
            if blob_name:
                await self._offer_file(
                    turn_context, session, blob_name, msg.get("download_file_name")
                )

    async def _offer_file(
        self, turn_context: TurnContext, session, blob_name: str, file_name: str | None
    ) -> None:
        try:
            data, resolved = await asyncio.to_thread(
                _load_download, session, blob_name, file_name
            )
        except Exception:
            traceback.print_exc()
            await turn_context.send_activity(
                "The deck was generated but I couldn't attach it here. "
                "You can still download it from the PPT Agent tab."
            )
            return

        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[_consent_card(resolved, len(data), blob_name)],
            )
        )


# ── Adapter + FastAPI route ────────────────────────────────────────────────
_BOT = TurnBTeamsBot()
_ADAPTER: CloudAdapter | None = None


async def _on_turn_error(turn_context: TurnContext, error: Exception) -> None:
    print(f"[teams_bot] unhandled error: {error}")
    traceback.print_exc()
    try:
        await turn_context.send_activity(
            "Something went wrong on my side. Try again, or send /clear to start fresh."
        )
    except Exception:
        pass


def _adapter() -> CloudAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication(_BotConfig()))
        adapter.on_turn_error = _on_turn_error
        _ADAPTER = adapter
    return _ADAPTER


router = APIRouter()


@router.post("/api/messages")
async def teams_messages(request: Request) -> Response:
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    invoke_response = await _adapter().process_activity(
        auth_header, activity, _BOT.on_turn
    )
    if invoke_response is None:
        return Response(status_code=201)
    if invoke_response.body is None:
        return Response(status_code=invoke_response.status)
    return Response(
        content=json.dumps(invoke_response.body),
        status_code=invoke_response.status,
        media_type="application/json",
    )
