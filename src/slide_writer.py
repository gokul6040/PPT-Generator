"""Convert structured case study prose into concise slide bullets via LLM."""
import json

from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

REQUIRED_HEADINGS = {"Problem Statement", "Design and Implementation", "Impact"}


def _normalize_bullets(result: dict, structured_content: dict) -> dict:
    """Validate and clean the LLM bullet response."""
    # Preserve the original title — never let the LLM invent one
    result["title"] = str(structured_content.get("title") or "").strip()

    sections_out = []
    input_sections = {
        s["heading"]: s for s in structured_content.get("sections", [])
    }

    # Enforce required heading order
    for heading in ("Problem Statement", "Design and Implementation", "Impact"):
        matched = None
        for sec in result.get("sections", []):
            if str(sec.get("heading", "")).strip() == heading:
                matched = sec
                break

        bullets = list(matched.get("bullets") or []) if matched else []

        # Clean each bullet — strip whitespace and bullet chars the LLM might add
        bullets = [
            b.lstrip("•-– ").strip()
            for b in bullets
            if str(b).strip().lstrip("•-– ").strip()
        ]

        # If the LLM returned bullets for an empty source section, discard them
        src_content = str(input_sections.get(heading, {}).get("content") or "").strip()
        if not src_content:
            bullets = []

        sections_out.append({"heading": heading, "bullets": bullets})

    result["sections"] = sections_out
    return result


def write_slide_bullets(
    structured_content: dict,
    tone: str = "professional",
    audience: str = "leadership",
) -> dict:
    """
    Convert structured prose sections into concise slide bullet lists.

    Input: structured_content dict from content_structurer
    Output: {title, sections: [{heading, bullets: [str, ...]}, ...]}
    """
    # If all sections are empty, return empty bullets immediately (no LLM call)
    all_empty = all(
        not str(s.get("content") or "").strip()
        for s in structured_content.get("sections", [])
    )
    if all_empty:
        return {
            "title": structured_content.get("title", ""),
            "sections": [
                {"heading": h, "bullets": []}
                for h in ("Problem Statement", "Design and Implementation", "Impact")
            ],
        }

    system_prompt = load_prompt("slide_writer_prompt.md")
    client, model = get_llm_client()

    user_message = (
        f"Tone: {tone}\n"
        f"Audience: {audience}\n\n"
        f"Structured content:\n{json.dumps(structured_content, indent=2, ensure_ascii=False)}"
    )

    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.15,
    )

    raw = response.choices[0].message.content or ""
    result = parse_json_response(raw)

    if "sections" not in result:
        raise ValueError("Slide writer LLM response missing 'sections' key.")

    return _normalize_bullets(result, structured_content)


def bullets_to_body_text(section_bullets: list[str]) -> str:
    """
    Format a bullet list as newline-separated lines with • prefix.
    Used by ppt_generator when rendering bullet slides.
    """
    return "\n".join(f"• {b.strip()}" for b in section_bullets if b.strip())
