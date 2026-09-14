"""Structure reviewed content into three PPT sections."""
import re

from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

REQUIRED_HEADINGS = {"Problem Statement", "Design and Implementation", "Impact"}
_STRUCTURE_MAX_TOKENS = 8192
_JSON_RETRY_INSTRUCTION = """

CRITICAL OUTPUT RETRY:
- Return exactly one complete, valid JSON object using the required schema.
- Do not use markdown fences or add text before or after the JSON.
- Escape all newlines and quotation marks inside JSON string values.
- Include all three required sections, even when a section's content is empty.
- Verify that every string, array, and object is closed before responding.
"""
_INDEXED_STRUCTURE_PROMPT = """You organize case-study source units into exactly three sections.

Return only a complete valid JSON object. Do not use markdown fences. Do not copy or
rewrite the source text. Refer to source units only by their integer IDs.

Rules:
- Use only IDs present in the input.
- Assign every substantive source unit to exactly one section.
- Omit units that are only the document title or a section-label line.
- Preserve source order inside each unit_ids array.
- Do not invent a title. Return an empty title when none is present.

Section meanings:
- Problem Statement: before-state, pain, manual work, delays, risks.
- Design and Implementation: solution, tools, architecture, process, delivery.
- Impact: after-state, benefits, metrics, adoption, strategic outcomes.

Return exactly this schema:
{
  "title": "string",
  "sections": [
    {"heading": "Problem Statement", "unit_ids": [1, 2]},
    {"heading": "Design and Implementation", "unit_ids": [3, 4]},
    {"heading": "Impact", "unit_ids": [5, 6]}
  ]
}
"""

_SECTION_LABELS = {
    "problem statement",
    "problem",
    "challenge",
    "challenges",
    "design and implementation",
    "turnb approach",
    "our approach",
    "solution",
    "impact",
    "implications",
    "outcomes",
    "results",
}

_EXPLICIT_SECTION_HEADING_RE = re.compile(
    r"(?im)(?:^|[\r\n\v\f]|\s{2,})"
    r"(?P<label>Problem\s+Statement|Design\s+and\s+Implementation|TurnB\s+Approach|"
    r"Our\s+Approach|Impact|Implications|Outcomes|Results)"
    r"(?=$|[\r\n\v\f]|\s{2,}|:)",
)
_EXPLICIT_SECTION_HEADING_MAP = {
    "problem statement": "Problem Statement",
    "design and implementation": "Design and Implementation",
    "turnb approach": "Design and Implementation",
    "our approach": "Design and Implementation",
    "impact": "Impact",
    "implications": "Impact",
    "outcomes": "Impact",
    "results": "Impact",
}

# Outcome/solution phrasing that must not sit in Problem Statement
_PROBLEM_MISPLACED_RE = re.compile(
    r"(?i)\b("
    r"executives can now|leadership (?:now )?operates|was deployed|was built|"
    r"eliminating manual|resolves in a single|available live during|"
    r"bandwidth was redirected|most significant transformation was|"
    r"always surface identical|guaranteed to surface|system-validated figures"
    r")\b"
)


def _sanitize_sections(sections: list) -> list:
    """Clear mis-placed or invented filler — missing sections stay blank."""
    for section in sections:
        heading = section.get("heading", "")
        content = str(section.get("content") or "").strip()

        if heading == "Problem Statement" and content and _PROBLEM_MISPLACED_RE.search(content):
            section["content"] = ""

    return sections


def _recover_missing_explicit_sections(content: str, sections: list[dict]) -> list[dict]:
    """Restore an explicitly labelled source section if a valid LLM response omits it."""
    matches = list(_EXPLICIT_SECTION_HEADING_RE.finditer(str(content or "")))
    if not matches:
        return sections

    recovered: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = _EXPLICIT_SECTION_HEADING_MAP[match.group("label").lower()]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section_text = str(content[match.end():end]).strip(" \t\r\n\v\f:-")
        if section_text and heading not in recovered:
            recovered[heading] = section_text

    for section in sections:
        heading = str(section.get("heading") or "").strip()
        if heading in recovered and not str(section.get("content") or "").strip():
            section["content"] = recovered[heading]

    return sections


def _source_units(content: str) -> list[str]:
    """Split source text into compact, order-preserving units for classification."""
    normalized = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if len(blocks) > 1:
        return blocks

    # Documents extracted without blank lines still commonly retain logical lines.
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines

    # A pasted narrative often arrives as one long paragraph. The unit-ID
    # fallback cannot classify a single unit that contains the problem, the
    # solution, and the impact, so retain sentence boundaries for that path.
    inline_chunks = [
        chunk.strip()
        for chunk in re.split(r"\s{2,}", normalized)
        if chunk.strip()
    ]
    sentence_units: list[str] = []
    for chunk in inline_chunks or ([normalized.strip()] if normalized.strip() else []):
        sentence_units.extend(
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+(?=(?:[A-Z0-9\"“']))", chunk
            )
            if sentence.strip()
        )
    return sentence_units


def _is_non_content_unit(text: str, title: str) -> bool:
    normalized = re.sub(r"[*#:_\-]+", " ", str(text or "")).strip().lower()
    if normalized in _SECTION_LABELS:
        return True
    return bool(title.strip()) and str(text or "").strip() == title.strip()


def _reconstruct_indexed_result(indexed: dict, units: list[str]) -> dict:
    """Rebuild full section prose locally from a compact unit-ID response."""
    title = str(indexed.get("title") or "").strip()
    raw_sections = indexed.get("sections")
    if not isinstance(raw_sections, list):
        raise ValueError("Indexed structure response is missing sections.")

    by_heading = {
        str(section.get("heading") or "").strip(): section
        for section in raw_sections
        if isinstance(section, dict)
    }
    if set(by_heading) != REQUIRED_HEADINGS:
        raise ValueError(f"Unexpected indexed section headings: {set(by_heading)}")

    assignments: dict[int, str] = {}
    for heading in ("Problem Statement", "Design and Implementation", "Impact"):
        unit_ids = by_heading[heading].get("unit_ids") or []
        if not isinstance(unit_ids, list):
            raise ValueError(f"unit_ids for {heading} must be a list.")
        for value in unit_ids:
            if not isinstance(value, int) or value < 1 or value > len(units):
                continue
            assignments.setdefault(value, heading)

    # Preserve any substantive unit the model accidentally omitted by attaching it
    # to the nearest classified source unit. Title/section-label lines remain omitted.
    assigned_ids = sorted(assignments)
    for unit_id, unit_text in enumerate(units, start=1):
        if unit_id in assignments or _is_non_content_unit(unit_text, title):
            continue
        if assigned_ids:
            nearest = min(assigned_ids, key=lambda candidate: abs(candidate - unit_id))
            assignments[unit_id] = assignments[nearest]
        else:
            assignments[unit_id] = "Problem Statement"

    sections = []
    for heading in ("Problem Statement", "Design and Implementation", "Impact"):
        section_units = [
            units[unit_id - 1]
            for unit_id in sorted(assignments)
            if assignments[unit_id] == heading
        ]
        sections.append({"heading": heading, "content": "\n\n".join(section_units)})
    return {"title": title, "sections": sections}


def _structure_with_unit_ids(content: str, client, model: str) -> dict:
    """Compact fallback that never asks the LLM to repeat source prose in JSON."""
    units = _source_units(content)
    numbered = "\n\n".join(
        f"[UNIT {index}]\n{text}" for index, text in enumerate(units, start=1)
    )
    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": _INDEXED_STRUCTURE_PROMPT},
            {"role": "user", "content": f"SOURCE UNITS:\n\n{numbered}"},
        ],
        temperature=0.0,
        **({"max_tokens": 2048} if hasattr(client, "max_tokens") else {}),
    )
    indexed = parse_json_response(response.choices[0].message.content or "")
    return _reconstruct_indexed_result(indexed, units)


def _has_structure_schema(result: object) -> bool:
    """Return True only for the full top-level structure contract."""
    if not isinstance(result, dict):
        return False
    if "title" not in result or "sections" not in result:
        return False
    return isinstance(result["sections"], list)


def structure_case_study_content(content: str) -> dict:
    """
    Ask LLM to organize content into three sections.
    Returns dict: { title, sections: [{heading, content}, ...] }
    """
    if not content or not content.strip():
        raise ValueError("Content is empty. Cannot structure empty content.")

    system_prompt = load_prompt("structure_prompt.md")
    client, model = get_llm_client()
    user_message = f"Here is the case study content to structure:\n\n{content}"
    completion_args = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
    }
    if hasattr(client, "max_tokens"):
        completion_args["max_tokens"] = max(
            int(getattr(client, "max_tokens", 0) or 0),
            _STRUCTURE_MAX_TOKENS,
        )

    response = llm_chat_completion(client, **completion_args)
    raw = response.choices[0].message.content or ""
    result = None
    try:
        result = parse_json_response(raw)
    except ValueError:
        pass

    # A response can be valid JSON but still be the wrong object shape. Treat
    # that exactly like malformed JSON and retry before using the compact,
    # unit-ID fallback.
    if not _has_structure_schema(result):
        retry_args = dict(completion_args)
        retry_args["messages"] = [
            {"role": "system", "content": system_prompt + _JSON_RETRY_INSTRUCTION},
            {"role": "user", "content": user_message},
        ]
        retry_args["temperature"] = 0.0
        retry = llm_chat_completion(client, **retry_args)
        retry_raw = retry.choices[0].message.content or ""
        try:
            result = parse_json_response(retry_raw)
        except ValueError:
            result = None
        if not _has_structure_schema(result):
            result = _structure_with_unit_ids(content, client, model)

    if not _has_structure_schema(result):
        raise ValueError("LLM structure response is missing 'title' or 'sections'.")

    result["title"] = str(result.get("title") or "").strip()

    sections = result["sections"]
    if not isinstance(sections, list) or len(sections) != 3:
        raise ValueError(f"Expected 3 sections, got {len(sections) if isinstance(sections, list) else 'invalid'}.")

    headings_returned = {s.get("heading", "") for s in sections}
    if headings_returned != REQUIRED_HEADINGS:
        raise ValueError(f"Unexpected section headings returned: {headings_returned}")

    for section in sections:
        section["content"] = str(section.get("content") or "").strip()
        if "[" in section["content"]:
            section["content"] = re.sub(r"\[.*?\]", "", section["content"]).strip()

    result["sections"] = _sanitize_sections(
        _recover_missing_explicit_sections(content, sections)
    )
    return result
