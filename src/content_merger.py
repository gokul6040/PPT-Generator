"""Merge fragment or full follow-up details into existing case study content."""
from src.utils import get_llm_client, llm_chat_completion, load_prompt


def merge_additional_details(
    base_content: str,
    additional_input: str,
    review_result: dict | None = None,
) -> str:
    """
    Intelligently merge user follow-up into base content.

    - Short / fragment answers (e.g. "POS, ERP, CRM") are woven into the right topics.
    - Full rewrites from the user are preserved as-is with minimal editing.
    """
    base = (base_content or "").strip()
    addition = (additional_input or "").strip()
    if not addition:
        return base
    if not base:
        return addition

    system_prompt = load_prompt("merge_prompt.md")
    client, model = get_llm_client()

    review_block = ""
    if review_result:
        missing = review_result.get("missing_weak") or []
        questions = review_result.get("questions_to_user") or []
        section_status = review_result.get("section_status") or {}
        coverage = review_result.get("section_coverage") or {}
        captured = review_result.get("already_captured") or []
        priority = review_result.get("priority_focus") or []
        if missing or questions or section_status or coverage:
            review_block = "\n\nPRIOR ASSESSMENT CONTEXT (place new input in the right section):\n"
            if section_status:
                review_block += "Section status: " + ", ".join(
                    f"{k}={v}" for k, v in section_status.items()
                ) + "\n"
            elif coverage:
                review_block += "Section coverage: " + ", ".join(
                    f"{k}={v}" for k, v in coverage.items()
                ) + "\n"
            if captured:
                review_block += "Already captured (do not duplicate):\n"
                review_block += "\n".join(f"- {item}" for item in captured[:12])
                review_block += "\n"
            if priority:
                review_block += "Priority sections for new detail: " + ", ".join(priority) + "\n"
            if missing:
                review_block += "Missing / weak areas:\n"
                review_block += "\n".join(f"- {item}" for item in missing)
                review_block += "\n"
            if questions:
                review_block += "Questions previously asked:\n"
                review_block += "\n".join(f"- {item}" for item in questions)

    user_message = (
        f"BASE CONTENT:\n{base}\n\n"
        f"ADDITIONAL USER INPUT:\n{addition}"
        f"{review_block}"
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

    merged = (response.choices[0].message.content or "").strip()
    if not merged:
        raise ValueError("LLM returned empty merged content.")

    # Strip accidental markdown fences
    if merged.startswith("```"):
        merged = merged.strip("`").strip()
        if merged.lower().startswith("text"):
            merged = merged[4:].strip()

    # Reject lazy end-append patterns — one retry with explicit correction
    append_markers = ("\n\nAdditional details:", "\n\nAdditional Details:", "\n\nUpdates:")
    if any(marker in merged for marker in append_markers):
        retry = llm_chat_completion(
            client,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": merged},
                {
                    "role": "user",
                    "content": (
                        "You appended new information at the end. Rewrite the full merged document "
                        "and weave EVERY new detail inline into the correct part of the narrative. "
                        "No trailing 'Additional details' section."
                    ),
                },
            ],
            temperature=0.1,
        )
        merged = (retry.choices[0].message.content or merged).strip()

    return merged
