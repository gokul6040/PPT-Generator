"""Interactive chat: intent routing and grounded Q&A for the case study agent."""
import re

from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

VALID_INTENTS = {
    "greeting",
    "new_case_study_request",
    "off_topic",
    "question",
    "content_addition",
    "submit_content",
    "generate",
    "layout_preference",
    "revise",
}

_GREETING_RE = re.compile(
    r"^(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening))[\s!.,?]*$",
    re.I,
)
_SMALLTALK_RE = re.compile(
    r"^(how are you|how'?s it going|what'?s up|how do you do|how r u)[\s!.,?]*$",
    re.I,
)
_GENERATE_RE = re.compile(
    r"^(continue(\s+and\s+generate(\s+ppt)?)?|generate(\s+(the\s+)?(ppt|powerpoint|anyway))?|"
    r"go\s+ahead|build\s+(the\s+)?(ppt|powerpoint)|create\s+(the\s+)?(ppt|powerpoint)|"
    r"generate\s+anyway)[\s!.,?]*$",
    re.I,
)
_LAYOUT_PREF_RE = re.compile(
    r"^(keep\s+exactly\s+\d+\s+slides?|exactly\s+\d+\s+slides?|split\s+if\s+needed|"
    r"compact\s+layout|use\s+(a\s+)?compact|one\s+section\s+per\s+slide)[\s!.,?]*$",
    re.I,
)
# Matches "I want to create a case study on X" — short messages only
_NEW_CS_REQUEST_RE = re.compile(
    r"(?:"
    r"i\s+(?:want|need|would\s+like)\s+(?:to\s+)?(?:create|build|make|generate)\b"
    r"|(?:create|build|make|generate|help\s+(?:me|us)\s+(?:create|make|build))\b"
    r")"
    r"[^.]{0,60}?"
    r"(?:case\s+study|ppt|powerpoint|deck|presentation|slides?)",
    re.I,
)


def _fast_intent(message: str, phase: str) -> str | None:
    text = message.strip()
    if not text:
        return None
    if _GREETING_RE.match(text) or _SMALLTALK_RE.match(text):
        return "greeting"
    if phase in ("reviewed", "awaiting_details", "done", "generated", "collecting") and _GENERATE_RE.match(text):
        return "generate"
    if _LAYOUT_PREF_RE.match(text):
        return "layout_preference" if phase != "generated" else "revise"
    # new_case_study_request: only for short messages without substantial content
    if _NEW_CS_REQUEST_RE.search(text) and len(text.split()) < 50:
        return "new_case_study_request"
    return None


def classify_user_intent(
    message: str,
    phase: str,
    review_result: dict | None = None,
    has_content: bool = False,
) -> str:
    """Return intent string for routing in app.py."""
    quick = _fast_intent(message, phase)
    if quick:
        return quick

    system_prompt = load_prompt("chat_intent_prompt.md")
    client, model = get_llm_client()

    review_block = ""
    if review_result:
        missing = review_result.get("missing_weak") or []
        questions = review_result.get("questions_to_user") or []
        if missing:
            review_block += "\nMissing/weak from last review:\n" + "\n".join(f"- {m}" for m in missing[:12])
        if questions:
            review_block += "\nQuestions from last review:\n" + "\n".join(f"- {q}" for q in questions[:8])

    user_payload = (
        f"Phase: {phase}\n"
        f"Case study already provided: {has_content}\n"
        f"User message:\n{message.strip()}"
        f"{review_block}"
    )

    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.0,
    )

    raw = response.choices[0].message.content or ""
    result = parse_json_response(raw)
    intent = str(result.get("intent", "question")).strip().lower()
    if intent not in VALID_INTENTS:
        intent = "revise" if phase == "generated" and "revis" in intent else "question"
    return intent


def _format_review_for_context(review_result: dict | None) -> str:
    if not review_result:
        return ""
    parts = []
    for key, label in (
        ("available_strong", "Available / Strong"),
        ("missing_weak", "Missing / Weak"),
        ("questions_to_user", "Questions"),
    ):
        items = review_result.get(key) or []
        if items:
            parts.append(f"{label}:\n" + "\n".join(f"- {i}" for i in items))
    note = review_result.get("impact_note")
    if note:
        parts.append(f"Impact note: {note}")
    return "\n\n".join(parts)


def _format_recent_messages(messages: list, limit: int = 8) -> str:
    recent = messages[-limit:] if messages else []
    lines = []
    for msg in recent:
        role = msg.get("role", "user")
        if msg.get("msg_type") == "review":
            lines.append("assistant: [shared content review]")
            continue
        content = str(msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:600]}")
    return "\n".join(lines)


def greeting_reply(phase: str, message: str = "") -> str:
    if _SMALLTALK_RE.match((message or "").strip()):
        return (
            "Doing well, thanks! Ready when you are.\n\n"
            "Tell me about your case study — paste content, attach a file, "
            "or describe the project and I'll guide you through Problem, Design, and Impact."
        )
    if phase == "collecting":
        return (
            "Hi! I'm helping you build your case study deck.\n\n"
            "Share details for Problem, Design & Implementation, and Impact — "
            "or say **generate anyway** when you want to proceed with what's available."
        )
    if phase in ("reviewed", "awaiting_details", "needs_content"):
        return (
            "Hi! I'm your TurnB Case Study PPT Generator agent.\n\n"
            "Add more details any time — I'll show section status and ask only what's still missing. "
            "Say **review the content so far** for a full review, or **generate** when ready."
        )
    if phase == "generated":
        return (
            "Hi! Your deck was just generated.\n\n"
            "You can **download** it above, ask for **revisions** (e.g. 'make it shorter', "
            "'more executive', 'keep exactly 3 slides'), or paste new content to start another case study."
        )
    if phase == "done":
        return (
            "Hi! Welcome back to the TurnB Case Study PPT Generator.\n\n"
            "Say **generate** or click **Continue and generate PPT** to rebuild the deck, "
            "add details to refine the story, or paste new content to start another case study."
        )
    return (
        "Hi! Welcome to the TurnB Case Study PPT Generator.\n\n"
        "Tell me what case study you'd like to create, paste your content, or attach a file — "
        "I'll track Problem, Design & Implementation, and Impact, and ask what's still missing."
    )


def off_topic_reply() -> str:
    return (
        "I'm focused on helping you build case study PowerPoints — I can't help with that topic.\n\n"
        "Ask me about your case study content, the review feedback, what to add, or say **hi** "
        "if you want a quick orientation."
    )


def answer_user_question(
    message: str,
    phase: str,
    case_content: str = "",
    review_result: dict | None = None,
    recent_messages: list | None = None,
) -> str:
    """Grounded conversational reply about gaps, examples, or how the app works."""
    system_prompt = load_prompt("chat_assistant_prompt.md")
    client, model = get_llm_client()

    context_parts = [f"Current phase: {phase}"]
    if case_content.strip():
        snippet = case_content.strip()
        if len(snippet) > 3500:
            snippet = snippet[:3500] + "\n...[truncated]"
        context_parts.append(f"Case study content:\n{snippet}")

    review_ctx = _format_review_for_context(review_result)
    if review_ctx:
        context_parts.append(f"Latest review:\n{review_ctx}")

    if recent_messages:
        chat_ctx = _format_recent_messages(recent_messages)
        if chat_ctx:
            context_parts.append(f"Recent chat:\n{chat_ctx}")

    user_payload = "\n\n".join(context_parts) + f"\n\nUser message:\n{message.strip()}"

    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.35,
    )

    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise ValueError("Assistant returned an empty reply.")
    return reply
