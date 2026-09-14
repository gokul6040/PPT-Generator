"""Chat session orchestration — shared by Streamlit UI and FastAPI."""
from __future__ import annotations

import io
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.agent_controller import handle_user_message as ac_handle_message
from src.agent_responder import generate_post_generate_warning
from src.content_reviewer import assess_case_study_content
from src.content_structurer import structure_case_study_content
from src.file_reader import read_uploaded_file
from src.guide_policy import build_pre_generate_message, deck_ready
from src.layout_planner import plan_layout
from src.ppt_generator import generate_case_study_ppt_bytes
from src.schemas import CaseStudyState
from src.slide_writer import write_slide_content
from src.storage import (
    read_download,
    resolve_template_path,
    save_generated_ppt,
    upload_user_template,
)
from src.template_analyzer import analyze_template
from src.token_tracker import ensure_session_initialized, reset_session_id
from src.session_context import bind_session_getter

WELCOME = (
    "Upload a file or paste your project details. I'll review the content, "
    "identify missing information, and generate a presentation when ready."
)


def _format_ts() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def _msg_id() -> str:
    return uuid.uuid4().hex


@dataclass
class ChatSession:
    """In-memory chat session mirroring former Streamlit session_state."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[dict[str, Any]] = field(default_factory=list)
    phase: str = "start"
    original_content: str = ""
    combined_content: str = ""
    review_result: dict | None = None
    structured_content: dict | None = None
    generated_ppt_blob: str | None = None
    uploaded_template_name: str | None = None
    uploaded_template_bytes: bytes | None = None
    uploaded_template_blob: str | None = None
    layout_preference: str = "auto"
    tone: str = "professional"
    audience: str = "leadership"
    title: str = ""
    topic: str = ""
    case_study_state: CaseStudyState | None = None
    slide_bullets: dict | None = None
    layout_plan: dict | None = None
    token_session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    _token_binding: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.messages:
            self.messages = [_assistant(WELCOME)]

    def as_token_dict(self) -> dict[str, Any]:
        self._token_binding["token_session_id"] = self.token_session_id
        return self._token_binding

    def bind(self) -> None:
        bind_session_getter(lambda: self.as_token_dict())


def _assistant(content: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "id": _msg_id(),
        "role": "assistant",
        "content": content,
        "timestamp": _format_ts(),
        **extra,
    }


def _user(content: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "id": _msg_id(),
        "role": "user",
        "content": content,
        "timestamp": _format_ts(),
        **extra,
    }


def new_session() -> ChatSession:
    session = ChatSession()
    session.bind()
    ensure_session_initialized()
    return session


def _get_case_study_state(session: ChatSession) -> CaseStudyState:
    if not isinstance(session.case_study_state, CaseStudyState):
        session.case_study_state = CaseStudyState(
            layout_preference=session.layout_preference,
            tone=session.tone,
            audience=session.audience,
        )
    return session.case_study_state


def _sync_case_study_state(session: ChatSession) -> None:
    from src.title_utils import extract_explicit_title

    state = _get_case_study_state(session)
    content = (session.combined_content or session.original_content or "").strip()
    if content:
        state.update_from_content(content)
    review = session.review_result
    if review:
        state.update_review(review)
    state.layout_preference = session.layout_preference
    state.tone = session.tone
    state.audience = session.audience

    title = (session.title or "").strip()
    if not title and review and review.get("title_status") == "provided":
        title = str(review.get("detected_title") or "").strip()
        if title:
            session.title = title
    if not title and content:
        title = extract_explicit_title(content)
        if title:
            session.title = title
    if title:
        state.set_title(title)

    topic = (session.topic or "").strip()
    if topic:
        state.topic = topic

    if review:
        coverage = review.get("section_status") or review.get("section_coverage") or {}
        if coverage:
            state.update_section_coverage(coverage)


def _append(session: ChatSession, role: str, content: str = "", **extra: Any) -> None:
    msg = _assistant(content, **extra) if role == "assistant" else _user(content, **extra)
    session.messages.append(msg)


def _current_case_content(session: ChatSession) -> str:
    return (session.combined_content or session.original_content or "").strip()


def _storage_session_id(session: ChatSession) -> str:
    return session.token_session_id or session.session_id


def _get_template_path(session: ChatSession) -> str:
    if session.uploaded_template_bytes and not session.uploaded_template_blob:
        ref = upload_user_template(
            _storage_session_id(session),
            session.uploaded_template_name or "uploaded_template.pptx",
            session.uploaded_template_bytes,
        )
        session.uploaded_template_blob = ref.blob_name

    return resolve_template_path(
        _storage_session_id(session),
        uploaded_name=session.uploaded_template_name,
        uploaded_bytes=session.uploaded_template_bytes,
        uploaded_blob=session.uploaded_template_blob,
    )


def _run_review(session: ChatSession, content: str) -> None:
    session.combined_content = content.strip()
    result = assess_case_study_content(
        session.combined_content,
        interaction_mode="full_review",
    )
    session.review_result = result
    session.structured_content = None
    session.generated_ppt_blob = None
    session.phase = "reviewed" if result.get("can_continue") else "needs_content"
    _append(session, "assistant", msg_type="review", review=result)
    _sync_case_study_state(session)


def can_show_action_buttons(session: ChatSession) -> bool:
    if not _current_case_content(session) or not session.review_result:
        return False
    return session.phase in (
        "reviewed",
        "awaiting_details",
        "done",
        "generated",
        "needs_content",
        "collecting",
    )


def _resolve_title(session: ChatSession) -> str:
    from src.title_utils import extract_explicit_title

    title = (session.title or "").strip()
    if title:
        return title

    state = session.case_study_state
    if isinstance(state, CaseStudyState) and state.title.strip():
        return state.title.strip()

    review = session.review_result or {}
    if review.get("title_status") == "provided":
        detected = str(review.get("detected_title") or "").strip()
        if detected:
            return detected

    return extract_explicit_title(_current_case_content(session))


def _blank_slide_sections(review: dict | None, structured: dict) -> list[str]:
    notes: list[str] = []
    heading_map = {
        "problem_statement": "Problem Statement",
        "design_implementation": "Design and Implementation",
        "impact": "Impact",
    }
    sections_by_heading = {s.get("heading"): s for s in structured.get("sections", [])}
    coverage = (review or {}).get("section_coverage") or {}
    section_status = (review or {}).get("section_status") or {}
    for key, label in heading_map.items():
        status = section_status.get(key) or coverage.get(key, "missing")
        if status == "missing" or not sections_by_heading.get(label, {}).get("content", "").strip():
            notes.append(label)
    return notes


def _blank_section_note(review: dict | None, structured: dict) -> str:
    notes = _blank_slide_sections(review, structured)
    if not notes:
        return ""
    return f"\n\n_Note: Left blank — {', '.join(notes)}._"


def _pre_generate_gate(session: ChatSession, user_message: str) -> bool:
    if "anyway" in user_message.lower():
        return True
    content = _current_case_content(session)
    if not content:
        return False
    review = session.review_result or {}
    if review and not deck_ready(review):
        _append(session, "assistant", build_pre_generate_message(review, content))
        return False
    return True


def _run_generate(session: ChatSession) -> None:
    _sync_case_study_state(session)
    state = _get_case_study_state(session)
    content = state.build_generation_context()
    if not content:
        content = session.combined_content or session.original_content or ""
    if not content:
        _append(session, "assistant", "No case study content available to generate from. Add details first.")
        return

    from src.title_utils import resolve_ppt_banner_title

    user_title = _resolve_title(session)
    banner_title, title_used_placeholder = resolve_ppt_banner_title(user_title)
    review = session.review_result
    structured = structure_case_study_content(content)
    if user_title:
        structured["title"] = user_title
    session.structured_content = structured

    slide_content = write_slide_content(structured, session.tone, session.audience)
    slide_content["title"] = banner_title
    # Keep the persisted field name for backward-compatible session restoration.
    session.slide_bullets = slide_content

    template_path = _get_template_path(session)
    template_profile = analyze_template(template_path)
    layout_plan = plan_layout(slide_content, template_profile, session.layout_preference)
    session.layout_plan = layout_plan

    pptx_bytes, file_name = generate_case_study_ppt_bytes(
        slide_content,
        template_path,
        layout_plan=layout_plan,
        title_override=banner_title,
    )
    stored = save_generated_ppt(_storage_session_id(session), pptx_bytes, file_name)
    session.generated_ppt_blob = stored.blob_name
    session.phase = "generated"

    blank_sections = _blank_slide_sections(review, structured)
    blank_note = _blank_section_note(review, structured)
    warning = generate_post_generate_warning(
        review or {},
        case_content=content,
        title_missing=title_used_placeholder,
        blank_slide_sections=blank_sections,
    )
    warning_note = f"\n\n_{warning}_" if warning else ""
    _append(
        session,
        "assistant",
        f"Your PowerPoint is ready: **{stored.file_name}**{blank_note}{warning_note}",
        download_blob=stored.blob_name,
        download_file_name=stored.file_name,
    )
    _sync_case_study_state(session)


def handle_message(session: ChatSession, text: str) -> None:
    text = text.strip()
    if not text:
        return
    _append(session, "user", text)
    phase = session.phase
    try:
        _sync_case_study_state(session)
        response = ac_handle_message(
            message=text,
            phase=phase,
            review_result=session.review_result,
            has_content=bool(_current_case_content(session)),
            case_content=_current_case_content(session),
            recent_messages=session.messages,
            layout_preference=session.layout_preference,
            tone=session.tone,
            audience=session.audience,
            case_study_state=_get_case_study_state(session),
        )
        for k, v in response.state_updates.items():
            if k == "case_study_state" and isinstance(v, CaseStudyState):
                session.case_study_state = v
            elif hasattr(session, k):
                setattr(session, k, v)
            elif k in ("original_content", "combined_content", "review_result", "title", "topic"):
                setattr(session, k, v)

        if response.new_phase:
            session.phase = response.new_phase

        for msg in response.assistant_messages:
            normalized = dict(msg)
            normalized.setdefault("id", _msg_id())
            normalized.setdefault("timestamp", _format_ts())
            session.messages.append(normalized)

        _sync_case_study_state(session)
        if response.trigger_generate:
            _run_generate(session)
    except Exception as e:
        _append(session, "assistant", f"Something went wrong: {e}")
        print(traceback.format_exc())


def handle_upload(session: ChatSession, name: str, raw: bytes) -> None:
    wrapper = io.BytesIO(raw)
    wrapper.name = name
    extracted = read_uploaded_file(wrapper)

    if name.lower().endswith(".pptx") and len(extracted.split()) < 25:
        session.uploaded_template_name = name
        session.uploaded_template_bytes = raw
        session.uploaded_template_blob = None
        ref = upload_user_template(_storage_session_id(session), name, raw)
        session.uploaded_template_blob = ref.blob_name
        _append(
            session,
            "assistant",
            f"Got it — **{name}** is now your slide template. "
            "Tell me about your case study or paste your content whenever you're ready.",
        )
        return

    if not extracted.strip():
        _append(
            session,
            "assistant",
            f"Couldn't read any text from **{name}**. "
            "Try a .txt, .docx, or .pdf with your case study content.",
        )
        return

    preview = extracted[:280] + ("..." if len(extracted) > 280 else "")
    _append(session, "user", f"Uploaded: {name}\n\n{preview}")
    session.original_content = extracted
    _run_review(session, extracted)


def clear_session(session: ChatSession) -> None:
    """Reset conversation; preserve template and tone settings."""
    template_name = session.uploaded_template_name
    template_bytes = session.uploaded_template_bytes
    template_blob = session.uploaded_template_blob
    layout = session.layout_preference
    tone = session.tone
    audience = session.audience

    session.messages = []
    session.phase = "start"
    session.original_content = ""
    session.combined_content = ""
    session.review_result = None
    session.structured_content = None
    session.generated_ppt_blob = None
    session.title = ""
    session.topic = ""
    session.case_study_state = None
    session.slide_bullets = None
    session.layout_plan = None

    session.uploaded_template_name = template_name
    session.uploaded_template_bytes = template_bytes
    session.uploaded_template_blob = template_blob
    session.layout_preference = layout
    session.tone = tone
    session.audience = audience

    session.bind()
    reset_session_id()
    session.token_session_id = session._token_binding.get(
        "token_session_id", uuid.uuid4().hex[:8]
    )
    session.messages = [_assistant(WELCOME)]


def session_to_api(session: ChatSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "phase": session.phase,
        "combined_content": session.combined_content,
        "review_result": session.review_result,
        "show_action_buttons": can_show_action_buttons(session),
        "messages": [_public_message(m, session.session_id) for m in session.messages],
    }


def _public_message(msg: dict[str, Any], session_id: str) -> dict[str, Any]:
    out = {
        "id": msg.get("id") or _msg_id(),
        "role": msg["role"],
        "content": msg.get("content", ""),
        "timestamp": msg.get("timestamp") or _format_ts(),
    }
    if msg.get("msg_type") == "review":
        out["msg_type"] = "review"
        out["review"] = msg.get("review")
    if msg.get("download_blob"):
        out["download_blob"] = msg["download_blob"]
        out["download_file_name"] = msg.get("download_file_name")
        out["download_url"] = (
            f"/chat/download?session_id={session_id}&blob_name={msg['download_blob']}"
        )
    return out


def get_download(session: ChatSession, blob_name: str, file_name: str | None = None):
    return read_download(blob_name=blob_name, file_name=file_name)
