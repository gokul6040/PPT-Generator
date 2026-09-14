"""
Decide how many slides to create and which layout each slide uses.

Takes slide content (from slide_writer) + template_profile (from template_analyzer)
+ user's layout_preference and returns a layout_plan dict. Headline-and-bullet
sections are converted to ordered render blocks before fitting.

Layout plan format:
{
    "preference": str,
    "total_slides": int,
    "slides": [
        {"type": "single",       "heading": str, "bullets": [str, ...]},
        {"type": "continuation", "heading": str, "bullets": [str, ...]},
        {"type": "single",       "heading": str, "blocks": [dict, ...]},
        {"type": "two_section",  "sections": [
            {"heading": str, "bullets": [str, ...]},
            {"heading": str, "bullets": [str, ...]},
        ]},
    ]
}
"""
from src.slide_fit import (
    blocks_fit,
    bullets_fit,
    is_orphan_block_chunk,
    is_orphan_chunk,
    pack_blocks,
    pack_bullets,
)
from src.slide_writer import section_to_content_blocks

# ── Helpers ──────────────────────────────────────────────────────────────────

_WEBSITE_DISPLAY_HEADINGS = {
    "Design and Implementation": "TurnB Approach",
    "Impact": "Implications",
}

def _base_heading(heading: str) -> str:
    return heading.replace(" Continued", "").strip()


def _make_single(heading: str, bullets: list[str]) -> dict:
    return {"type": "single", "heading": heading, "bullets": list(bullets)}


def _make_continuation(heading: str, bullets: list[str]) -> dict:
    return {"type": "continuation", "heading": f"{heading} Continued", "bullets": list(bullets)}


def _make_two_section(sec_a: dict, sec_b: dict) -> dict:
    return {
        "type": "two_section",
        "sections": [
            {"heading": sec_a["heading"], "bullets": list(sec_a.get("bullets") or [])},
            {"heading": sec_b["heading"], "bullets": list(sec_b.get("bullets") or [])},
        ],
    }


def _make_block_single(heading: str, blocks: list[dict]) -> dict:
    return {
        "type": "single",
        "heading": _WEBSITE_DISPLAY_HEADINGS.get(heading, heading),
        "blocks": list(blocks),
    }


def _make_block_continuation(heading: str, blocks: list[dict]) -> dict:
    display_heading = _WEBSITE_DISPLAY_HEADINGS.get(heading, heading)
    return {
        "type": "continuation",
        "heading": f"{display_heading} Continued",
        "blocks": list(blocks),
    }


def _make_block_two_section(sec_a: dict, sec_b: dict) -> dict:
    return {
        "type": "two_section",
        "sections": [
            {
                "heading": _WEBSITE_DISPLAY_HEADINGS.get(sec_a["heading"], sec_a["heading"]),
                "blocks": list(sec_a.get("blocks") or []),
            },
            {
                "heading": _WEBSITE_DISPLAY_HEADINGS.get(sec_b["heading"], sec_b["heading"]),
                "blocks": list(sec_b.get("blocks") or []),
            },
        ],
    }


def _truncate_to_fit(bullets: list[str], *, half: bool = False) -> list[str]:
    """Keep as many leading bullets as fit on one slide (height-based)."""
    if not bullets:
        return []
    chunks = pack_bullets(bullets, half=half)
    return chunks[0] if chunks else []


def _split_section(heading: str, bullets: list[str], *, half: bool = False) -> list[dict]:
    """Split one section using measured text height — not fixed bullet caps."""
    if not bullets:
        return [_make_single(heading, [])]
    if bullets_fit(bullets, half=half):
        return [_make_single(heading, bullets)]

    chunks = pack_bullets(bullets, half=half)
    slides: list[dict] = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            slides.append(_make_single(heading, chunk))
        else:
            slides.append(_make_continuation(heading, chunk))
    return slides


def _truncate_blocks_to_fit(blocks: list[dict], *, half: bool = False) -> list[dict]:
    if not blocks:
        return []
    chunks = pack_blocks(blocks, half=half)
    return chunks[0] if chunks else []


def _split_block_section(heading: str, blocks: list[dict]) -> list[dict]:
    """Split an ordered section while keeping subsection headings with content."""
    if not blocks:
        return [_make_block_single(heading, [])]
    chunks = pack_blocks(blocks)
    return [
        _make_block_single(heading, chunk)
        if index == 0
        else _make_block_continuation(heading, chunk)
        for index, chunk in enumerate(chunks)
    ]


def _prevent_orphan_continuations(slides: list[dict]) -> list[dict]:
    """
    If a continuation slide is mostly empty (1–3 short bullets), merge or shift
    bullets back onto the previous slide when height allows.
    """
    if len(slides) < 2:
        return slides

    merged: list[dict] = []
    for slide in slides:
        if slide.get("type") != "continuation" or not merged:
            merged.append(slide)
            continue

        bullets = slide.get("bullets") or []
        if not is_orphan_chunk(bullets):
            merged.append(slide)
            continue

        prev = merged[-1]
        if _base_heading(prev.get("heading", "")) != _base_heading(slide.get("heading", "")):
            merged.append(slide)
            continue

        combined = (prev.get("bullets") or []) + bullets
        if bullets_fit(combined):
            merged[-1] = _make_single(_base_heading(prev.get("heading", "")), combined)
            continue

        prev_bullets = list(prev.get("bullets") or [])
        orphan_bullets = list(bullets)
        while orphan_bullets and bullets_fit(prev_bullets + [orphan_bullets[0]]):
            prev_bullets.append(orphan_bullets.pop(0))

        merged[-1] = _make_single(_base_heading(prev.get("heading", "")), prev_bullets)
        if orphan_bullets:
            merged.append(_make_continuation(_base_heading(slide.get("heading", "")), orphan_bullets))

    return merged


def _prevent_orphan_block_continuations(slides: list[dict]) -> list[dict]:
    """Merge light block continuations when the combined content still fits."""
    if len(slides) < 2:
        return slides
    merged: list[dict] = []
    for slide in slides:
        if slide.get("type") != "continuation" or not merged:
            merged.append(slide)
            continue
        blocks = slide.get("blocks") or []
        previous = merged[-1]
        same_section = _base_heading(previous.get("heading", "")) == _base_heading(
            slide.get("heading", "")
        )
        combined = (previous.get("blocks") or []) + blocks
        if same_section and is_orphan_block_chunk(blocks) and blocks_fit(combined):
            merged[-1] = _make_block_single(
                _base_heading(previous.get("heading", "")), combined
            )
        else:
            merged.append(slide)
    return merged


# ── Per-preference planners ───────────────────────────────────────────────────

def _plan_exact_3(sections: list[dict]) -> list[dict]:
    """Always produce exactly 3 single-section slides. Truncate to fit if needed."""
    return [
        _make_single(s["heading"], _truncate_to_fit(s.get("bullets") or []))
        for s in sections
    ]


def _plan_compact(sections: list[dict]) -> list[dict]:
    """
    Problem + Design on slide 1 if they fit; Impact on slide 2.
    Falls back to one_section_per_slide if content is too large.
    """
    if len(sections) < 3:
        return _plan_one_section(sections)

    problem, design, impact = sections[0], sections[1], sections[2]
    pb = problem.get("bullets") or []
    db = design.get("bullets") or []

    if bullets_fit(pb, half=True, which_half="top") and bullets_fit(
        db, half=True, which_half="bottom"
    ):
        return [
            _make_two_section(
                {"heading": problem["heading"], "bullets": pb},
                {"heading": design["heading"], "bullets": db},
            ),
            _make_single(impact["heading"], impact.get("bullets") or []),
        ]
    return _plan_one_section(sections)


def _plan_split_if_needed(sections: list[dict]) -> list[dict]:
    """Continuation slides only when measured body height is exceeded."""
    slides: list[dict] = []
    for sec in sections:
        slides.extend(_split_section(sec["heading"], sec.get("bullets") or []))
    return slides


def _plan_one_section(sections: list[dict]) -> list[dict]:
    """One section per slide; continuation only when the next bullet will not fit."""
    slides: list[dict] = []
    for sec in sections:
        slides.extend(_split_section(sec["heading"], sec.get("bullets") or []))
    return slides


def _plan_auto(sections: list[dict]) -> list[dict]:
    """
    Small total content → compact (2 slides) when both halves fit.
    Otherwise one section per slide with height-based continuation only.
    """
    total = sum(len(s.get("bullets") or []) for s in sections)
    if total <= 8:
        compact = _plan_compact(sections)
        if len(compact) == 2 and compact[0].get("type") == "two_section":
            return compact
    return _plan_one_section(sections)


# ── Ordered content-block planners ──────────────────────────────────────────

def _plan_blocks_exact_3(sections: list[dict]) -> list[dict]:
    """Honor an explicit three-slide request, retaining as much as safely fits."""
    return [
        _make_block_single(
            section["heading"], _truncate_blocks_to_fit(section.get("blocks") or [])
        )
        for section in sections
    ]


def _plan_blocks_compact(sections: list[dict]) -> list[dict]:
    if len(sections) < 3:
        return _plan_blocks_one_section(sections)
    problem, design, impact = sections[0], sections[1], sections[2]
    problem_blocks = problem.get("blocks") or []
    design_blocks = design.get("blocks") or []
    if (
        blocks_fit(problem_blocks, half=True, which_half="top")
        and blocks_fit(design_blocks, half=True, which_half="bottom")
        and blocks_fit(impact.get("blocks") or [])
    ):
        return [
            _make_block_two_section(problem, design),
            _make_block_single(impact["heading"], impact.get("blocks") or []),
        ]
    return _plan_blocks_one_section(sections)


def _plan_blocks_one_section(sections: list[dict]) -> list[dict]:
    slides: list[dict] = []
    for section in sections:
        slides.extend(
            _split_block_section(section["heading"], section.get("blocks") or [])
        )
    return slides


def _plan_blocks_auto(sections: list[dict]) -> list[dict]:
    total_blocks = sum(len(section.get("blocks") or []) for section in sections)
    if total_blocks <= 8:
        compact = _plan_blocks_compact(sections)
        if len(compact) == 2 and compact[0].get("type") == "two_section":
            return compact
    return _plan_blocks_one_section(sections)


# ── Main entry point ─────────────────────────────────────────────────────────

def plan_layout(
    slide_bullets: dict,
    template_profile: dict,
    layout_preference: str = "auto",
) -> dict:
    """
    Build a layout plan from slide_bullets and user preference.

    slide_bullets: output of slide_writer.write_slide_bullets
    template_profile: output of template_analyzer.analyze_template
    layout_preference: "auto" | "exact_3_slides" | "compact" | "split_if_needed" | "one_section_per_slide"
    """
    sections = slide_bullets.get("sections", [])

    if any(
        "blocks" in section or "headline" in section or "points" in section
        for section in sections
    ):
        block_sections = [
            {
                "heading": section.get("heading", ""),
                "blocks": section_to_content_blocks(section),
            }
            for section in sections
        ]
        block_planners = {
            "exact_3_slides": _plan_blocks_exact_3,
            "compact": _plan_blocks_compact,
            "split_if_needed": _plan_blocks_one_section,
            "one_section_per_slide": _plan_blocks_one_section,
        }
        block_planner = block_planners.get(layout_preference, _plan_blocks_auto)
        slides = _prevent_orphan_block_continuations(block_planner(block_sections))
        return {
            "preference": layout_preference,
            "total_slides": len(slides),
            "slides": slides,
        }

    planners = {
        "exact_3_slides": _plan_exact_3,
        "compact": _plan_compact,
        "split_if_needed": _plan_split_if_needed,
        "one_section_per_slide": _plan_one_section,
    }

    planner = planners.get(layout_preference, _plan_auto)
    slides = _prevent_orphan_continuations(planner(sections))

    return {
        "preference": layout_preference,
        "total_slides": len(slides),
        "slides": slides,
    }
