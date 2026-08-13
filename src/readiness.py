"""
Routing helpers and thin accessors for LLM assessment output.

All section status, readiness, and questions come from assess_case_study_content().
Python does NOT heuristically judge content quality.
"""
import re

_SECTION_LABELS = {
    "problem_statement": "Problem Statement",
    "design_implementation": "Design and Implementation",
    "impact": "Impact",
}

_EXPLICIT_REVIEW_RE = re.compile(
    r"(?i)\b("
    r"review\s+(this|the\s+content|my\s+content|content\s+so\s+far|everything)|"
    r"check\s+(this|my\s+content|the\s+content)|"
    r"what\s+is\s+missing|what'?s\s+missing|"
    r"show\s+(me\s+)?(the\s+)?review|"
    r"run\s+(a\s+)?review|"
    r"full\s+review"
    r")\b",
)

_READINESS_ADVICE_RE = re.compile(
    r"(?i)\b("
    r"what\s+next|what\s+should\s+i\s+do\s+next|"
    r"what\s+is\s+the\s+best\s+thing|best\s+next\s+step|"
    r"is\s+this\s+good\s+enough|is\s+this\s+enough|"
    r"how\s+to\s+make\s+it\s+better|how\s+can\s+i\s+improve|"
    r"ready\s+to\s+generate|can\s+i\s+generate"
    r")\b",
)

_DETAILED_TEMPLATE_RE = re.compile(
    r"(?i)\b("
    r"give\s+me\s+(a\s+)?(detailed\s+)?(format|template)|"
    r"what\s+should\s+i\s+fill|"
    r"detailed\s+questions|"
    r"fill[\s-]in\s+template|"
    r"question\s+list|"
    r"what\s+details\s+do\s+i\s+need"
    r")\b",
)


def is_explicit_review_request(message: str) -> bool:
    text = message.strip()
    if re.match(r"(?i)^review[\s!.,?]*$", text):
        return True
    return bool(_EXPLICIT_REVIEW_RE.search(text))


def is_readiness_advice_request(message: str) -> bool:
    return bool(_READINESS_ADVICE_RE.search(message.strip()))


def is_detailed_template_request(message: str) -> bool:
    return bool(_DETAILED_TEMPLATE_RE.search(message.strip()))


def should_show_full_review(
    user_message: str,
    intent: str,
    phase: str,
    content_length: int,
    *,
    explicit_review_requested: bool = False,
    is_file_upload: bool = False,
    review_button_clicked: bool = False,
) -> bool:
    if review_button_clicked or is_file_upload:
        return True
    if explicit_review_requested or is_explicit_review_request(user_message):
        return True
    if intent == "submit_content" and content_length >= 400:
        return True
    if intent == "submit_content" and len(user_message.split()) >= 120:
        return True
    return False


def readiness_from_assessment(assessment: dict) -> dict:
    """Extract readiness view from LLM assessment (no heuristics)."""
    section_status = assessment.get("section_status") or {}
    hint = assessment.get("question_count_hint", "")
    q_count = len(assessment.get("questions_to_user") or [])
    if hint and "-" in hint:
        try:
            q_count = int(hint.split("-")[-1].strip())
        except ValueError:
            pass

    return {
        "readiness_level": assessment.get("readiness_level", "not_enough_to_generate"),
        "enough_to_generate": assessment.get("enough_to_generate", False),
        "quality_label": assessment.get("quality_label", "weak"),
        "section_status": section_status,
        "critical_missing_items": [
            item for item in (assessment.get("missing_weak") or [])
            if any(w in str(item).lower() for w in ("missing", "no ", "blank", "not provided"))
        ][:6],
        "top_improvement_items": list(assessment.get("top_improvement_items") or [])[:6],
        "recommended_question_count": q_count,
        "has_title": assessment.get("title_status") == "provided",
        "already_captured": list(assessment.get("already_captured") or []),
        "priority_focus": list(assessment.get("priority_focus") or []),
    }


def render_short_status(assessment_or_readiness: dict) -> str:
    """Render section status block from assessment or readiness dict."""
    section_status = (
        assessment_or_readiness.get("section_status")
        or {}
    )
    lines = ["Current status:", ""]
    for key, label in _SECTION_LABELS.items():
        status = section_status.get(key, "missing")
        lines.append(f"* {label}: {status}")
    return "\n".join(lines)


def build_post_generate_warning_template(assessment: dict, *, title_missing: bool = False) -> str:
    """Template fallback if post-generate warning LLM call fails."""
    parts: list[str] = []
    section_status = assessment.get("section_status") or {}

    if title_missing or assessment.get("title_status") == "missing":
        parts.append(
            "No title was provided — the banner uses the placeholder "
            "'[Title]'; add a real title and regenerate if needed."
        )

    for key, label in _SECTION_LABELS.items():
        status = section_status.get(key, "missing")
        if status == "missing":
            parts.append(f"{label} was thin or blank because no content was provided.")
        elif status == "weak":
            parts.append(f"{label} is thin — add more detail for a stronger deck.")

    if assessment.get("readiness_level") == "not_enough_to_generate":
        parts.insert(0, "Generated with very limited information.")

    if not parts:
        if assessment.get("quality_label") == "decent":
            return "Generated with available details. Add more impact metrics to strengthen the story."
        return ""

    prefix = (
        "Generated anyway. "
        if assessment.get("enough_to_generate")
        else "Generated with limited information. "
    )
    return prefix + " ".join(parts[:3])


# Backward compat alias used by app.py debug panel
def evaluate_readiness(state, review_result=None, *, content: str = ""):
    """Read readiness from stored LLM assessment; no Python judging."""
    if review_result and review_result.get("section_status"):
        return readiness_from_assessment(review_result)
    return {
        "readiness_level": "not_enough_to_generate",
        "enough_to_generate": bool(content.strip()),
        "quality_label": "weak",
        "section_status": {k: "missing" for k in _SECTION_LABELS},
        "critical_missing_items": [],
        "top_improvement_items": [],
        "recommended_question_count": 0,
        "has_title": False,
    }
