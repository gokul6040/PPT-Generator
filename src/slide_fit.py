"""
Height-based bullet packing for slide layout.

Estimates wrapped lines per bullet from box width, font size, and paragraph spacing.
Splits only when the next bullet would exceed the body safe area — not by fixed bullet count.
"""
from src.config import (
    BODY_FONT_SIZE,
    BODY_H,
    BODY_W,
    BODY_PARAGRAPH_SPACE_AFTER,
    MIN_BODY_FONT_SIZE,
    TWO_SEC_BOT_BODY_H,
    TWO_SEC_BOT_BODY_W,
    TWO_SEC_TOP_BODY_H,
    TWO_SEC_TOP_BODY_W,
)

LINE_SPACING = 1.2
CHAR_WIDTH_FACTOR = 0.52  # Segoe UI average glyph width vs point size
HEIGHT_FILL_RATIO = 0.92  # leave a small margin inside the text box
ORPHAN_HEIGHT_RATIO = 0.38  # continuation chunk below this → try merge / rebalance
ORPHAN_MAX_BULLETS = 3

_READABLE_FONT_STEPS = (
    BODY_FONT_SIZE.pt,
    10.0,
    MIN_BODY_FONT_SIZE.pt,
)


def _body_box(*, half: bool, which_half: str = "top") -> tuple[float, float]:
    if not half:
        return BODY_W.inches, BODY_H.inches
    if which_half == "top":
        return TWO_SEC_TOP_BODY_W.inches, TWO_SEC_TOP_BODY_H.inches
    return TWO_SEC_BOT_BODY_W.inches, TWO_SEC_BOT_BODY_H.inches


def chars_per_line(width_in: float, font_pt: float) -> int:
    char_w = (font_pt / 72.0) * CHAR_WIDTH_FACTOR
    return max(40, int(width_in / char_w))


def line_height_in(font_pt: float) -> float:
    return (font_pt * LINE_SPACING) / 72.0


def bullet_display_text(bullet: str) -> str:
    return f"• {bullet.strip()}"


def wrapped_lines_for_bullet(bullet: str, width_in: float, font_pt: float) -> int:
    text = bullet_display_text(bullet)
    cpl = chars_per_line(width_in, font_pt)
    return max(1, (len(text) + cpl - 1) // cpl)


def estimate_bullets_height(
    bullets: list[str],
    *,
    half: bool = False,
    which_half: str = "top",
    font_pt: float | None = None,
) -> float:
    if not bullets:
        return 0.0
    pt = font_pt or BODY_FONT_SIZE.pt
    width_in, _ = _body_box(half=half, which_half=which_half)
    lh = line_height_in(pt)
    gap = BODY_PARAGRAPH_SPACE_AFTER.pt / 72.0
    total = 0.0
    for i, bullet in enumerate(bullets):
        total += wrapped_lines_for_bullet(bullet, width_in, pt) * lh
        if i < len(bullets) - 1:
            total += gap
    return total


def max_body_height(
    *,
    half: bool = False,
    which_half: str = "top",
    font_pt: float | None = None,
) -> float:
    pt = font_pt or BODY_FONT_SIZE.pt
    _, height_in = _body_box(half=half, which_half=which_half)
    return height_in * HEIGHT_FILL_RATIO


def _fits_at_font(
    bullets: list[str],
    *,
    half: bool,
    which_half: str,
    font_pt: float,
) -> bool:
    return estimate_bullets_height(
        bullets, half=half, which_half=which_half, font_pt=font_pt
    ) <= max_body_height(half=half, which_half=which_half, font_pt=font_pt)


def bullets_fit(
    bullets: list[str],
    *,
    half: bool = False,
    which_half: str = "top",
) -> bool:
    """True when bullets fit at 12pt, or at a readable downstep (10pt / 9pt min)."""
    if not bullets:
        return True
    return any(_fits_at_font(bullets, half=half, which_half=which_half, font_pt=pt) for pt in _READABLE_FONT_STEPS)


def estimate_bullet_lines(bullets: list[str], *, half: bool = False, which_half: str = "top") -> int:
    width_in, _ = _body_box(half=half, which_half=which_half)
    pt = BODY_FONT_SIZE.pt
    return sum(wrapped_lines_for_bullet(b, width_in, pt) for b in bullets)


def pack_bullets(
    bullets: list[str],
    *,
    half: bool = False,
    which_half: str = "top",
) -> list[list[str]]:
    """
    Pack bullets into slide chunks.
    Adds the next bullet only while the slide still fits; otherwise starts a continuation.
    """
    if not bullets:
        return [[]]
    if bullets_fit(bullets, half=half, which_half=which_half):
        return [list(bullets)]

    chunks: list[list[str]] = []
    current: list[str] = []

    for bullet in bullets:
        candidate = current + [bullet]
        if current and not bullets_fit(candidate, half=half, which_half=which_half):
            chunks.append(current)
            current = [bullet]
        else:
            current = candidate

    if current:
        chunks.append(current)

    return rebalance_chunks(chunks, half=half, which_half=which_half)


def is_orphan_chunk(bullets: list[str], *, half: bool = False, which_half: str = "top") -> bool:
    if not bullets:
        return True
    if len(bullets) > ORPHAN_MAX_BULLETS:
        return False
    max_h = max_body_height(half=half, which_half=which_half)
    return estimate_bullets_height(bullets, half=half, which_half=which_half) < ORPHAN_HEIGHT_RATIO * max_h


def rebalance_chunks(
    chunks: list[list[str]],
    *,
    half: bool = False,
    which_half: str = "top",
) -> list[list[str]]:
    """Merge or shift bullets so continuation slides are not mostly empty."""
    if len(chunks) < 2:
        return [list(c) for c in chunks]

    out = [list(c) for c in chunks]
    changed = True
    while changed and len(out) >= 2:
        changed = False
        last = out[-1]
        if not is_orphan_chunk(last, half=half, which_half=which_half):
            break

        combined = out[-2] + last
        if bullets_fit(combined, half=half, which_half=which_half):
            out = out[:-2] + [combined]
            changed = True
            continue

        while last and bullets_fit(out[-2] + [last[0]], half=half, which_half=which_half):
            out[-2].append(last.pop(0))
            changed = True
        if not last:
            out.pop()
            changed = True

    if len(out) >= 2:
        out = _balance_pair(out[-2], out[-1], half=half, which_half=which_half, prefix=out[:-2])

    return out


def _balance_pair(
    prev: list[str],
    last: list[str],
    *,
    half: bool,
    which_half: str,
    prefix: list[list[str]],
) -> list[list[str]]:
    """Move bullets from the fuller slide to the lighter continuation when it improves balance."""
    out = prefix + [list(prev), list(last)]
    max_h = max_body_height(half=half, which_half=which_half)

    while len(out) >= 2:
        a, b = out[-2], out[-1]
        ha = estimate_bullets_height(a, half=half, which_half=which_half)
        hb = estimate_bullets_height(b, half=half, which_half=which_half)
        if hb >= ORPHAN_HEIGHT_RATIO * max_h or ha <= hb:
            break
        if not a:
            break
        trial_a = a[:-1]
        trial_b = [a[-1]] + b
        if not trial_a:
            break
        if bullets_fit(trial_a, half=half, which_half=which_half) and bullets_fit(
            trial_b, half=half, which_half=which_half
        ):
            out[-2] = trial_a
            out[-1] = trial_b
        else:
            break

    return out


# ── Ordered case-study content blocks ───────────────────────────────────────

def block_display_text(block: dict) -> str:
    """Return the text that will be visible for one content block."""
    block_type = str(block.get("type") or "paragraph").strip().lower()
    text = str(block.get("text") or "").strip()
    if block_type == "bullet":
        return f"• {text}"
    return text


def wrapped_lines_for_block(block: dict, width_in: float, font_pt: float) -> int:
    text = block_display_text(block)
    cpl = chars_per_line(width_in, font_pt)
    return max(1, (len(text) + cpl - 1) // cpl)


def estimate_blocks_height(
    blocks: list[dict],
    *,
    half: bool = False,
    which_half: str = "top",
    font_pt: float | None = None,
) -> float:
    """Estimate the height of paragraphs, subsection headings, and bullets."""
    if not blocks:
        return 0.0
    pt = font_pt or BODY_FONT_SIZE.pt
    width_in, _ = _body_box(half=half, which_half=which_half)
    line_height = line_height_in(pt)
    regular_gap = BODY_PARAGRAPH_SPACE_AFTER.pt / 72.0
    total = 0.0
    for index, block in enumerate(blocks):
        total += wrapped_lines_for_block(block, width_in, pt) * line_height
        if index < len(blocks) - 1:
            # Subheadings stay visually attached to the supporting content below.
            total += regular_gap * (0.55 if block.get("type") == "subheading" else 1.0)
    return total


def blocks_fit(
    blocks: list[dict],
    *,
    half: bool = False,
    which_half: str = "top",
) -> bool:
    if not blocks:
        return True
    return any(
        estimate_blocks_height(
            blocks, half=half, which_half=which_half, font_pt=font_pt
        ) <= max_body_height(half=half, which_half=which_half, font_pt=font_pt)
        for font_pt in _READABLE_FONT_STEPS
    )


def _block_units(blocks: list[dict]) -> list[list[dict]]:
    """Group each subsection heading with at least its first supporting block."""
    units: list[list[dict]] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.get("type") == "subheading" and index + 1 < len(blocks):
            units.append([block, blocks[index + 1]])
            index += 2
        else:
            units.append([block])
            index += 1
    return units


def pack_blocks(
    blocks: list[dict],
    *,
    half: bool = False,
    which_half: str = "top",
) -> list[list[dict]]:
    """Pack ordered content without orphaning a subsection heading."""
    if not blocks:
        return [[]]
    if blocks_fit(blocks, half=half, which_half=which_half):
        return [list(blocks)]

    chunks: list[list[dict]] = []
    current: list[dict] = []
    for unit in _block_units(blocks):
        candidate = current + unit
        if current and not blocks_fit(candidate, half=half, which_half=which_half):
            chunks.append(current)
            current = list(unit)
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def is_orphan_block_chunk(
    blocks: list[dict],
    *,
    half: bool = False,
    which_half: str = "top",
) -> bool:
    if not blocks:
        return True
    max_height = max_body_height(half=half, which_half=which_half)
    return estimate_blocks_height(
        blocks, half=half, which_half=which_half
    ) < ORPHAN_HEIGHT_RATIO * max_height
