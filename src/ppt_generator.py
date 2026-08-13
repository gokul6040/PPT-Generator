"""Generate the PowerPoint from structured content and a template."""
import copy
import io
import re
from datetime import datetime

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from src.title_utils import resolve_ppt_banner_title
from src.config import (
    BLACK,
    BODY_FONT,
    BODY_FONT_SIZE,
    BODY_H,
    BODY_PARAGRAPH_SPACE_AFTER,
    BODY_W,
    BODY_X,
    BODY_Y,
    HEADING_FONT,
    HEADING_FONT_SIZE,
    HEADING_H,
    HEADING_W,
    HEADING_X,
    HEADING_Y,
    MAX_CHARS_PER_SLIDE,
    MIN_BODY_FONT_SIZE,
    QUOTE_FONT,
    TEAL_PRIMARY,
    TITLE_FONT,
    TITLE_BAR_H,
    TITLE_W,
    TITLE_X,
    TITLE_Y,
    TWO_SEC_BOT_BODY_H,
    TWO_SEC_BOT_BODY_W,
    TWO_SEC_BOT_BODY_X,
    TWO_SEC_BOT_BODY_Y,
    TWO_SEC_BOT_HEADING_H,
    TWO_SEC_BOT_HEADING_W,
    TWO_SEC_BOT_HEADING_X,
    TWO_SEC_BOT_HEADING_Y,
    TWO_SEC_TOP_BODY_H,
    TWO_SEC_TOP_BODY_W,
    TWO_SEC_TOP_BODY_X,
    TWO_SEC_TOP_BODY_Y,
    TWO_SEC_TOP_HEADING_H,
    TWO_SEC_TOP_HEADING_W,
    TWO_SEC_TOP_HEADING_X,
    TWO_SEC_TOP_HEADING_Y,
)
from src.slide_writer import bullets_to_body_text
from src.text_fitter import split_text_for_slides

_PML_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def generate_case_study_ppt_bytes(
    structured_content: dict,
    template_path: str,
    layout_plan: dict | None = None,
    title_override: str | None = None,
) -> tuple[bytes, str]:
    """
    Build a PPT in memory.
    Returns (pptx_bytes, suggested_filename).
    """
    prs = Presentation(template_path)
    clean_snapshot = _snapshot_clean_slide(prs.slides[0])

    slide_title, _ = resolve_ppt_banner_title(
        str(title_override or "").strip()
        or str(structured_content.get("title") or "").strip()
    )

    if layout_plan:
        slide_specs = layout_plan.get("slides", [])
    else:
        pairs = _build_slide_plan(structured_content.get("sections", []))
        slide_specs = [{"type": "single", "heading": h, "_body": b} for h, b in pairs]

    if not slide_specs:
        raise ValueError("No slide content to generate.")

    _write_slide_spec(prs.slides[0], slide_specs[0], title=slide_title)

    for spec in slide_specs[1:]:
        new_slide = _create_slide_from_snapshot(prs, clean_snapshot)
        _write_slide_spec(new_slide, spec, title=slide_title)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"turnb_case_study_{timestamp}.pptx"
    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue(), file_name


def _build_slide_plan(sections: list[dict]) -> list[tuple[str, str]]:
    """
    Build (heading, body) pairs with correct Continued labels.
    Accepts both prose format (content key) and bullet format (bullets key).
    """
    slides: list[tuple[str, str]] = []

    for section in sections:
        heading = section["heading"]

        # Bullet format takes priority over prose format
        if "bullets" in section:
            bullet_list = section.get("bullets") or []
            body = bullets_to_body_text(bullet_list)
        else:
            body = section.get("content", "").strip()

        if not body:
            slides.append((heading, ""))
            continue

        chunks = split_text_for_slides(body, MAX_CHARS_PER_SLIDE)
        for i, chunk in enumerate(chunks):
            h = heading if i == 0 else f"{heading} Continued"
            slides.append((h, chunk))

    return slides


def _snapshot_clean_slide(slide) -> dict:
    """Capture the template slide before any text is written."""
    sp_children = [copy.deepcopy(child) for child in slide.shapes._spTree]
    bg = slide._element.find(f".//{{{_PML_NS}}}bg")
    return {
        "sp_children": sp_children,
        "bg": copy.deepcopy(bg) if bg is not None else None,
        "layout": slide.slide_layout,
    }


def _create_slide_from_snapshot(prs: Presentation, snapshot: dict):
    """Create a new slide that mirrors the original clean template."""
    new_slide = prs.slides.add_slide(snapshot["layout"])
    sp_tree = new_slide.shapes._spTree

    for child in list(sp_tree):
        sp_tree.remove(child)

    for child in snapshot["sp_children"]:
        sp_tree.append(copy.deepcopy(child))

    if snapshot["bg"] is not None:
        sp_tree_elem = new_slide._element.find(f".//{{{_DML_NS}}}spTree")
        if sp_tree_elem is not None:
            sp_tree_elem.getparent().insert(0, copy.deepcopy(snapshot["bg"]))

    return new_slide


def _write_slide(slide, heading_text: str, body_text: str, title: str | None = None):
    """Overlay title, heading, and body text on the template slide."""
    if title:
        _add_title(slide, title)
    _add_heading(slide, heading_text)
    if body_text:
        _add_body(slide, body_text)


def _write_slide_spec(slide, spec: dict, title: str | None = None):
    """
    Dispatch to the correct writer based on spec type.

    spec types:
    - "single" / "continuation": single-section slide (heading + body)
    - "two_section": two stacked sections sharing one slide
    - legacy: spec with "_body" key (from old _build_slide_plan path)
    """
    spec_type = spec.get("type", "single")

    if spec_type == "two_section":
        _write_two_section_slide(slide, spec.get("sections", []), title=title)
        return

    # single / continuation / legacy
    if "_body" in spec:
        # Legacy path from old _build_slide_plan — body is already a formatted string
        body = spec["_body"]
    else:
        bullets = spec.get("bullets") or []
        body = bullets_to_body_text(bullets)

    heading = spec.get("heading", "")
    _write_slide(slide, heading, body, title=title)


def _write_two_section_slide(slide, sections: list[dict], title: str | None = None):
    """
    Render two sections stacked on one slide.
    Top half: first section. Bottom half: second section.
    """
    if title:
        _add_title(slide, title)

    if len(sections) >= 1:
        top = sections[0]
        _add_heading(
            slide, top.get("heading", ""),
            x=TWO_SEC_TOP_HEADING_X, y=TWO_SEC_TOP_HEADING_Y,
            w=TWO_SEC_TOP_HEADING_W, h=TWO_SEC_TOP_HEADING_H,
        )
        top_body = bullets_to_body_text(top.get("bullets") or [])
        if top_body:
            _add_body(
                slide, top_body,
                x=TWO_SEC_TOP_BODY_X, y=TWO_SEC_TOP_BODY_Y,
                w=TWO_SEC_TOP_BODY_W, h=TWO_SEC_TOP_BODY_H,
            )

    if len(sections) >= 2:
        bot = sections[1]
        _add_heading(
            slide, bot.get("heading", ""),
            x=TWO_SEC_BOT_HEADING_X, y=TWO_SEC_BOT_HEADING_Y,
            w=TWO_SEC_BOT_HEADING_W, h=TWO_SEC_BOT_HEADING_H,
        )
        bot_body = bullets_to_body_text(bot.get("bullets") or [])
        if bot_body:
            _add_body(
                slide, bot_body,
                x=TWO_SEC_BOT_BODY_X, y=TWO_SEC_BOT_BODY_Y,
                w=TWO_SEC_BOT_BODY_W, h=TWO_SEC_BOT_BODY_H,
            )


def _title_layout(text: str) -> int:
    """Font size for title — box height is fixed to the grey banner."""
    length = len(text)
    if length <= 38:
        return 24
    if length <= 55:
        return 20
    if length <= 75:
        return 18
    if length <= 100:
        return 16
    if length <= 130:
        return 14
    return 12


def _add_title(slide, text: str):
    """Case study title locked inside the grey banner — always left-aligned."""
    font_pt = _title_layout(text)
    txBox = slide.shapes.add_textbox(TITLE_X, TITLE_Y, TITLE_W, TITLE_BAR_H)
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_top = Pt(0)
    tf.margin_bottom = Pt(0)
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(2)

    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.LEFT
    para.line_spacing = 1.0
    run = para.add_run()
    run.text = text
    run.font.name = TITLE_FONT
    run.font.size = Pt(font_pt)
    run.font.bold = True
    run.font.color.rgb = BLACK


def _add_heading(slide, text: str, *, x=HEADING_X, y=HEADING_Y, w=HEADING_W, h=HEADING_H):
    """
    Section heading. First letter teal (#028482), remainder black. Segoe UI 14pt bold.
    Accepts optional x/y/w/h overrides for two-section slide positioning.
    """
    txBox = slide.shapes.add_textbox(x, y, w, h)
    tf = txBox.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]

    if not text:
        return

    first_char = text[0]
    rest = text[1:]

    run_first = para.add_run()
    run_first.text = first_char
    run_first.font.name = HEADING_FONT
    run_first.font.size = HEADING_FONT_SIZE
    run_first.font.bold = True
    run_first.font.color.rgb = TEAL_PRIMARY

    if rest:
        run_rest = para.add_run()
        run_rest.text = rest
        run_rest.font.name = HEADING_FONT
        run_rest.font.size = HEADING_FONT_SIZE
        run_rest.font.bold = True
        run_rest.font.color.rgb = BLACK


_LABEL_MAX_LEN = 70


def _clean_body_line(line: str) -> str:
    """Strip invisible chars sometimes pasted from Word/PDF."""
    return re.sub(r"[\u200b\ufeff]", "", line)


def _parse_label_prefix(line: str) -> tuple[str, str] | None:
    """
    Detect thematic sub-labels: 'Topic Name: explanation...'
    Returns (label_with_colon, rest) or None.
    Bullet-prefixed lines (•, -, –) are never parsed as labels.
    """
    stripped = line.strip()
    # Bullet lines — render as plain text, not as bold labels
    if stripped and stripped[0] in ("•", "-", "–"):
        return None
    if ":" not in stripped:
        return None

    idx = stripped.index(":")
    if idx < 2 or idx > _LABEL_MAX_LEN:
        return None

    label = stripped[:idx].strip()
    rest = stripped[idx + 1 :].lstrip()
    if not label or not rest:
        return None
    if not re.search(r"[A-Za-z]", label):
        return None
    if re.fullmatch(r"[\d:.]+", label):
        return None
    if label.lower().startswith("http"):
        return None

    return (label + ":", rest)


def _apply_run_style(run, *, bold: bool = False, italic: bool = False):
    run.font.name = QUOTE_FONT if italic else BODY_FONT
    run.font.size = BODY_FONT_SIZE
    run.font.color.rgb = BLACK
    run.font.bold = bold
    run.font.italic = italic
    if run.font.size < MIN_BODY_FONT_SIZE:
        run.font.size = MIN_BODY_FONT_SIZE


def _add_body_run(para, text: str, *, bold: bool = False, italic: bool = False):
    if not text:
        return
    run = para.add_run()
    run.text = text
    _apply_run_style(run, bold=bold, italic=italic)


def _add_body_with_inline_bold(para, text: str, *, italic: bool = False):
    """Render body text, honouring **bold** markers."""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            _add_body_run(para, part[2:-2], bold=True, italic=italic)
        else:
            _add_body_run(para, part, italic=italic)


def _add_body_line(para, line: str):
    line = _clean_body_line(line)

    if _is_quote_line(line):
        _add_body_run(para, line, italic=True)
        return

    parsed = _parse_label_prefix(line)
    if parsed:
        label, rest = parsed
        _add_body_run(para, label, bold=True)
        _add_body_with_inline_bold(para, " " + rest, italic=False)
        return

    _add_body_with_inline_bold(para, line)


def _add_body(slide, text: str, *, x=BODY_X, y=BODY_Y, w=BODY_W, h=BODY_H):
    """
    Body text area. Segoe UI 12pt black. Preserves paragraphs.
    Italic for quoted lines. Thematic labels before ':' are bold.
    **markdown** bold supported. Never shrinks below MIN_BODY_FONT_SIZE (9pt).
    Accepts optional x/y/w/h overrides for two-section slide positioning.
    """
    txBox = slide.shapes.add_textbox(x, y, w, h)
    tf = txBox.text_frame
    tf.word_wrap = True

    lines = [_clean_body_line(line) for line in text.split("\n")]
    lines = [line for line in lines if line.strip()]
    first = True

    for i, line in enumerate(lines):
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        _add_body_line(para, line)
        if i < len(lines) - 1:
            para.space_after = BODY_PARAGRAPH_SPACE_AFTER


def _is_quote_line(line: str) -> bool:
    """Detect user-provided quotes for italic styling."""
    stripped = line.strip()
    if len(stripped) >= 2 and stripped[0] in ('"', "'") and stripped[-1] == stripped[0]:
        return True
    if re.match(r'^".*"$', stripped) or re.match(r"^'.*'$", stripped):
        return True
    return False
