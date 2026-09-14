"""
Non-LLM pipeline validation tests.

Run: python test_pipeline.py

Validates layout planner, slide writer normalisation, template analyser,
schemas, and config constants — without making any LLM API calls.
Requires only python-pptx and the project's own src/ modules.
"""
import os
import sys
import json
from types import SimpleNamespace
from unittest.mock import patch

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
    from src.slide_writer import (
        _normalize_blocks,
        _normalize_bullets,
        bullets_to_body_text,
        section_to_content_blocks,
    )

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
            {"heading": "Problem Statement", "points": [
                {"label": "First Issue", "description": "Bullet 1"},
                {"label": "Second Issue", "description": "Bullet 2"},
                {"label": "Plain Detail", "description": "Plain"},
            ]},
            {"heading": "Design and Implementation", "points": [
                {"label": "Design", "description": "Clean design detail"},
            ]},
            {"heading": "Impact", "points": [
                {"label": "Impact", "description": "Impact detail invented"},
            ]},
        ],
    }
    norm = _normalize_bullets(raw, structured)

    assert norm["title"] == "Real Title", f"Title must be from structured, got: {norm['title']}"

    points = norm["sections"][0]["points"]
    assert len(points) == 3
    assert points[0] == {"label": "First Issue", "description": "Bullet 1"}

    imp = norm["sections"][2]["points"]
    assert imp == [], f"Impact points should be empty (empty source section): {imp}"

    # Sections must always be in correct order
    headings = [s["heading"] for s in norm["sections"]]
    assert headings == ["Problem Statement", "Design and Implementation", "Impact"]

    # Regression: source-backed sections must never become heading-only slides
    # when the LLM omits their points.
    missing_design = {
        "sections": [
            {"heading": "Problem Statement", "points": [{"label": "Records", "description": "Records were unreliable."}]},
            {"heading": "Design and Implementation", "points": []},
            {"heading": "Impact", "points": [{"label": "Visibility", "description": "Leaders gained visibility."}]},
        ],
    }
    fallback_source = {
        "title": "Real Title",
        "sections": [
            {"heading": "Problem Statement", "content": "Records were unreliable."},
            {
                "heading": "Design and Implementation",
                "content": "Built a validated lease-data pipeline.\n\nDeployed a Teams-based AI query agent.",
            },
            {"heading": "Impact", "content": "Leaders gained visibility."},
        ],
    }
    recovered = _normalize_bullets(missing_design, fallback_source)
    design = recovered["sections"][1]
    assert design["points"] == [
        {"label": "", "description": "Built a validated lease-data pipeline."},
        {"label": "", "description": "Deployed a Teams-based AI query agent."},
    ]
    assert section_to_content_blocks(design), "Non-empty source must yield slide body blocks"

    recovered_blocks = _normalize_blocks(
        {"sections": [{"heading": heading, "blocks": []} for heading in headings]},
        fallback_source,
    )
    assert recovered_blocks["sections"][1]["blocks"], (
        "The ordered-block path must also preserve non-empty source content"
    )


def test_content_structurer_retries_invalid_json():
    from src.content_structurer import structure_case_study_content

    valid_result = {
        "title": "Portfolio Analytics",
        "sections": [
            {"heading": "Problem Statement", "content": "Records contained duplicates."},
            {"heading": "Design and Implementation", "content": "The team built a dashboard."},
            {"heading": "Impact", "content": "Leaders gained portfolio visibility."},
        ],
    }
    invalid_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='```json\n{"title":"Truncated"'))]
    )
    valid_response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=json.dumps(valid_result)))
        ]
    )
    fake_client = SimpleNamespace(max_tokens=4096)
    with (
        patch("src.content_structurer.get_llm_client", return_value=(fake_client, "test-model")),
        patch(
            "src.content_structurer.llm_chat_completion",
            side_effect=[invalid_response, valid_response],
        ) as completion,
    ):
        result = structure_case_study_content("Case study source content")

    assert result == valid_result
    assert completion.call_count == 2
    assert completion.call_args_list[0].kwargs["max_tokens"] == 8192
    retry_call = completion.call_args_list[1].kwargs
    assert retry_call["temperature"] == 0.0
    assert "CRITICAL OUTPUT RETRY" in retry_call["messages"][0]["content"]


def test_content_structurer_retries_wrong_json_schema():
    from src.content_structurer import structure_case_study_content

    wrong_schema = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"heading":"Problem Statement"}'))]
    )
    valid_result = {
        "title": "Portfolio Analytics",
        "sections": [
            {"heading": "Problem Statement", "content": "Records contained duplicates."},
            {"heading": "Design and Implementation", "content": "The team built a dashboard."},
            {"heading": "Impact", "content": "Leaders gained visibility."},
        ],
    }
    valid_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(valid_result)))]
    )
    with (
        patch("src.content_structurer.get_llm_client", return_value=(object(), "test-model")),
        patch(
            "src.content_structurer.llm_chat_completion",
            side_effect=[wrong_schema, valid_response],
        ) as completion,
    ):
        result = structure_case_study_content("Case study source content")

    assert result == valid_result
    assert completion.call_count == 2
    assert "CRITICAL OUTPUT RETRY" in completion.call_args_list[1].kwargs["messages"][0]["content"]


def test_json_parser_accepts_trailing_model_commentary():
    from src.utils import parse_json_response

    raw = '''```json
    {"title":"Lease Data Transformation","sections":[]}
    ```
    Wait, I need to re-read the source before continuing.'''
    assert parse_json_response(raw) == {
        "title": "Lease Data Transformation",
        "sections": [],
    }


def test_content_structurer_splits_single_paragraph_fallback_units():
    from src.content_structurer import _source_units

    source = (
        "Lease Data Transformation  CRM records contained duplicates. "
        "The team built a validated data warehouse. "
        "Leaders gained on-demand portfolio insights."
    )
    assert _source_units(source) == [
        "Lease Data Transformation",
        "CRM records contained duplicates.",
        "The team built a validated data warehouse.",
        "Leaders gained on-demand portfolio insights.",
    ]


def test_content_structurer_uses_compact_indexed_fallback():
    from src.content_structurer import structure_case_study_content

    source = """Portfolio Analytics

Problem Statement

Records contained duplicates and phantom entries.

Design and Implementation

The team built a centralized portfolio dashboard.

Impact

Leaders gained trusted portfolio visibility."""
    invalid_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='```json\n{"title":"Truncated"'))]
    )
    indexed_result = {
        "title": "Portfolio Analytics",
        "sections": [
            {"heading": "Problem Statement", "unit_ids": [3]},
            {"heading": "Design and Implementation", "unit_ids": [5]},
            {"heading": "Impact", "unit_ids": [7]},
        ],
    }
    indexed_response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=json.dumps(indexed_result)))
        ]
    )
    fake_client = SimpleNamespace(max_tokens=4096)
    with (
        patch("src.content_structurer.get_llm_client", return_value=(fake_client, "test-model")),
        patch(
            "src.content_structurer.llm_chat_completion",
            side_effect=[invalid_response, invalid_response, indexed_response],
        ) as completion,
    ):
        result = structure_case_study_content(source)

    assert completion.call_count == 3
    assert completion.call_args_list[2].kwargs["max_tokens"] == 2048
    assert result == {
        "title": "Portfolio Analytics",
        "sections": [
            {"heading": "Problem Statement", "content": "Records contained duplicates and phantom entries."},
            {"heading": "Design and Implementation", "content": "The team built a centralized portfolio dashboard."},
            {"heading": "Impact", "content": "Leaders gained trusted portfolio visibility."},
        ],
    }


def test_content_structurer_recovers_omitted_explicit_section():
    from src.content_structurer import structure_case_study_content

    source = """Leasing Operations

Problem Statement

CRM records were unreliable.

TurnB Approach

Built a validated lease-data pipeline and Teams query agent.

Implications

Leaders could act earlier on renewal risk."""
    omitted_design = {
        "title": "Leasing Operations",
        "sections": [
            {"heading": "Problem Statement", "content": "CRM records were unreliable."},
            {"heading": "Design and Implementation", "content": ""},
            {"heading": "Impact", "content": ""},
        ],
    }
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(omitted_design)))]
    )
    with (
        patch("src.content_structurer.get_llm_client", return_value=(object(), "test-model")),
        patch("src.content_structurer.llm_chat_completion", return_value=response),
    ):
        result = structure_case_study_content(source)

    assert result["sections"][1]["content"] == (
        "Built a validated lease-data pipeline and Teams query agent."
    )
    assert result["sections"][2]["content"] == (
        "Leaders could act earlier on renewal risk."
    )


def test_hybrid_case_study_content_blocks():
    from src.layout_planner import plan_layout
    from src.slide_writer import (
        _normalize_blocks,
        content_blocks_to_body_text,
        section_to_content_blocks,
        source_content_to_blocks,
        write_slide_content,
    )

    structured = {
        "title": "AI-Enabled Power BI Dashboard",
        "sections": [
            {"heading": "Problem Statement", "content": "Context followed by challenges."},
            {"heading": "Design and Implementation", "content": "Approach groups and details."},
            {"heading": "Impact", "content": "Summary followed by outcomes."},
        ],
    }
    raw = {
        "title": "Invented title",
        "sections": [
            {
                "heading": "Problem Statement",
                "blocks": [
                    {"type": "paragraph", "text": "The global program scaled across regions and partners."},
                    {"type": "bullet", "text": "• No single source of truth existed."},
                    {"type": "paragraph", "text": "The client needed centralized visibility without additional program cost."},
                ],
            },
            {
                "heading": "Design and Implementation",
                "blocks": [
                    {"type": "subheading", "text": "**Identifying Stakeholder Needs & Gaps**"},
                    {"type": "bullet", "text": "Conducted stakeholder feedback sessions across multiple levels."},
                    {"type": "bullet", "text": "Defined the critical business questions the dashboard needed to answer."},
                    {"type": "subheading", "text": "Building a Centralized Power BI Dashboard:"},
                    {"type": "bullet", "text": "Delivered unified reporting across regions and training partners."},
                ],
            },
            {
                "heading": "Impact",
                "blocks": [
                    {"type": "paragraph", "text": "The dashboard transformed program oversight."},
                    {"type": "bullet", "text": "Improved planning through real-time utilization insight."},
                ],
            },
        ],
    }
    normalized = _normalize_blocks(raw, structured)
    assert normalized["title"] == structured["title"]
    problem = normalized["sections"][0]["blocks"]
    assert [block["type"] for block in problem] == ["paragraph", "bullet", "paragraph"]
    assert problem[1]["text"] == "No single source of truth existed."
    design = normalized["sections"][1]["blocks"]
    assert design[0] == {"type": "subheading", "text": "Identifying Stakeholder Needs & Gaps"}
    assert design[3] == {"type": "subheading", "text": "Building a Centralized Power BI Dashboard"}

    body = content_blocks_to_body_text(design)
    assert "**Identifying Stakeholder Needs & Gaps**" in body
    assert "• Conducted stakeholder feedback sessions" in body

    website_text = """Opening client context for the case study and its global program.\n\n- First challenge remained unresolved.\n- Second challenge limited forward-looking planning.\n\n**Proactive Risk Monitoring**\n\n- Introduced early warning indicators.\n"""
    parsed = source_content_to_blocks(website_text)
    assert [block["type"] for block in parsed] == [
        "paragraph", "bullet", "bullet", "subheading", "bullet"
    ]
    prompt_result = {
        "title": "Website-ready",
        "sections": [
            {
                "heading": "Problem Statement",
                "points": [
                    {"label": "First Challenge", "description": "The first challenge remained unresolved across the program."},
                    {"label": "Planning Constraint", "description": "The second challenge limited forward-looking planning for stakeholders."},
                    {"label": "Risk Monitoring", "description": "Early warning indicators enabled proactive risk monitoring."},
                ],
            },
            {"heading": "Design and Implementation", "points": []},
            {"heading": "Impact", "points": []},
        ],
    }
    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(prompt_result))
            )
        ]
    )
    with (
        patch("src.slide_writer.get_llm_client", return_value=(object(), "test-model")),
        patch("src.slide_writer.llm_chat_completion", return_value=fake_response) as completion,
    ):
        direct = write_slide_content({
            "title": "Website-ready",
            "sections": [
                {"heading": "Problem Statement", "content": website_text},
                {"heading": "Design and Implementation", "content": ""},
                {"heading": "Impact", "content": ""},
            ],
        })
    assert completion.call_count == 1, "Structured source content must not bypass the slide-writer prompt"
    assert direct["sections"][0]["points"] == prompt_result["sections"][0]["points"]
    rendered_blocks = section_to_content_blocks(direct["sections"][0])
    assert rendered_blocks[0] == {
        "type": "bullet",
        "text": "**First Challenge:** The first challenge remained unresolved across the program.",
    }
    assert [block["type"] for block in rendered_blocks] == ["bullet", "bullet", "bullet"]

    headline_plan = plan_layout(direct, _TEMPLATE_PROFILE, "auto")
    planned_sections = []
    for slide in headline_plan["slides"]:
        if slide.get("type") == "two_section":
            planned_sections.extend(slide.get("sections") or [])
        else:
            planned_sections.append(slide)
    problem_slide = next(
        slide for slide in planned_sections
        if slide.get("heading") == "Problem Statement"
    )
    assert problem_slide["blocks"][0]["text"] == rendered_blocks[0]["text"]

    # Rich website-style content must be split without dropping or reordering blocks.
    long_blocks = []
    for index in range(5):
        long_blocks.extend([
            {"type": "subheading", "text": f"Approach Area {index + 1}"},
            {
                "type": "bullet",
                "text": f"Delivered detailed capability {index + 1} across regions, partners, stakeholder groups, reporting workflows, and governance requirements.",
            },
            {
                "type": "bullet",
                "text": f"Enabled proactive action {index + 1} through standardized performance measures, tailored insights, and consistent interpretation.",
            },
            {
                "type": "bullet",
                "text": f"Replaced fragmented reporting process {index + 1} with centralized governance and accessible operational detail.",
            },
            {
                "type": "bullet",
                "text": f"Supported stakeholder decision path {index + 1} with early indicators, automated summaries, and focused interventions.",
            },
        ])
    rich = {
        "title": "Rich Case Study",
        "sections": [
            normalized["sections"][0],
            {"heading": "Design and Implementation", "blocks": long_blocks},
            normalized["sections"][2],
        ],
    }
    plan = plan_layout(rich, _TEMPLATE_PROFILE, "auto")
    assert plan["total_slides"] > 3
    planned_design = [
        block
        for slide in plan["slides"]
        if "TurnB Approach" in slide.get("heading", "")
        for block in slide.get("blocks", [])
    ]
    assert planned_design == long_blocks
    for slide in plan["slides"]:
        blocks = slide.get("blocks") or []
        assert not blocks or blocks[-1].get("type") != "subheading"

    # The existing application renderer must emit the hybrid hierarchy in PPTX.
    if os.path.exists("templates/sample_template.pptx"):
        import io
        from pptx import Presentation
        from src.ppt_generator import generate_case_study_ppt_bytes

        pptx_bytes, _ = generate_case_study_ppt_bytes(
            rich, "templates/sample_template.pptx", layout_plan=plan
        )
        presentation = Presentation(io.BytesIO(pptx_bytes))
        assert len(presentation.slides) == plan["total_slides"]
        visible_text = "\n".join(
            shape.text
            for slide in presentation.slides
            for shape in slide.shapes
            if hasattr(shape, "text_frame")
        )
        assert "TurnB Approach" in visible_text
        assert "Implications" in visible_text
        assert "Approach Area 1" in visible_text
        assert "• Delivered detailed capability 1" in visible_text

        headline_bytes, _ = generate_case_study_ppt_bytes(
            direct, "templates/sample_template.pptx", layout_plan=headline_plan
        )
        headline_presentation = Presentation(io.BytesIO(headline_bytes))
        headline_text = "\n".join(
            shape.text
            for slide in headline_presentation.slides
            for shape in slide.shapes
            if hasattr(shape, "text_frame")
        )
        assert "First Challenge: The first challenge remained unresolved" in headline_text


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
    test_content_structurer_retries_invalid_json,
    test_content_structurer_retries_wrong_json_schema,
    test_json_parser_accepts_trailing_model_commentary,
    test_content_structurer_splits_single_paragraph_fallback_units,
    test_content_structurer_uses_compact_indexed_fallback,
    test_content_structurer_recovers_omitted_explicit_section,
    test_hybrid_case_study_content_blocks,
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
