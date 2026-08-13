"""Title helpers — explicit detection, merge, and PPT banner placeholder."""
import re

# Shown on the grey title banner when the user generates without providing a title
PPT_TITLE_PLACEHOLDER = "[Title]"

# Thematic block labels: "Fragmented Data: Yacht data was..."
_LABEL_LINE_RE = re.compile(r"^[A-Za-z0-9][^:\n]{0,120}:\s+\S")
_TITLE_PREFIX_RE = re.compile(
    r"(?i)^(?:title|case\s+study\s+title|headline)\s*:\s*(.+)$"
)
_SECTION_OPENER_RE = re.compile(
    r"(?i)^(problem\s+statement|design\s+(and\s+)?implementation|impact)(\s|:|\b)"
    r"|^client\s*:"
    r"|^before\s+turnb\b"
)


def _looks_like_standalone_title(line: str) -> bool:
    """Short deck heading on its own line — not a section opener or narrative."""
    text = (line or "").strip()
    if not text or _LABEL_LINE_RE.match(text) or _SECTION_OPENER_RE.match(text):
        return False
    if ":" in text:
        return False
    words = text.split()
    if not words or len(words) > 15 or len(text) > 200:
        return False
    if text.endswith(".") and len(words) > 8:
        return False
    return True


def extract_explicit_title(content: str) -> str:
    """
    Return a deck title when the user provided one (prefix line or standalone first line).
  Used as a generation fallback when review state has no detected title.
    """
    lines = [ln.strip() for ln in (content or "").strip().splitlines() if ln.strip()]
    if not lines:
        return ""

    for line in lines:
        prefixed = _TITLE_PREFIX_RE.match(line)
        if prefixed:
            return prefixed.group(1).strip()

    first = lines[0]
    if _looks_like_standalone_title(first):
        return first

    return ""


def has_explicit_title(content: str) -> bool:
    return bool(extract_explicit_title(content))


def parse_title_message(message: str) -> str | None:
    """Return title text when the user message is Title:/Case Study Title:/Headline:."""
    match = _TITLE_PREFIX_RE.match((message or "").strip())
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def resolve_ppt_banner_title(title: str | None) -> tuple[str, bool]:
    """
    Return (banner_text, used_placeholder).
    Never returns empty — missing user title → PPT_TITLE_PLACEHOLDER.
    """
    text = (title or "").strip()
    if text:
        return text, False
    return PPT_TITLE_PLACEHOLDER, True


def merge_title_into_content(content: str, title: str) -> str:
    """Insert or replace a Title: line at the top of case study content."""
    title = (title or "").strip()
    if not title:
        return (content or "").strip()

    title_line = f"Title: {title}"
    body = (content or "").strip()
    if not body:
        return title_line

    lines = body.splitlines()
    for i, line in enumerate(lines):
        if _TITLE_PREFIX_RE.match(line.strip()):
            lines[i] = title_line
            return "\n".join(lines).strip()

    return f"{title_line}\n\n{body}"
