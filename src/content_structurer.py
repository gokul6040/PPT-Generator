"""Structure reviewed content into three PPT sections."""
import re

from src.utils import get_llm_client, llm_chat_completion, load_prompt, parse_json_response

REQUIRED_HEADINGS = {"Problem Statement", "Design and Implementation", "Impact"}

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


def structure_case_study_content(content: str) -> dict:
    """
    Ask LLM to organize content into three sections.
    Returns dict: { title, sections: [{heading, content}, ...] }
    """
    if not content or not content.strip():
        raise ValueError("Content is empty. Cannot structure empty content.")

    system_prompt = load_prompt("structure_prompt.md")
    client, model = get_llm_client()

    response = llm_chat_completion(
        client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the case study content to structure:\n\n{content}"},
        ],
        temperature=0.1,
    )

    raw = response.choices[0].message.content or ""
    result = parse_json_response(raw)

    if "title" not in result or "sections" not in result:
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

    result["sections"] = _sanitize_sections(sections)
    return result
