"""
Format guide messages from LLM assessment output.

The LLM owns: merge placement (via merge_prompt), assessment, guide replies,
and post-generate warnings. Python only extracts/displays.
"""
from src.utils import get_llm_client, llm_chat_completion, load_prompt


def guide_message_from_assessment(assessment: dict) -> str:
    """
    Return the LLM-authored guide message.
    Falls back to minimal assembly only if conversational_reply is empty.
    """
    reply = (assessment.get("conversational_reply") or "").strip()
    if reply:
        return reply
    return _minimal_fallback(assessment)


def generate_post_generate_warning(
    assessment: dict,
    *,
    case_content: str = "",
    title_missing: bool = False,
    blank_slide_sections: list[str] | None = None,
) -> str:
    """
    LLM-authored warning after PPT generation about thin/missing content.
    Falls back to template only if the LLM call fails or returns empty when gaps exist.
    """
    from src.readiness import build_post_generate_warning_template, render_short_status

    section_status = assessment.get("section_status") or {}
    has_gaps = (
        title_missing
        or assessment.get("title_status") == "missing"
        or any(v in ("missing", "weak") for v in section_status.values())
        or bool(blank_slide_sections)
        or assessment.get("readiness_level") in ("not_enough_to_generate", "enough_but_weak")
    )

    if not has_gaps and assessment.get("quality_label") == "strong":
        return ""

    try:
        system_prompt = load_prompt("agent_response_prompt.md")
        client, model = get_llm_client()

        lines = [
            "MODE: POST_GENERATE_WARNING",
            "The PowerPoint file was just generated from the accumulated case study content.",
            render_short_status(assessment),
            f"Readiness: {assessment.get('readiness_level', 'unknown')}",
            f"Quality: {assessment.get('quality_label', 'unknown')}",
            f"Enough to generate was: {assessment.get('enough_to_generate', False)}",
            f"Title missing on deck: {title_missing or assessment.get('title_status') == 'missing'}",
        ]

        if blank_slide_sections:
            lines.append(
                "Slides/areas left blank in the generated file: "
                + ", ".join(blank_slide_sections)
            )

        missing_weak = assessment.get("missing_weak") or []
        improvements = assessment.get("top_improvement_items") or []
        if missing_weak:
            lines.append("Assessment gaps:\n" + "\n".join(f"- {i}" for i in missing_weak[:6]))
        if improvements:
            lines.append(
                "Top improvements:\n" + "\n".join(f"- {i}" for i in improvements[:4])
            )

        if case_content.strip():
            snippet = case_content.strip()[:1200]
            if len(case_content) > 1200:
                snippet += "…"
            lines.append(f"Content used for generation:\n{snippet}")

        response = llm_chat_completion(
            client,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n\n".join(lines)},
            ],
            temperature=0.2,
        )

        reply = (response.choices[0].message.content or "").strip()
        if reply.lower() in ("", "none", "n/a", "no warning needed"):
            return "" if not has_gaps else build_post_generate_warning_template(
                assessment, title_missing=title_missing
            )
        return reply

    except Exception:
        return build_post_generate_warning_template(assessment, title_missing=title_missing)


def _minimal_fallback(assessment: dict) -> str:
    """Emergency fallback if LLM omitted conversational_reply."""
    from src.readiness import render_short_status

    ack = assessment.get("acknowledgement") or "Got it."
    status = render_short_status(assessment)
    questions = assessment.get("questions_to_user") or []
    parts = [ack, "", status]

    if questions:
        numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        parts.extend(["", "To complete the deck:", "", numbered])

    if assessment.get("enough_to_generate"):
        parts.extend(["", "Or say **generate anyway**."])

    return "\n".join(parts)
