"""LLM assessment of case study content — status, readiness, questions, and guide reply."""
import re

from src.title_utils import extract_explicit_title
from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

REQUIRED_KEYS = {
    "acknowledgement",
    "section_status",
    "already_captured",
    "do_not_ask_about",
    "priority_focus",
    "readiness_level",
    "enough_to_generate",
    "deck_ready",
    "quality_label",
    "question_count_hint",
    "available_strong",
    "missing_weak",
    "questions_to_user",
    "top_improvement_items",
    "detected_title",
    "title_status",
    "suggested_title",
    "impact_note",
    "can_continue",
    "conversational_reply",
}

_VALID_STATUS = {"missing", "weak", "usable", "strong"}
_VALID_READINESS = {"not_enough_to_generate", "enough_but_weak", "decent", "strong"}

_NO_TITLE_NEGATIVE_RE = re.compile(
    r"(?i)(no\s+(explicit\s+)?title|title\s+(was\s+)?not\s+provided|title\s+is\s+missing|title\s+banner|left\s+blank)"
)
_SUGGESTED_TITLE_LINE_RE = re.compile(r"(?i)^suggested\s+title\s*:")


def _strip_title_contradictions(items: list[str]) -> list[str]:
    return [item for item in items if not _NO_TITLE_NEGATIVE_RE.search(str(item))]


def _strip_suggested_title_lines(items: list[str]) -> list[str]:
    return [item for item in items if not _SUGGESTED_TITLE_LINE_RE.search(str(item))]


def _reconcile_title_review(result: dict) -> None:
    """
    Keep title fields and missing_weak consistent after LLM assessment.
    LLM owns detection; Python only fixes impossible/contradictory states.
    """
    status = str(result.get("title_status") or "missing").lower().strip()
    if status not in ("provided", "missing"):
        status = "missing"

    detected = str(result.get("detected_title") or "").strip()
    suggested = str(result.get("suggested_title") or "").strip()

    if status == "provided" and not detected:
        status = "missing"
    elif status == "missing" and detected:
        status = "provided"

    if status == "provided":
        result["title_status"] = "provided"
        result["detected_title"] = detected
        result["suggested_title"] = ""
        result["missing_weak"] = _strip_title_contradictions(
            _strip_suggested_title_lines(result.get("missing_weak") or [])
        )
        return

    result["title_status"] = "missing"
    result["detected_title"] = ""
    missing_weak = _strip_title_contradictions(
        _strip_suggested_title_lines(result.get("missing_weak") or [])
    )
    if suggested:
        missing_weak.insert(0, f"Suggested title: {suggested}")
    result["suggested_title"] = suggested
    result["missing_weak"] = missing_weak


def _status_to_coverage(status: str) -> str:
    """Map 4-level status to 3-level section_coverage for legacy UI."""
    s = (status or "missing").lower()
    if s == "strong":
        return "strong"
    if s in ("usable", "weak"):
        return "weak"
    return "missing"


def _normalize_title_fields(result: dict, content: str) -> None:
    """Reconcile LLM title output; use content parser only when LLM left status ambiguous."""
    _reconcile_title_review(result)

    if result["title_status"] == "missing" and not result.get("suggested_title"):
        explicit = extract_explicit_title(content)
        if explicit:
            result["title_status"] = "provided"
            result["detected_title"] = explicit
            result["suggested_title"] = ""
            result["missing_weak"] = _strip_title_contradictions(
                _strip_suggested_title_lines(result.get("missing_weak") or [])
            )
        else:
            _reconcile_title_review(result)


def _normalize_assessment(result: dict, content: str) -> dict:
    """Validate and normalize LLM assessment JSON."""
    for key in (
        "already_captured", "do_not_ask_about", "priority_focus",
        "available_strong", "missing_weak", "questions_to_user", "top_improvement_items",
    ):
        result[key] = list(result.get(key) or [])

    result["acknowledgement"] = str(result.get("acknowledgement") or "").strip()
    result["impact_note"] = str(result.get("impact_note") or "").strip()
    result["question_count_hint"] = str(result.get("question_count_hint") or "").strip()
    result["conversational_reply"] = str(result.get("conversational_reply") or "").strip()
    result["suggested_title"] = str(result.get("suggested_title") or "").strip()

    section_status = dict(result.get("section_status") or {})
    for key in ("problem_statement", "design_implementation", "impact"):
        level = str(section_status.get(key, "missing")).lower().strip()
        section_status[key] = level if level in _VALID_STATUS else "missing"
    result["section_status"] = section_status

    result["section_coverage"] = {
        k: _status_to_coverage(v) for k, v in section_status.items()
    }

    readiness = str(result.get("readiness_level", "not_enough_to_generate")).lower().strip()
    result["readiness_level"] = readiness if readiness in _VALID_READINESS else "enough_but_weak"

    quality = str(result.get("quality_label", "weak")).lower().strip()
    result["quality_label"] = quality if quality in ("weak", "decent", "strong") else "weak"

    result["enough_to_generate"] = bool(result.get("enough_to_generate", True))
    result["deck_ready"] = bool(result.get("deck_ready", False))
    result["can_continue"] = bool(result.get("can_continue", True))

    _normalize_title_fields(result, content)

    if result["title_status"] == "provided":
        result["questions_to_user"] = [
            q for q in result["questions_to_user"]
            if not re.search(r"(?i)(what\s+(is\s+)?the\s+)?(case\s+study\s+)?title", str(q))
        ]

    return result


def assess_case_study_content(
    content: str,
    *,
    latest_message: str = "",
    interaction_mode: str = "guide",
    prior_assessment: dict | None = None,
) -> dict:
    """
    Single LLM call: section status, readiness, prioritized questions, and guide reply.

    interaction_mode: guide | readiness_advice | detailed_template | full_review
    """
    if not content or not content.strip():
        raise ValueError("Content is empty. Please provide case study content before assessing.")

    from src.guide_policy import apply_guide_policy, completeness_context

    system_prompt = load_prompt("guidance_assessment_prompt.md")
    client, model = get_llm_client()

    user_parts = [
        f"INTERACTION_MODE: {interaction_mode}",
        completeness_context(content, prior_assessment),
        f"ACCUMULATED_CASE_STUDY_CONTENT:\n{content.strip()}",
    ]
    if latest_message.strip():
        user_parts.append(f"LATEST_USER_MESSAGE:\n{latest_message.strip()}")

    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        temperature=0.25,
    )

    raw = response.choices[0].message.content or ""
    result = parse_json_response(raw)

    missing_keys = REQUIRED_KEYS - set(result.keys())
    if missing_keys:
        raise ValueError(f"LLM assessment response is missing keys: {missing_keys}")

    result = _normalize_assessment(result, content)
    return apply_guide_policy(
        result,
        content,
        interaction_mode=interaction_mode,
        prior_assessment=prior_assessment,
    )


def review_case_study_content(content: str) -> dict:
    """Backward-compatible review — uses full_review assessment mode."""
    return assess_case_study_content(content, interaction_mode="full_review")
