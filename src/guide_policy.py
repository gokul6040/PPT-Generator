"""
Post-assessment policy — LLM owns judgment and questions; Python batches display.

LLM: grading, deck_ready, questions_to_user, conversational_reply.
Python: dedupe, autonomous cap on strong baselines, batch display (8→4, or 4→4 when strong).
"""
from src.readiness import render_short_status

_SECTION_KEYS = ("problem_statement", "design_implementation", "impact")

FIRST_BATCH_SIZE = 8
LATER_BATCH_SIZE = 4
STRONG_BASELINE_FIRST_BATCH = 4
STRONG_BASELINE_MAX_QUESTIONS = 5


def completeness_context(content: str, prior_assessment: dict | None = None) -> str:
    word_count = len((content or "").split())
    lines = [f"ACCUMULATED_WORD_COUNT: {word_count}"]

    if prior_assessment:
        status = prior_assessment.get("section_status") or {}
        if status:
            lines.append(
                "PRIOR_SECTION_STATUS: "
                + ", ".join(f"{k}={v}" for k, v in status.items())
            )
        captured = prior_assessment.get("already_captured") or []
        if captured:
            lines.append("PRIOR_ALREADY_CAPTURED:\n" + "\n".join(f"- {c}" for c in captured[:12]))
        do_not = prior_assessment.get("do_not_ask_about") or []
        if do_not:
            lines.append("DO_NOT_ASK_ABOUT:\n" + "\n".join(f"- {d}" for d in do_not[:10]))
        shown = prior_assessment.get("questions_shown_history") or []
        if shown:
            lines.append(
                "QUESTIONS_ALREADY_SHOWN_TO_USER:\n"
                + "\n".join(f"- {q}" for q in shown[:12])
            )
        pending = prior_assessment.get("pending_questions") or []
        if pending:
            lines.append(
                f"PENDING_QUESTIONS_NOT_YET_SHOWN ({len(pending)}):\n"
                + "\n".join(f"- {q}" for q in pending[:8])
            )

    lines.append(
        "AUTONOMOUS RULES: You decide how many questions (0–8). "
        "Strong baseline → deck_ready or enough_to_generate + max 2–4 polish questions only. "
        f"Python displays first batch up to {FIRST_BATCH_SIZE} (or {STRONG_BASELINE_FIRST_BATCH} if strong baseline), "
        f"then {LATER_BATCH_SIZE} — never padded."
    )

    return "\n".join(lines)


def _strong_count(section_status: dict) -> int:
    return sum(1 for k in _SECTION_KEYS if section_status.get(k) == "strong")


def is_strong_baseline(assessment: dict) -> bool:
    """Content is credible enough that only polish questions are warranted."""
    status = assessment.get("section_status") or {}
    if assessment.get("deck_ready"):
        return True
    if _strong_count(status) >= 2 and assessment.get("enough_to_generate"):
        return True
    if assessment.get("readiness_level") in ("decent", "strong") and _strong_count(status) >= 2:
        return True
    if assessment.get("quality_label") == "strong":
        return True
    return False


def autonomous_question_cap(assessment: dict) -> int | None:
    """Max questions LLM should have listed — safety trim only on strong baselines."""
    if is_strong_baseline(assessment):
        return STRONG_BASELINE_MAX_QUESTIONS
    return None


def deck_ready(assessment: dict) -> bool:
    if assessment.get("pending_questions"):
        return False
    if assessment.get("questions_to_user"):
        return False
    return bool(assessment.get("deck_ready", False))


def _dedupe_questions(questions: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for q in questions:
        q = str(q).strip()
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def build_question_queue(assessment: dict) -> list[str]:
    queue = _dedupe_questions(list(assessment.get("questions_to_user") or []))
    cap = autonomous_question_cap(assessment)
    if cap is not None:
        queue = queue[:cap]
    return queue


def _first_batch_size(assessment: dict) -> int:
    if is_strong_baseline(assessment):
        return STRONG_BASELINE_FIRST_BATCH
    return FIRST_BATCH_SIZE


def select_question_batch(
    full_queue: list[str],
    prior_assessment: dict | None,
    *,
    assessment: dict | None = None,
) -> tuple[list[str], list[str], int, list[str]]:
    shown_history = list((prior_assessment or {}).get("questions_shown_history") or [])
    batch_number = int((prior_assessment or {}).get("question_batch_number") or 0)

    if not prior_assessment or not shown_history:
        batch_number = 0

    unshown = [q for q in full_queue if q.strip() not in shown_history]

    if not unshown:
        return [], [], batch_number, shown_history

    if batch_number == 0:
        batch_size = _first_batch_size(assessment or {})
    else:
        batch_size = LATER_BATCH_SIZE

    this_batch = unshown[:batch_size]
    still_pending = unshown[len(this_batch):]
    next_batch_number = batch_number + (1 if this_batch else 0)

    return this_batch, still_pending, next_batch_number, shown_history + this_batch


def max_questions_for_assessment(assessment: dict, content: str) -> int:
    if deck_ready(assessment):
        return 0
    return len(assessment.get("questions_to_user") or [])


def _build_review_style_reply(assessment: dict, questions: list[str]) -> str:
    """Structured review response — practical, not a checklist."""
    ready = deck_ready(assessment)
    enough = assessment.get("enough_to_generate", False)
    llm_ready = bool(assessment.get("deck_ready", False))
    quality = assessment.get("quality_label", "unknown")
    status = render_short_status(assessment)
    ack = (assessment.get("acknowledgement") or "").strip()
    more_pending = bool(assessment.get("pending_questions"))

    parts: list[str] = []
    if ack:
        parts.append(ack)
        parts.append("")

    good_enough = ready or enough or llm_ready
    parts.append(f"**Good enough to generate?** {'Yes' if good_enough else 'Not yet'}")
    parts.append(f"**Quality:** {quality}")

    if ready:
        parts.append("**Verdict:** Deck-ready — say **generate** when you want the PPT.")
    elif llm_ready or (enough and is_strong_baseline(assessment)):
        parts.append(
            "**Verdict:** Strong baseline — good enough for a solid deck. "
            "Answer below only if you want it sharper (optional)."
        )
    elif enough:
        parts.append("**Verdict:** Workable — generate anyway OK, or strengthen with answers below.")
    else:
        parts.append("**Verdict:** Core gaps remain — answer what's below.")

    parts.extend(["", status])

    missing = list(assessment.get("missing_weak") or [])[:5]
    if missing:
        parts.extend(["", "**Top gaps:**"])
        parts.extend(f"- {m}" for m in missing)

    optional = list(assessment.get("top_improvement_items") or [])
    if questions:
        label = (
            "**Optional — to sharpen further (answer any you know):**"
            if good_enough and is_strong_baseline(assessment)
            else "**What's still needed:**"
        )
        parts.extend(["", label])
        parts.extend(f"{i + 1}. {q}" for i, q in enumerate(questions))
        if more_pending:
            n = len(assessment.get("pending_questions") or [])
            parts.append(f"\n({n} more in next batch if needed.)")
    elif optional and good_enough:
        parts.extend(["", "**Optional polish** (say if you want to add any):"])
        parts.extend(f"- {o}" for o in optional[:3])

    if ready:
        parts.extend(["", "Say **generate** when ready."])
    elif enough:
        parts.extend(["", "Or say **generate anyway**."])

    llm_reply = (assessment.get("conversational_reply") or "").strip()
    if llm_reply and len(llm_reply) > 30 and "good enough" in llm_reply.lower():
        return llm_reply + (
            ("\n\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions)))
            if questions else ""
        )

    return "\n".join(parts)


def _build_display_reply(
    assessment: dict,
    questions: list[str],
    *,
    interaction_mode: str = "guide",
) -> str:
    if interaction_mode == "readiness_advice":
        return _build_review_style_reply(assessment, questions)

    ack = (assessment.get("acknowledgement") or "Got it.").strip()
    llm_reply = (assessment.get("conversational_reply") or "").strip()
    status = render_short_status(assessment)
    enough = assessment.get("enough_to_generate", False)
    ready = deck_ready(assessment)
    more_pending = bool(assessment.get("pending_questions"))
    strong = is_strong_baseline(assessment)

    if ready and not questions:
        if llm_reply:
            return llm_reply
        return (
            f"{ack}\n\n{status}\n\n"
            "You're ready to generate.\n\nSay **generate** when ready."
        )

    parts: list[str] = []
    if llm_reply and len(llm_reply) > 20:
        parts.append(llm_reply)
    else:
        parts.extend([ack, "", status])

    if questions:
        if strong and enough:
            parts.extend(["", "**Optional — to make it stronger (not required):**", ""])
        elif not parts[-1].endswith(":"):
            parts.append("")
        parts.extend(f"{i + 1}. {q}" for i, q in enumerate(questions))
        if more_pending:
            n = len(assessment.get("pending_questions") or [])
            parts.append(f"\n({n} more after you reply.)")

    if enough and not ready:
        parts.append("\nOr say **generate anyway**.")

    return "\n".join(parts)


def build_pre_generate_message(assessment: dict, content: str) -> str:
    full_queue = build_question_queue(assessment)
    this_batch, still_pending, _, _ = select_question_batch(full_queue, assessment, assessment=assessment)
    if not this_batch and full_queue:
        this_batch = full_queue[:LATER_BATCH_SIZE]

    parts = [
        (assessment.get("acknowledgement") or "Before I build the PPT:").strip(),
        "",
        render_short_status(assessment),
        "",
    ]
    if this_batch:
        parts.extend(f"{i + 1}. {q}" for i, q in enumerate(this_batch))
    if still_pending:
        parts.append(f"\n(+ {len(still_pending)} more after you answer these)")
    parts.extend([
        "",
        "Reply with answers, or say **generate anyway** to build with current content.",
    ])
    return "\n".join(parts)


def apply_guide_policy(
    assessment: dict,
    content: str,
    *,
    interaction_mode: str = "guide",
    prior_assessment: dict | None = None,
) -> dict:
    if interaction_mode == "full_review":
        queue = build_question_queue(assessment)
        assessment["questions_to_user"] = queue
        assessment["question_queue"] = queue
        assessment["pending_questions"] = []
        assessment["deck_ready"] = deck_ready(assessment)
        return assessment

    if interaction_mode not in ("guide", "readiness_advice"):
        assessment["deck_ready"] = deck_ready(assessment)
        return assessment

    full_queue = build_question_queue(assessment)
    this_batch, still_pending, next_batch_number, shown_history = select_question_batch(
        full_queue, prior_assessment, assessment=assessment
    )

    assessment["question_queue"] = full_queue
    assessment["questions_to_user"] = this_batch
    assessment["pending_questions"] = still_pending
    assessment["questions_shown_history"] = shown_history
    assessment["question_batch_number"] = next_batch_number
    assessment["has_more_questions"] = bool(still_pending)
    assessment["question_count_hint"] = str(len(this_batch)) if this_batch else "0"
    assessment["deck_ready"] = deck_ready(assessment)
    assessment["conversational_reply"] = _build_display_reply(
        assessment, this_batch, interaction_mode=interaction_mode
    )

    return assessment
