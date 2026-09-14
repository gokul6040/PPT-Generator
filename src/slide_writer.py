"""Convert structured case-study prose into concise slide headlines and bullets."""
import json
import re

from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

REQUIRED_HEADINGS = {"Problem Statement", "Design and Implementation", "Impact"}
HEADING_ORDER = ("Problem Statement", "Design and Implementation", "Impact")
VALID_BLOCK_TYPES = {"paragraph", "subheading", "bullet"}

_BULLET_LINE_RE = re.compile(r"^\s*[•\-–*]\s+(.+?)\s*$")
_BOLD_HEADING_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?[\s\u00a0]*$")


def _clean_block_text(value: object, block_type: str) -> str:
    text = str(value or "").strip()
    if block_type == "bullet":
        text = text.lstrip("•-– ").strip()
    elif block_type == "subheading":
        if text.startswith("**") and text.endswith("**") and len(text) > 4:
            text = text[2:-2].strip()
        text = text.rstrip(":").strip()
    return text


def _clean_headline(value: object) -> str:
    """Normalize a model headline without changing its wording."""
    return str(value or "").strip()


def _clean_point(value: object) -> dict | None:
    """Normalize a model-produced label-and-description point."""
    if not isinstance(value, dict):
        return None
    label = str(value.get("label") or value.get("heading") or "").strip()
    description = str(value.get("description") or value.get("text") or "").strip()
    label = label.rstrip(":.").strip()
    description = description.lstrip("•-– ").strip()
    if not description:
        return None
    return {"label": label, "description": description}


def source_content_to_blocks(content: str) -> list[dict]:
    """Parse website-style prose, bold subsection headings, and bullets in order."""
    blocks: list[dict] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines if line.strip()).strip()
        paragraph_lines.clear()
        if text:
            blocks.append({"type": "paragraph", "text": text})

    for raw_line in str(content or "").splitlines():
        line = raw_line.replace("\u00a0", " ").strip()
        if not line:
            flush_paragraph()
            continue

        heading_match = _BOLD_HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            heading = heading_match.group(1).strip().rstrip(":").strip()
            if heading:
                blocks.append({"type": "subheading", "text": heading})
            continue

        bullet_match = _BULLET_LINE_RE.match(line)
        if bullet_match:
            flush_paragraph()
            bullet = bullet_match.group(1).strip()
            if bullet:
                blocks.append({"type": "bullet", "text": bullet})
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    return blocks


def _fallback_points_from_source(content: str) -> list[dict]:
    """Keep source-grounded content visible if the point-writing model omits it."""
    points: list[dict] = []
    for block in source_content_to_blocks(content):
        text = _clean_block_text(block.get("text"), block.get("type", "paragraph"))
        if not text:
            continue
        if ":" in text:
            label, description = text.split(":", 1)
            label, description = label.strip(), description.strip()
            if label and description and len(label) <= 70:
                points.append({"label": label, "description": description})
                continue
        points.append({"label": "", "description": text})
    return points


def _fallback_bullets_from_source(content: str) -> list[str]:
    """Preserve source detail when the slide-writing model omits a section."""
    bullets: list[str] = []
    for block in source_content_to_blocks(content):
        block_type = str(block.get("type") or "").strip().lower()
        if block_type not in VALID_BLOCK_TYPES:
            continue
        text = _clean_block_text(block.get("text"), block_type)
        if text:
            bullets.append(text)

    if bullets:
        return bullets

    text = str(content or "").strip()
    return [text] if text else []


def _has_explicit_website_structure(content: str) -> bool:
    text = str(content or "")
    has_bullet = any(_BULLET_LINE_RE.match(line) for line in text.splitlines())
    has_subheading = any(_BOLD_HEADING_RE.match(line) for line in text.splitlines())
    has_paragraph = bool(re.search(r"(?m)^\s*[^\s•\-–*#].{30,}$", text))
    return has_bullet and (has_subheading or has_paragraph)


def _normalize_blocks(result: dict, structured_content: dict) -> dict:
    """Validate ordered content blocks and preserve the source title/empty sections."""
    input_sections = {
        str(section.get("heading") or "").strip(): section
        for section in structured_content.get("sections", [])
    }
    sections_out: list[dict] = []

    for heading in HEADING_ORDER:
        matched = next(
            (
                section
                for section in result.get("sections", [])
                if str(section.get("heading") or "").strip() == heading
            ),
            None,
        )
        blocks: list[dict] = []
        raw_blocks = matched.get("blocks") if isinstance(matched, dict) else None
        if isinstance(raw_blocks, list):
            for raw_block in raw_blocks:
                if isinstance(raw_block, str):
                    block_type = "bullet"
                    text = _clean_block_text(raw_block, block_type)
                elif isinstance(raw_block, dict):
                    block_type = str(raw_block.get("type") or "").strip().lower()
                    if block_type not in VALID_BLOCK_TYPES:
                        continue
                    text = _clean_block_text(raw_block.get("text"), block_type)
                else:
                    continue
                if text:
                    blocks.append({"type": block_type, "text": text})

        # Recover safely if an older model response still returns flat bullets.
        if not blocks and isinstance(matched, dict):
            for bullet in matched.get("bullets") or []:
                text = _clean_block_text(bullet, "bullet")
                if text:
                    blocks.append({"type": "bullet", "text": text})

        source_content = str(input_sections.get(heading, {}).get("content") or "").strip()
        if not source_content:
            blocks = []
        elif not blocks:
            # A missing model section must not become a heading-only slide.
            blocks = source_content_to_blocks(source_content)
        sections_out.append({"heading": heading, "blocks": blocks})

    return {
        "title": str(structured_content.get("title") or ""),
        "sections": sections_out,
    }


def _normalize_bullets(result: dict, structured_content: dict) -> dict:
    """Validate the compact label-and-description point contract."""
    input_sections = {
        str(section.get("heading") or "").strip(): section
        for section in structured_content.get("sections", [])
    }
    sections_out: list[dict] = []
    for heading in HEADING_ORDER:
        matched = next(
            (
                section
                for section in result.get("sections", [])
                if str(section.get("heading") or "").strip() == heading
            ),
            None,
        )
        points: list[dict] = []
        if isinstance(matched, dict):
            for raw_point in matched.get("points") or []:
                point = _clean_point(raw_point)
                if point:
                    points.append(point)

            # Support older cached/model responses during the transition.
            if not points:
                for bullet in matched.get("bullets") or []:
                    text = str(bullet).lstrip("•-– ").strip()
                    if text:
                        points.append({"label": "", "description": text})
        source_content = str(input_sections.get(heading, {}).get("content") or "").strip()
        if not source_content:
            points = []
        elif not points:
            points = _fallback_points_from_source(source_content)
        sections_out.append({"heading": heading, "points": points})
    return {
        "title": str(structured_content.get("title") or ""),
        "sections": sections_out,
    }


def write_slide_content(
    structured_content: dict,
    tone: str = "professional",
    audience: str = "leadership",
) -> dict:
    """Convert every non-empty section through the slide-writer prompt."""
    all_empty = all(
        not str(section.get("content") or "").strip()
        for section in structured_content.get("sections", [])
    )
    if all_empty:
        return {
            "title": structured_content.get("title", ""),
            "sections": [
                {"heading": heading, "points": []}
                for heading in HEADING_ORDER
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
        temperature=0.1,
    )
    result = parse_json_response(response.choices[0].message.content or "")
    if "sections" not in result:
        raise ValueError("Slide writer LLM response missing 'sections' key.")
    return _normalize_bullets(result, structured_content)


def write_slide_bullets(
    structured_content: dict,
    tone: str = "professional",
    audience: str = "leadership",
) -> dict:
    """Backward-compatible entry point for headline-and-bullet slide content."""
    return write_slide_content(structured_content, tone, audience)


def section_to_content_blocks(section: dict) -> list[dict]:
    """Convert points into bold-label bullet lines for the PPT renderer."""
    if "blocks" in section:
        return list(section.get("blocks") or [])

    blocks: list[dict] = []
    if "points" in section:
        for raw_point in section.get("points") or []:
            point = _clean_point(raw_point)
            if not point:
                continue
            label = point["label"]
            description = point["description"]
            text = f"**{label}:** {description}" if label else description
            blocks.append({"type": "bullet", "text": text})
        return blocks

    # Backward compatibility for saved sessions created before point-based output.
    headline = _clean_headline(section.get("headline"))
    if headline:
        blocks.append({"type": "subheading", "text": headline})
    for bullet in section.get("bullets") or []:
        text = _clean_block_text(bullet, "bullet")
        if text:
            blocks.append({"type": "bullet", "text": text})
    return blocks


def bullets_to_body_text(section_bullets: list[str]) -> str:
    """Format a legacy bullet list as newline-separated display text."""
    return "\n".join(f"• {b.strip()}" for b in section_bullets if b.strip())


def content_blocks_to_body_text(blocks: list[dict]) -> str:
    """Format ordered content blocks for the PowerPoint body renderer."""
    lines: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        if block_type not in VALID_BLOCK_TYPES:
            continue
        text = _clean_block_text(block.get("text"), block_type)
        if not text:
            continue
        if block_type == "bullet":
            lines.append(f"• {text}")
        elif block_type == "subheading":
            lines.append(f"**{text}**")
        else:
            lines.append(text)
    return "\n".join(lines)
