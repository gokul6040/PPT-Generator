"""
Non-LLM pipeline validation tests.

Run: python test_pipeline.py

Validates layout planner, slide writer normalisation, template analyser,
schemas, and config constants — without making any LLM API calls.
Requires only python-pptx and the project's own src/ modules.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bullets(n: int) -> list[str]:
    return [f"Sample bullet point number {i + 1} for testing purposes here" for i in range(n)]


def _short_bullets(n: int) -> list[str]:
    return [f"Short bullet {i + 1} for slide fit testing." for i in range(n)]


def _long_bullets(n: int) -> list[str]:
    return [
        f"This is a deliberately longer bullet point number {i + 1} with enough words to stress layout word budgets."
        for i in range(n)
    ]


def _slide_bullets(n_prob=4, n_design=4, n_impact=3, title="Test Title") -> dict:
    return {
        "title": title,
        "sections": [
            {"heading": "Problem Statement", "bullets": _bullets(n_prob)},
            {"heading": "Design and Implementation", "bullets": _bullets(n_design)},
            {"heading": "Impact", "bullets": _bullets(n_impact)},
        ],
    }


_TEMPLATE_PROFILE = {
    "slide_width": 13.333,
    "slide_height": 7.5,
    "template_type": "plain_canvas",
    "safe_area": {"left": 0.7, "top": 1.1, "right": 12.6, "bottom": 6.8},
}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_config():
    from src.config import (
        TEAL_PRIMARY, BLACK,
        MAX_CHARS_PER_SLIDE, BODY_GAP_CHAR_COST,
        MAX_BULLETS_PER_SINGLE_SECTION_SLIDE,
        MAX_BULLETS_PER_TWO_SECTION_HALF,
        TWO_SEC_TOP_HEADING_X, TWO_SEC_TOP_BODY_H,
        TWO_SEC_BOT_HEADING_X, TWO_SEC_BOT_BODY_H,
    )
    from pptx.util import Inches

    assert MAX_BULLETS_PER_SINGLE_SECTION_SLIDE == 6
    assert MAX_BULLETS_PER_TWO_SECTION_HALF == 3
    assert MAX_CHARS_PER_SLIDE > 500
    assert BODY_GAP_CHAR_COST >= 0
    assert TWO_SEC_TOP_HEADING_X == Inches(0.60)
    assert TWO_SEC_BOT_BODY_H == Inches(2.10)
    assert TWO_SEC_TOP_BODY_H == Inches(2.00)
    assert TWO_SEC_BOT_HEADING_X == Inches(0.60)


def test_schemas():
    from src.schemas import CaseStudyState, AgentResponse

    state = CaseStudyState(title="Demo", tone="executive", audience="leadership")
    assert state.title == "Demo"
    assert state.layout_preference == "auto"

    state.update_from_content("Some case study text")
    assert state.raw_content == "Some case study text"
    assert state.merged_content == "Some case study text"

    state.update_from_content("Updated merged text")
    assert state.raw_content == "Some case study text"   # raw stays first
    assert state.merged_content == "Updated merged text"

    state.set_title("Retail Analytics Dashboard")
    assert state.title == "Retail Analytics Dashboard"

    state.topic = "retail analytics"
    assert state.topic == "retail analytics"

    state.update_section_coverage({"problem_statement": "usable", "impact": "strong"})
    assert state.section_coverage["problem_statement"] == "usable"

    ctx = state.build_review_context()
    assert "Title: Retail Analytics Dashboard" in ctx
    assert "Updated merged text" in ctx

    gen_ctx = state.build_generation_context()
    assert "Title: Retail Analytics Dashboard" in gen_ctx

    d = state.to_dict()
    state2 = CaseStudyState.from_dict(d)
    assert state2.title == "Retail Analytics Dashboard"
    assert state2.tone == "executive"

    resp = AgentResponse(new_phase="generated", trigger_generate=True)
    assert resp.trigger_generate is True
    assert resp.new_phase == "generated"
    assert resp.assistant_messages == []
    assert resp.state_updates == {}


def test_slide_writer_helpers():
    from src.slide_writer import bullets_to_body_text, _normalize_bullets

    # bullets_to_body_text
    assert bullets_to_body_text([]) == ""
    assert bullets_to_body_text(["  "]) == ""
    result = bullets_to_body_text(["Alpha", "Beta"])
    assert result == "• Alpha\n• Beta"

    # _normalize_bullets — title must come from structured, not LLM
    structured = {
        "title": "Real Title",
        "sections": [
            {"heading": "Problem Statement", "content": "Some problem"},
            {"heading": "Design and Implementation", "content": "Design details here"},
            {"heading": "Impact", "content": ""},        # empty — LLM bullets should be discarded
        ],
    }
    raw = {
        "title": "LLM Invented Title",
        "sections": [
            {"heading": "Problem Statement",         "bullets": ["• Bullet 1", "- Bullet 2", "Plain"]},
            {"heading": "Design and Implementation", "bullets": ["Clean design bullet"]},
            {"heading": "Impact",                    "bullets": ["Impact bullet invented"]},
        ],
    }
    norm = _normalize_bullets(raw, structured)

    assert norm["title"] == "Real Title", f"Title must be from structured, got: {norm['title']}"

    pb = norm["sections"][0]["bullets"]
    assert all(not b.startswith("•") for b in pb), f"• prefix not stripped: {pb}"
    assert all(not b.startswith("-") for b in pb), f"- prefix not stripped: {pb}"
    assert len(pb) == 3

    imp = norm["sections"][2]["bullets"]
    assert imp == [], f"Impact bullets should be empty (empty source section): {imp}"

    # Sections must always be in correct order
    headings = [s["heading"] for s in norm["sections"]]
    assert headings == ["Problem Statement", "Design and Implementation", "Impact"]


def test_layout_planner_auto():
    from src.layout_planner import plan_layout

    # Small content (≤8 bullets) → compact (2 slides)
    plan = plan_layout(_slide_bullets(2, 2, 2), _TEMPLATE_PROFILE, "auto")
    assert plan["total_slides"] == 2, f"Expected 2 for auto+small, got {plan['total_slides']}"
    assert plan["slides"][0]["type"] == "two_section"
    assert plan["slides"][1]["type"] == "single"

    # Medium content (9–15 bullets) → one_section_per_slide (3 slides)
    plan = plan_layout(_slide_bullets(4, 4, 4), _TEMPLATE_PROFILE, "auto")
    assert plan["total_slides"] == 3, f"Expected 3 for auto+medium, got {plan['total_slides']}"
    for s in plan["slides"]:
        assert s["type"] == "single"

    # Large content — auto may split or stay at 3 depending on word/line budgets
    plan = plan_layout(_slide_bullets(6, 6, 6), _TEMPLATE_PROFILE, "auto")
    assert plan["total_slides"] >= 3, f"Expected >=3 slides for large content, got {plan['total_slides']}"


def test_layout_planner_exact_3():
    from src.layout_planner import plan_layout

    # Always exactly 3 slides regardless of bullet count
    plan = plan_layout(_slide_bullets(8, 8, 8), _TEMPLATE_PROFILE, "exact_3_slides")
    assert plan["total_slides"] == 3, f"exact_3_slides must always produce 3, got {plan['total_slides']}"
    for s in plan["slides"]:
        assert s["type"] == "single"
        from src.slide_fit import bullets_fit
        assert bullets_fit(s["bullets"]), f"exact_3 slides must fit by height, got {len(s['bullets'])} bullets"


def test_layout_planner_compact():
    from src.layout_planner import plan_layout

    # 3+3 bullets: should fit in 2 slides
    plan = plan_layout(_slide_bullets(3, 3, 3), _TEMPLATE_PROFILE, "compact")
    assert plan["total_slides"] == 2
    assert plan["slides"][0]["type"] == "two_section"
    secs = plan["slides"][0]["sections"]
    assert secs[0]["heading"] == "Problem Statement"
    assert secs[1]["heading"] == "Design and Implementation"
    assert plan["slides"][1]["heading"] == "Impact"


def test_layout_planner_split_if_needed():
    from src.layout_planner import plan_layout

    # Long bullets force continuation slides when word budget is exceeded
    heavy = {
        "title": "Heavy",
        "sections": [
            {"heading": "Problem Statement", "bullets": _long_bullets(18)},
            {"heading": "Design and Implementation", "bullets": _long_bullets(18)},
            {"heading": "Impact", "bullets": _long_bullets(18)},
        ],
    }
    plan = plan_layout(heavy, _TEMPLATE_PROFILE, "split_if_needed")
    assert plan["total_slides"] > 3, f"long bullets should split, got {plan['total_slides']}"
    cont = [s for s in plan["slides"] if s["type"] == "continuation"]
    assert len(cont) >= 1


def test_layout_planner_one_section_per_slide():
    from src.layout_planner import plan_layout

    # Under limit → 3 clean slides
    plan = plan_layout(_slide_bullets(4, 4, 4), _TEMPLATE_PROFILE, "one_section_per_slide")
    assert plan["total_slides"] == 3
    for s in plan["slides"]:
        assert s["type"] == "single"

    # Over word budget → continuation slides appear
    heavy = {
        "title": "Heavy",
        "sections": [
            {"heading": "Problem Statement", "bullets": _long_bullets(18)},
            {"heading": "Design and Implementation", "bullets": _long_bullets(18)},
            {"heading": "Impact", "bullets": _long_bullets(18)},
        ],
    }
    plan = plan_layout(heavy, _TEMPLATE_PROFILE, "one_section_per_slide")
    assert plan["total_slides"] > 3


def test_slide_fit_height_packing():
    from src.layout_planner import plan_layout
    from src.slide_fit import bullets_fit, pack_bullets

    short_nine = _short_bullets(9)
    chunks = pack_bullets(short_nine)
    assert len(chunks) == 1, f"9 short bullets should fit one slide, got {len(chunks)} chunks"
    assert bullets_fit(short_nine)

    # Same section should not split early at a fixed bullet count
    plan = plan_layout(
        {
            "title": "Fit Test",
            "sections": [
                {"heading": "Problem Statement", "bullets": short_nine},
                {"heading": "Design and Implementation", "bullets": _short_bullets(2)},
                {"heading": "Impact", "bullets": _short_bullets(2)},
            ],
        },
        _TEMPLATE_PROFILE,
        "one_section_per_slide",
    )
    problem_slides = [s for s in plan["slides"] if "Problem" in s.get("heading", "")]
    assert len(problem_slides) == 1, f"expected 1 problem slide, got {len(problem_slides)}"
    assert len(problem_slides[0]["bullets"]) == 9

    # Heavy section splits by height; continuation chunks should not be mostly empty
    from src.slide_fit import estimate_bullets_height, is_orphan_chunk, max_body_height

    heavy_chunks = pack_bullets(_long_bullets(18))
    assert len(heavy_chunks) >= 2, "18 bullets should split across slides by height"
    for chunk in heavy_chunks:
        assert bullets_fit(chunk)
        assert not is_orphan_chunk(chunk), "continuation slides should carry meaningful content"
        assert estimate_bullets_height(chunk) >= 0.25 * max_body_height()


def test_layout_planner_empty_sections():
    from src.layout_planner import plan_layout

    # Empty sections (generate anyway scenario) still produce slides
    empty = {
        "title": "",
        "sections": [
            {"heading": "Problem Statement", "bullets": []},
            {"heading": "Design and Implementation", "bullets": ["One bullet"]},
            {"heading": "Impact", "bullets": []},
        ],
    }
    plan = plan_layout(empty, _TEMPLATE_PROFILE, "one_section_per_slide")
    assert plan["total_slides"] == 3
    assert plan["slides"][0]["bullets"] == []
    assert plan["slides"][2]["bullets"] == []


def test_template_analyzer():
    from src.template_analyzer import analyze_template

    template_path = "templates/sample_template.pptx"
    if not os.path.exists(template_path):
        print(f"  {SKIP}  template_analyzer — skipped (no template at {template_path})")
        return

    profile = analyze_template(template_path)
    required = {"slide_width", "slide_height", "slide_count", "template_type",
                "has_editable_placeholders", "safe_area"}
    missing = required - set(profile.keys())
    assert not missing, f"Missing keys: {missing}"
    assert isinstance(profile["slide_width"], float)
    assert isinstance(profile["slide_height"], float)
    assert profile["template_type"] == "plain_canvas"
    assert isinstance(profile["safe_area"], dict)
    safe = profile["safe_area"]
    assert all(k in safe for k in ("left", "top", "right", "bottom"))
    print(f"  Template: {profile['slide_width']:.3f}in x {profile['slide_height']:.3f}in "
          f"({profile['slide_count']} slide(s))")


def test_readiness():
    from src.readiness import (
        evaluate_readiness,
        is_explicit_review_request,
        is_readiness_advice_request,
        readiness_from_assessment,
        render_short_status,
        should_show_full_review,
    )

    assert is_explicit_review_request("review")
    assert is_explicit_review_request("review the content so far")
    assert is_readiness_advice_request("what is the best thing I can do?")
    assert not should_show_full_review("Power BI, SQL, Python", "content_addition", "collecting", 50)

    assessment = {
        "section_status": {
            "problem_statement": "weak",
            "design_implementation": "missing",
            "impact": "missing",
        },
        "readiness_level": "not_enough_to_generate",
        "enough_to_generate": False,
        "title_status": "missing",
        "questions_to_user": ["What was the problem?"],
        "question_count_hint": "1-3",
    }
    readiness = readiness_from_assessment(assessment)
    assert readiness["readiness_level"] == "not_enough_to_generate"
    assert not readiness["has_title"]

    status = render_short_status(assessment)
    assert "Problem Statement: weak" in status
    assert "Design and Implementation: missing" in status

    fallback = evaluate_readiness(None, review_result=None, content="")
    assert fallback["readiness_level"] == "not_enough_to_generate"


def test_guide_policy():
    from src.guide_policy import (
        FIRST_BATCH_SIZE,
        STRONG_BASELINE_FIRST_BATCH,
        STRONG_BASELINE_MAX_QUESTIONS,
        apply_guide_policy,
        autonomous_question_cap,
        build_pre_generate_message,
        build_question_queue,
        deck_ready,
        is_strong_baseline,
        select_question_batch,
    )

    content = "weekly reporting retail analytics " * 40

    # LLM says not ready with questions — Python respects it
    all_usable = {
        "acknowledgement": "Captured vague impact.",
        "section_status": {
            "problem_statement": "usable",
            "design_implementation": "usable",
            "impact": "usable",
        },
        "deck_ready": False,
        "title_status": "missing",
        "enough_to_generate": True,
        "questions_to_user": [
            "Title?",
            "Problem detail?",
            "Design KPIs?",
            "Impact metrics?",
        ],
        "conversational_reply": "Thin across all sections — a few specifics would help.",
    }
    assert not deck_ready(all_usable)

    out = apply_guide_policy(dict(all_usable), content, interaction_mode="guide")
    assert len(out["questions_to_user"]) == 4
    assert not out["deck_ready"]

    pre = build_pre_generate_message(out, content)
    assert "generate anyway" in pre.lower()

    # LLM impact question passes through unchanged
    not_ready = {
        "acknowledgement": "Got design details.",
        "section_status": {
            "problem_statement": "usable",
            "design_implementation": "usable",
            "impact": "missing",
        },
        "deck_ready": False,
        "title_status": "missing",
        "enough_to_generate": True,
        "questions_to_user": ["What measurable outcomes did the client see after go-live?"],
    }
    gap_out = apply_guide_policy(dict(not_ready), content, interaction_mode="guide")
    assert not gap_out["deck_ready"]
    assert "go-live" in gap_out["questions_to_user"][0].lower()

    # LLM ready + no questions = ready
    ready = {
        "acknowledgement": "Complete.",
        "section_status": {
            "problem_statement": "strong",
            "design_implementation": "strong",
            "impact": "strong",
        },
        "deck_ready": True,
        "title_status": "provided",
        "enough_to_generate": True,
        "questions_to_user": [],
        "conversational_reply": "All sections strong — say generate when ready.",
    }
    assert deck_ready(ready)
    ready_out = apply_guide_policy(dict(ready), content, interaction_mode="guide")
    assert ready_out["deck_ready"]
    assert ready_out["questions_to_user"] == []

    # LLM says ready but still has questions — Python blocks
    premature = dict(ready)
    premature["questions_to_user"] = ["Timeline?"]
    premature["deck_ready"] = True
    blocked = apply_guide_policy(dict(premature), content, interaction_mode="guide")
    assert not blocked["deck_ready"]

    # Batching: 5 needed → show 5, not forced to 8
    five_needed = {
        "section_status": {
            "problem_statement": "missing",
            "design_implementation": "missing",
            "impact": "missing",
        },
        "title_status": "missing",
        "enough_to_generate": False,
        "questions_to_user": [
            "Q1 problem?", "Q2 problem detail?", "Q3 design?",
            "Q4 impact?", "Q5 title line?",
        ],
        "priority_focus": ["problem_statement", "design_implementation", "impact"],
    }
    q5 = build_question_queue(five_needed)
    assert len(q5) >= 5
    batch5, pending5, _, _ = select_question_batch(q5, None)
    assert len(batch5) == 5
    assert pending5 == []

    # Batching: 9 needed → 8 first, 1 pending
    nine = [f"Question number {i} about case study gaps?" for i in range(9)]
    batch9, pending9, bn, _ = select_question_batch(nine, None)
    assert len(batch9) == FIRST_BATCH_SIZE
    assert len(pending9) == 1
    assert bn == 1

    # Batching: 2nd batch of 3 only (not forced to 4)
    prior = {
        "questions_shown_history": batch9,
        "question_batch_number": 1,
    }
    batch2, pending2, _, _ = select_question_batch(nine, prior)
    assert len(batch2) == 1
    assert pending2 == []

    # 2nd batch with 7 remaining after first 8 of 11
    eleven = [f"Gap question {i}?" for i in range(11)]
    b1, p1, bn1, hist1 = select_question_batch(eleven, None)
    assert len(b1) == 8 and len(p1) == 3
    prior2 = {"questions_shown_history": hist1, "question_batch_number": bn1}
    b2, p2, _, _ = select_question_batch(eleven, prior2)
    assert len(b2) == 3
    assert p2 == []

    # LLM full queue preserved in question_queue
    all_weak = {
        "section_status": {
            "problem_statement": "weak",
            "design_implementation": "weak",
            "impact": "weak",
        },
        "title_status": "missing",
        "deck_ready": False,
        "enough_to_generate": True,
        "questions_to_user": ["Title?", "Problem detail?", "Design detail?", "Impact outcomes?"],
    }
    weak_out = apply_guide_policy(dict(all_weak), content, interaction_mode="guide")
    assert len(weak_out["question_queue"]) == 4
    assert len(weak_out["questions_to_user"]) == 4

    # Strong baseline: LLM over-asked 8 — cap at 5, first batch 4
    strong_base = {
        "section_status": {
            "problem_statement": "strong",
            "design_implementation": "strong",
            "impact": "strong",
        },
        "deck_ready": True,
        "enough_to_generate": True,
        "quality_label": "strong",
        "readiness_level": "strong",
        "title_status": "provided",
        "questions_to_user": [f"Polish question {i}?" for i in range(8)],
        "conversational_reply": "Good enough to generate — optional polish below.",
    }
    assert is_strong_baseline(strong_base)
    assert autonomous_question_cap(strong_base) == STRONG_BASELINE_MAX_QUESTIONS
    queue = build_question_queue(strong_base)
    assert len(queue) == STRONG_BASELINE_MAX_QUESTIONS
    b1, pending, _, _ = select_question_batch(queue, None, assessment=strong_base)
    assert len(b1) == STRONG_BASELINE_FIRST_BATCH
    assert len(pending) == 1

    review_out = apply_guide_policy(
        dict(strong_base), content, interaction_mode="readiness_advice"
    )
    assert "Good enough to generate" in review_out["conversational_reply"]
    assert len(review_out["questions_to_user"]) <= STRONG_BASELINE_FIRST_BATCH


def test_title_placeholder():
    from src.title_utils import PPT_TITLE_PLACEHOLDER, resolve_ppt_banner_title

    assert resolve_ppt_banner_title("Retail Analytics")[0] == "Retail Analytics"
    assert resolve_ppt_banner_title("Retail Analytics")[1] is False
    text, used = resolve_ppt_banner_title("")
    assert text == PPT_TITLE_PLACEHOLDER
    assert used is True
    text2, used2 = resolve_ppt_banner_title(None)
    assert text2 == PPT_TITLE_PLACEHOLDER
    assert used2 is True


def test_title_detection_and_reconciliation():
    from src.content_reviewer import _normalize_assessment
    from src.title_utils import PPT_TITLE_PLACEHOLDER, extract_explicit_title

    assert PPT_TITLE_PLACEHOLDER == "[Title]"
    assert extract_explicit_title("Title: Retail Analytics Dashboard") == "Retail Analytics Dashboard"
    assert extract_explicit_title("Case Study Title: Procurement Flow") == "Procurement Flow"
    assert extract_explicit_title("Headline: Workflow Automation") == "Workflow Automation"
    assert (
        extract_explicit_title("Retail Store Task Tracking Dashboard\n\nProblem...")
        == "Retail Store Task Tracking Dashboard"
    )
    assert extract_explicit_title("Problem Statement Client: A manufacturing company") == ""
    assert extract_explicit_title("Client: A manufacturing company") == ""
    assert extract_explicit_title("Before TurnB, approvals were slow") == ""

    base = {
        "section_status": {
            "problem_statement": "strong",
            "design_implementation": "strong",
            "impact": "strong",
        },
        "readiness_level": "strong",
        "enough_to_generate": True,
        "deck_ready": True,
        "quality_label": "strong",
        "already_captured": [],
        "do_not_ask_about": [],
        "priority_focus": [],
        "available_strong": ["Good story"],
        "questions_to_user": [],
        "top_improvement_items": [],
        "impact_note": "",
        "can_continue": True,
        "conversational_reply": "",
        "acknowledgement": "ok",
        "question_count_hint": "0",
    }
    procurement = "Problem Statement Client: A manufacturing company with multiple departments."

    contradictory = {
        **base,
        "missing_weak": ["No explicit title was provided"],
        "detected_title": "",
        "title_status": "provided",
        "suggested_title": "",
    }
    out = _normalize_assessment(dict(contradictory), procurement)
    assert out["title_status"] == "missing"
    assert out["detected_title"] == ""
    assert not any("no explicit title" in x.lower() for x in out["missing_weak"])

    missing_with_suggestion = {
        **base,
        "missing_weak": ["No explicit title was provided", "No rollout timeline"],
        "detected_title": "",
        "title_status": "missing",
        "suggested_title": "Procurement Approval Workflow Automation",
    }
    out2 = _normalize_assessment(dict(missing_with_suggestion), procurement)
    assert out2["title_status"] == "missing"
    assert out2["missing_weak"][0] == "Suggested title: Procurement Approval Workflow Automation"
    assert not any("no explicit title" in x.lower() for x in out2["missing_weak"])

    provided = {
        **base,
        "missing_weak": ["No explicit title was provided", "No timeline"],
        "detected_title": "Procurement Approval Workflow Automation",
        "title_status": "provided",
        "suggested_title": "",
    }
    out3 = _normalize_assessment(
        dict(provided),
        "Procurement Approval Workflow Automation\n\nProblem Statement...",
    )
    assert out3["title_status"] == "provided"
    assert not any("no explicit title" in x.lower() for x in out3["missing_weak"])


def test_storage_helpers():
    from src.storage import (
        DownloadRef,
        can_serve_download,
        download_ref_from_message,
        _sanitize_filename,
    )

    assert _sanitize_filename("My Deck.pptx") == "My Deck.pptx"
    assert _sanitize_filename("../../evil.pptx") == "evil.pptx"

    msg = {
        "download_blob": "generated/sess01/turnb_case_study_test.pptx",
        "download_file_name": "turnb_case_study_test.pptx",
    }
    ref = download_ref_from_message(msg)
    assert isinstance(ref, DownloadRef)
    assert ref.blob_name == "generated/sess01/turnb_case_study_test.pptx"
    assert not can_serve_download(msg)  # no live blob in unit test


def test_agent_controller_fast_paths():
    """Test intent fast-path regex without LLM calls."""
    from src.chat_assistant import _fast_intent

    assert _fast_intent("hi", "start") == "greeting"
    assert _fast_intent("hello!", "reviewed") == "greeting"
    assert _fast_intent("generate", "reviewed") == "generate"
    assert _fast_intent("generate anyway", "reviewed") == "generate"
    assert _fast_intent("continue", "awaiting_details") == "generate"
    assert _fast_intent("generate", "collecting") == "generate"
    assert _fast_intent("generate", "generated") == "generate"  # re-generate after first run
    assert _fast_intent("I want to create a case study on retail", "start") == "new_case_study_request"
    assert _fast_intent("keep exactly 3 slides", "reviewed") == "layout_preference"
    assert _fast_intent("keep exactly 3 slides", "generated") == "revise"
    assert _fast_intent("some random text about the project", "start") is None


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    test_config,
    test_schemas,
    test_slide_writer_helpers,
    test_layout_planner_auto,
    test_layout_planner_exact_3,
    test_layout_planner_compact,
    test_layout_planner_split_if_needed,
    test_layout_planner_one_section_per_slide,
    test_slide_fit_height_packing,
    test_layout_planner_empty_sections,
    test_template_analyzer,
    test_readiness,
    test_guide_policy,
    test_title_placeholder,
    test_title_detection_and_reconciliation,
    test_storage_helpers,
    test_agent_controller_fast_paths,
]

if __name__ == "__main__":
    failures = []
    for fn in TESTS:
        name = fn.__name__.replace("test_", "").replace("_", " ")
        try:
            fn()
            print(f"  {PASS}  {name}")
        except Exception as exc:
            failures.append((name, exc))
            print(f"  {FAIL}  {name}: {exc}")

    print()
    if failures:
        print(f"{len(failures)} test(s) FAILED:")
        for name, exc in failures:
            print(f"  - {name}: {exc}")
        sys.exit(1)
    else:
        total = len(TESTS)
        print(f"All {total} tests passed {PASS}")
