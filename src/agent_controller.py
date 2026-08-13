"""
Central agent controller — routes user messages.

LLM autonomy:
  merge_additional_details() weaves new user input into combined_content (Problem/Design/Impact).
  assess_case_study_content() does section status, readiness, questions, and guide reply.
  Python only routes commands and displays results — no dumb text append for case study content.

Deterministic: Title:, layout, generate, greet, off-topic, file upload routing.
"""
import re

from src.agent_responder import guide_message_from_assessment
from src.chat_assistant import (
    answer_user_question,
    classify_user_intent,
    greeting_reply,
    off_topic_reply,
)
from src.content_merger import merge_additional_details
from src.content_reviewer import assess_case_study_content
from src.guide_policy import build_pre_generate_message, deck_ready
from src.readiness import (
    is_detailed_template_request,
    is_explicit_review_request,
    is_readiness_advice_request,
    readiness_from_assessment,
    should_show_full_review,
)
from src.schemas import AgentResponse, CaseStudyState
from src.title_utils import merge_title_into_content, parse_title_message

# ── Layout / tone / audience ─────────────────────────────────────────────────

_LAYOUT_PATTERNS = [
    (re.compile(r"\b(exact(ly)?\s*(3|three)\s*slides?|always\s*(3|three)\s*slides?)\b", re.I), "exact_3_slides"),
    (re.compile(r"\bcompact\b|\bfewer\s*slides?\b|\b2\s*slides?\b", re.I), "compact"),
    (re.compile(r"\bsplit(\s*if\s*needed)?\b|\bmore\s*slides?\b|\bcontinuation\b", re.I), "split_if_needed"),
    (re.compile(r"\bone[\s_-]section[\s_-]per[\s_-]slide\b", re.I), "one_section_per_slide"),
]
_TONE_PATTERNS = [
    (re.compile(r"\bexecutive\b", re.I), "executive"),
    (re.compile(r"\btechnical\b", re.I), "technical"),
    (re.compile(r"\bbusiness\b", re.I), "business"),
    (re.compile(r"\bprofessional\b", re.I), "professional"),
]
_AUDIENCE_PATTERNS = [
    (re.compile(r"\bleadership\b|\bc-suite\b|\bc suite\b", re.I), "leadership"),
    (re.compile(r"\btechnical\b|\bengineers?\b|\bdevs?\b|\bdevelopers?\b", re.I), "technical"),
    (re.compile(r"\bsales\b", re.I), "sales"),
    (re.compile(r"\bgeneral\b", re.I), "general"),
]
_TOPIC_PATTERNS = [
    re.compile(
        r"(?:case\s+study|ppt|powerpoint|deck|presentation|slides?)\s+"
        r"(?:for|on|about|of|regarding)\s+(.+?)(?:\.|,|$)",
        re.I,
    ),
    re.compile(r"(?:for|on|about|regarding)\s+([A-Z][^.,]{3,80})(?:\.|,|$)", re.I),
]


def _extract_layout_preference(message: str) -> str | None:
    for pattern, value in _LAYOUT_PATTERNS:
        if pattern.search(message):
            return value
    return None


def _extract_tone(message: str) -> str | None:
    for pattern, value in _TONE_PATTERNS:
        if pattern.search(message):
            return value
    return None


def _extract_audience(message: str) -> str | None:
    for pattern, value in _AUDIENCE_PATTERNS:
        if pattern.search(message):
            return value
    return None


def _extract_topic(message: str) -> str:
    for pat in _TOPIC_PATTERNS:
        m = pat.search(message)
        if m:
            topic = m.group(1).strip()
            topic = re.sub(r"(?i)\s*\b(project|solution|initiative|for us|for me)\s*$", "", topic).strip()
            if 3 <= len(topic) <= 80:
                return topic
    return ""


def _layout_label(preference: str) -> str:
    return {
        "exact_3_slides": "Exactly 3 slides — compressed if needed",
        "compact": "Compact — 2 slides where possible",
        "split_if_needed": "Split if needed — continuation slides allowed",
        "one_section_per_slide": "One section per slide (default 3-slide layout)",
        "auto": "Auto — I'll decide based on content length",
    }.get(preference, preference)


def _build_review_context(merged: str, state: CaseStudyState | None) -> str:
    if state and state.title:
        return merge_title_into_content(merged, state.title)
    return merged


def _run_assessment(
    content: str,
    *,
    latest_message: str = "",
    interaction_mode: str = "guide",
    prior_assessment: dict | None = None,
) -> dict:
    return assess_case_study_content(
        content,
        latest_message=latest_message,
        interaction_mode=interaction_mode,
        prior_assessment=prior_assessment,
    )


def _base_state_updates(store_content: str, assessment: dict) -> dict:
    updates = {
        "original_content": store_content,
        "combined_content": store_content,
        "review_result": assessment,
        "structured_content": None,
        "generated_ppt_blob": None,
    }
    if assessment.get("title_status") == "provided":
        title = str(assessment.get("detected_title") or "").strip()
        if title:
            updates["title"] = title
    return updates


def _debug_from_assessment(intent: str, assessment: dict, content_len: int) -> dict:
    readiness = readiness_from_assessment(assessment)
    return {
        "detected_intent": intent,
        "section_status": assessment.get("section_status") or {},
        "section_coverage": assessment.get("section_coverage") or {},
        "readiness_level": readiness.get("readiness_level"),
        "enough_to_generate": readiness.get("enough_to_generate"),
        "already_captured": assessment.get("already_captured") or [],
        "priority_focus": assessment.get("priority_focus") or [],
        "review_context_length": content_len,
    }


def _guide_response(
    *,
    user_message: str,
    intent_label: str,
    review_content: str,
    store_content: str,
    assessment: dict,
    phase: str,
) -> AgentResponse:
    """LLM-authored conversational guide — no formal review card."""
    reply = guide_message_from_assessment(assessment)
    new_phase = "collecting" if phase == "collecting" else (
        "reviewed" if assessment.get("can_continue") else "needs_content"
    )
    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": reply}],
        new_phase=new_phase,
        state_updates=_base_state_updates(store_content, assessment),
        debug_info=_debug_from_assessment(intent_label, assessment, len(review_content)),
    )


def _full_review_response(
    *,
    intent_label: str,
    review_content: str,
    store_content: str,
    assessment: dict,
) -> AgentResponse:
    """Formal review card from LLM assessment."""
    new_phase = "reviewed" if assessment.get("can_continue") else "needs_content"
    messages: list[dict] = [{"role": "assistant", "msg_type": "review", "review": assessment}]

    bridge = (assessment.get("conversational_reply") or "").strip()
    if bridge:
        messages.append({"role": "assistant", "content": bridge})

    return AgentResponse(
        assistant_messages=messages,
        new_phase=new_phase,
        state_updates=_base_state_updates(store_content, assessment),
        debug_info=_debug_from_assessment(intent_label, assessment, len(review_content)),
    )


def _update_content_and_respond(
    *,
    user_message: str,
    merged: str,
    state: CaseStudyState | None,
    intent_label: str,
    intent: str,
    phase: str,
    force_full_review: bool = False,
    interaction_mode: str = "guide",
) -> AgentResponse:
    review_content = _build_review_context(merged, state)

    show_full = force_full_review or should_show_full_review(
        user_message, intent, phase,
        content_length=len(review_content),
        explicit_review_requested=is_explicit_review_request(user_message),
    )

    mode = "full_review" if show_full else interaction_mode
    prior = state.review if state and state.review else None
    assessment = _run_assessment(
        review_content,
        latest_message=user_message,
        interaction_mode=mode,
        prior_assessment=prior,
    )

    if show_full:
        return _full_review_response(
            intent_label=intent_label,
            review_content=review_content,
            store_content=merged,
            assessment=assessment,
        )

    return _guide_response(
        user_message=user_message,
        intent_label=intent_label,
        review_content=review_content,
        store_content=merged,
        assessment=assessment,
        phase=phase,
    )


# ── Intent handlers ───────────────────────────────────────────────────────────

def _handle_new_case_study_request(message: str, state: CaseStudyState | None) -> AgentResponse:
    topic = _extract_topic(message)
    assessment = _run_assessment(message, latest_message=message, interaction_mode="guide")
    reply = guide_message_from_assessment(assessment)

    updates = _base_state_updates(message, assessment)
    if topic:
        updates["title"] = topic
        updates["topic"] = topic

    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": reply}],
        new_phase="collecting",
        state_updates=updates,
        debug_info=_debug_from_assessment("new_case_study_request", assessment, len(message)),
    )


def _handle_content_addition(
    message: str,
    phase: str,
    case_content: str,
    review_result: dict | None,
    state: CaseStudyState | None,
    intent: str = "content_addition",
) -> AgentResponse:
    merged = merge_additional_details(case_content, message, review_result) if case_content else message
    return _update_content_and_respond(
        user_message=message,
        merged=merged,
        state=state,
        intent_label="content_addition",
        intent=intent,
        phase=phase,
    )


def _handle_submit_content(
    message: str,
    state: CaseStudyState | None,
    phase: str,
    case_content: str = "",
    review_result: dict | None = None,
) -> AgentResponse:
    # LLM merge even on full paste — weaves into existing narrative or treats as rewrite (Mode B)
    merged = (
        merge_additional_details(case_content, message, review_result)
        if case_content.strip()
        else message
    )
    return _update_content_and_respond(
        user_message=message,
        merged=merged,
        state=state,
        intent_label="submit_content",
        intent="submit_content",
        phase=phase,
    )


def _handle_explicit_review(message: str, case_content: str, state: CaseStudyState | None) -> AgentResponse:
    if not case_content:
        return AgentResponse(
            assistant_messages=[{
                "role": "assistant",
                "content": "No content to review yet. Describe your case study or paste your content first.",
            }],
            debug_info={"detected_intent": "explicit_review", "blocked": "no_content"},
        )
    review_content = _build_review_context(case_content, state)
    prior = state.review if state and state.review else None
    assessment = _run_assessment(
        review_content,
        latest_message=message,
        interaction_mode="readiness_advice",
        prior_assessment=prior,
    )
    return _guide_response(
        user_message=message,
        intent_label="explicit_review",
        review_content=review_content,
        store_content=case_content,
        assessment=assessment,
        phase="reviewed",
    )


def _handle_readiness_advice(
    message: str,
    case_content: str,
    state: CaseStudyState | None,
    review_result: dict | None,
    *,
    detailed_template: bool = False,
) -> AgentResponse:
    review_content = _build_review_context(case_content, state) if case_content else ""
    mode = "detailed_template" if detailed_template else "readiness_advice"

    if review_context := review_content:
        prior = (state.review if state and state.review else None) or review_result
        assessment = _run_assessment(
            review_context,
            latest_message=message,
            interaction_mode=mode,
            prior_assessment=prior,
        )
        updates = _base_state_updates(case_content, assessment) if not review_result else {}
    else:
        assessment = {
            "conversational_reply": (
                "Share your case study details first — describe the project, paste content, or upload a file. "
                "I'll track Problem, Design, and Impact as you go."
            ),
            "can_continue": False,
            "enough_to_generate": False,
            "section_status": {k: "missing" for k in ("problem_statement", "design_implementation", "impact")},
        }
        updates = {}

    reply = guide_message_from_assessment(assessment)
    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": reply}],
        state_updates=updates,
        debug_info=_debug_from_assessment("readiness_advice", assessment, len(review_context)),
    )


def _handle_layout_preference(message: str, current_layout: str) -> AgentResponse:
    new_layout = _extract_layout_preference(message) or current_layout
    label = _layout_label(new_layout)
    reply = (
        f"Got it — layout set to: **{label}**\n\n"
        "Say **generate** or click **Continue and generate PPT** when ready."
    )
    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": reply}],
        state_updates={"layout_preference": new_layout},
        debug_info={"detected_intent": "layout_preference", "layout": new_layout},
    )


def _handle_revise(message: str, current_layout: str, current_tone: str) -> AgentResponse:
    updates: dict = {}
    if new_layout := _extract_layout_preference(message):
        updates["layout_preference"] = new_layout
    if new_tone := _extract_tone(message):
        updates["tone"] = new_tone
    if new_audience := _extract_audience(message):
        updates["audience"] = new_audience

    if updates:
        parts = []
        if "layout_preference" in updates:
            parts.append(f"layout → **{_layout_label(updates['layout_preference'])}**")
        if "tone" in updates:
            parts.append(f"tone → **{updates['tone']}**")
        if "audience" in updates:
            parts.append(f"audience → **{updates['audience']}**")
        reply = f"Applying changes ({', '.join(parts)}) and regenerating..."
    else:
        reply = "Applying your revision and regenerating the deck..."

    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": reply}],
        trigger_generate=True,
        state_updates=updates,
        debug_info={"detected_intent": "revise"},
    )


def _handle_title_update(title: str, case_content: str) -> AgentResponse:
    updates: dict = {"title": title}
    if case_content:
        updated = merge_title_into_content(case_content, title)
        updates["combined_content"] = updated
        updates["original_content"] = updated
        msg = f"Title saved: **{title}**\n\nSay **generate** when ready, or keep adding details."
    else:
        msg = f"Title saved: **{title}**\n\nPaste or upload content when you're ready."

    return AgentResponse(
        assistant_messages=[{"role": "assistant", "content": msg}],
        state_updates=updates,
        debug_info={"detected_intent": "title_update", "title": title},
    )


# ── Main entry point ─────────────────────────────────────────────────────────

def handle_user_message(
    message: str,
    phase: str,
    review_result: dict | None,
    has_content: bool,
    case_content: str,
    recent_messages: list,
    layout_preference: str = "auto",
    tone: str = "professional",
    audience: str = "leadership",
    case_study_state: CaseStudyState | None = None,
) -> AgentResponse:
    title = parse_title_message(message)
    if title is not None:
        return _handle_title_update(title, case_content)

    if is_explicit_review_request(message):
        return _handle_explicit_review(message, case_content, case_study_state)

    if is_detailed_template_request(message):
        return _handle_readiness_advice(
            message, case_content, case_study_state, review_result, detailed_template=True
        )

    if is_readiness_advice_request(message):
        return _handle_readiness_advice(message, case_content, case_study_state, review_result)

    intent = classify_user_intent(message, phase, review_result, has_content)

    if intent == "greeting":
        return AgentResponse(
            assistant_messages=[{"role": "assistant", "content": greeting_reply(phase, message)}],
            debug_info={"detected_intent": "greeting"},
        )

    if intent == "off_topic":
        return AgentResponse(
            assistant_messages=[{"role": "assistant", "content": off_topic_reply()}],
            debug_info={"detected_intent": "off_topic"},
        )

    if intent == "new_case_study_request":
        return _handle_new_case_study_request(message, case_study_state)

    if intent == "question":
        reply = answer_user_question(message, phase, case_content, review_result, recent_messages)
        return AgentResponse(
            assistant_messages=[{"role": "assistant", "content": reply}],
            debug_info={"detected_intent": "question"},
        )

    if intent == "layout_preference":
        return _handle_layout_preference(message, layout_preference)

    if intent == "revise":
        if not has_content:
            return AgentResponse(
                assistant_messages=[{
                    "role": "assistant",
                    "content": "Paste or upload your case study content first, then I can revise.",
                }],
                debug_info={"detected_intent": "revise", "blocked": "no_content"},
            )
        return _handle_revise(message, layout_preference, tone)

    if intent == "generate":
        if not has_content and "anyway" not in message.lower():
            return AgentResponse(
                assistant_messages=[{
                    "role": "assistant",
                    "content": (
                        "You haven't shared any case study details yet. "
                        "Describe your project or paste content first — "
                        "or say **generate anyway** for a blank deck."
                    ),
                }],
                debug_info={"detected_intent": "generate", "blocked": "no_content"},
            )

        generate_anyway = "anyway" in message.lower()
        if not generate_anyway and has_content:
            review_ctx = _build_review_context(case_content, case_study_state)
            assessment = review_result or {}
            if not assessment.get("section_status") and review_ctx:
                assessment = _run_assessment(review_ctx, latest_message=message, interaction_mode="guide")

            if assessment and not deck_ready(assessment):
                reply = build_pre_generate_message(assessment, review_ctx or case_content)
                return AgentResponse(
                    assistant_messages=[{"role": "assistant", "content": reply}],
                    debug_info={
                        "detected_intent": "generate",
                        "blocked": "pre_generate_strengthen",
                        "deck_ready": False,
                    },
                )

        return AgentResponse(
            trigger_generate=True,
            debug_info={"detected_intent": "generate"},
        )

    if intent == "content_addition":
        return _handle_content_addition(
            message, phase, case_content, review_result, case_study_state, intent
        )

    if intent == "submit_content":
        return _handle_submit_content(
            message, case_study_state, phase, case_content, review_result
        )

    if case_content:
        return _handle_content_addition(
            message, phase, case_content, review_result, case_study_state, "fallback_merge"
        )
    return _handle_submit_content(
        message, case_study_state, phase, case_content, review_result
    )
