from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.layout_planner import plan_layout
from src.ppt_generator import generate_case_study_ppt_bytes
from src.slide_writer import _normalize_bullets

structured_content = {
    "title": "360 Degree View to Leasing Operations",
    "sections": [
        {
            "heading": "Problem Statement",
            "content": (
                "Duplicate records, phantom entries, and manual keying errors in the CRM "
                "undermined trust in lease data and led to double-counting of active leases. "
                "Leasing managers and directors built Excel reports manually, taking time away "
                "from strategic portfolio decisions. Operational and financial CRM data could not "
                "be correlated, hiding links between maintenance bottlenecks and lease renewal risk. "
                "Without real-time insight, teams missed renewal windows, delayed vacancy marketing, "
                "and extended vacancy durations."
            ),
        },
        {
            "heading": "Design and Implementation",
            "content": (
                "A data pipeline applied validation rules to remove duplicate and erroneous CRM records, "
                "creating a trusted reporting dataset. Interactive Power BI dashboards tracked revenue "
                "collection, leasing pipeline status, and occupancy trends using finalized prior-day data. "
                "A Microsoft Teams and M365 Copilot conversational agent enabled non-technical users to "
                "query lease data in natural language. Machine-learning models produced 12-month portfolio "
                "revenue forecasts and tenant churn risk scores."
            ),
        },
        {
            "heading": "Impact",
            "content": (
                "Leasing managers can query verified portfolio metrics in Microsoft Teams without manually "
                "compiling reports. The AI agent and Power BI dashboards show the same system-validated figures. "
                "Leadership can connect maintenance history with lease renewal probability before issues affect "
                "retention. Revenue forecasts and churn risk scores help the leasing team protect cash flow and "
                "optimize occupancy."
            ),
        },
    ],
}

# Local, deterministic check of the new label-and-description output contract.
# The production workflow obtains this same shape from the configured LLM.
local_model_output = {
    "sections": [
        {
            "heading": "Problem Statement",
            "points": [
                {"label": "Data Integrity", "description": "Duplicate CRM records and manual keying errors undermined trust in active lease data."},
                {"label": "Manual Reporting", "description": "Leasing managers built Excel reports manually instead of focusing on portfolio decisions."},
                {"label": "Operational Visibility", "description": "CRM data could not link maintenance bottlenecks with lease renewal risk."},
                {"label": "Decision Latency", "description": "Missing real-time insight delayed renewals, vacancy marketing, and maintenance responses."},
            ],
        },
        {
            "heading": "Design and Implementation",
            "points": [
                {"label": "Validated Data Pipeline", "description": "Validation rules removed duplicate and erroneous CRM records for reliable reporting."},
                {"label": "Power BI Dashboards", "description": "Interactive views tracked revenue, leasing pipeline status, and occupancy using finalized prior-day data."},
                {"label": "Conversational Agent", "description": "Microsoft Teams and M365 Copilot enabled non-technical users to query lease data in natural language."},
                {"label": "Predictive Models", "description": "Machine learning produced 12-month portfolio revenue forecasts and tenant churn risk scores."},
            ],
        },
        {
            "heading": "Impact",
            "points": [
                {"label": "On-Demand Metrics", "description": "Managers can query verified portfolio metrics in Microsoft Teams without compiling manual reports."},
                {"label": "Trusted Figures", "description": "The AI agent and Power BI dashboards show the same system-validated figures."},
                {"label": "Renewal Risk Visibility", "description": "Leadership can link maintenance history to lease renewal probability before retention issues grow."},
                {"label": "Proactive Management", "description": "Forecasts and churn risk scores help the leasing team protect cash flow and optimize occupancy."},
            ],
        },
    ],
}
slide_content = _normalize_bullets(local_model_output, structured_content)
layout_plan = plan_layout(slide_content, {}, "one_section_per_slide")
pptx, _ = generate_case_study_ppt_bytes(
    slide_content,
    str(ROOT / "templates" / "sample_template.pptx"),
    layout_plan=layout_plan,
)

candidate = ROOT / ".ppt-build" / "point-format-check-candidate.pptx"
candidate.write_bytes(pptx)
(ROOT / ".ppt-build" / "point-format-check-content.json").write_text(
    json.dumps(slide_content, indent=2), encoding="utf-8"
)
print(json.dumps({"candidate": str(candidate), "layout_plan": layout_plan, "content": slide_content}, indent=2))
