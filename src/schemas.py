"""Data models for the autonomous case study agent."""
from dataclasses import dataclass, field, fields as dc_fields
from typing import Optional


@dataclass
class CaseStudyState:
    """Structured representation of a case study in progress."""

    # Core content
    title: str = ""
    raw_content: str = ""
    merged_content: str = ""

    # Problem Statement fields
    client_context: str = ""
    business_problem: str = ""
    current_process: str = ""
    pain_points: str = ""
    why_it_matters: str = ""

    # Design and Implementation fields
    turnb_solution: str = ""
    implementation_details: str = ""
    tools_technologies: str = ""
    data_sources: str = ""
    workflow_details: str = ""
    governance_security: str = ""

    # Impact fields
    impact_summary: str = ""
    measurable_results: str = ""
    adoption_feedback: str = ""
    business_value: str = ""

    # Agent metadata
    topic: str = ""
    section_coverage: dict = field(default_factory=dict)
    review: Optional[dict] = None
    layout_preference: str = "auto"
    tone: str = "professional"
    audience: str = "leadership"

    def update_from_content(self, content: str) -> None:
        self.merged_content = content
        if not self.raw_content:
            self.raw_content = content

    def set_title(self, title: str) -> None:
        self.title = (title or "").strip()

    def update_review(self, review: dict) -> None:
        self.review = review

    def update_section_coverage(self, coverage: dict) -> None:
        self.section_coverage = dict(coverage or {})

    def build_review_context(self) -> str:
        """
        Compile all accumulated state into a single string for review.
        Title is prepended only if not already present in merged content.
        """
        parts: list[str] = []
        title = self.title.strip()
        content = (self.merged_content or self.raw_content or "").strip()

        if title and f"Title: {title}" not in content:
            parts.append(f"Title: {title}")

        if self.topic.strip() and self.topic.strip().lower() not in content.lower():
            parts.append(f"Topic: {self.topic.strip()}")

        if content:
            parts.append(content)

        return "\n\n".join(parts).strip()

    def build_generation_context(self) -> str:
        """Build a PPT-generation-ready document from accumulated state."""
        parts: list[str] = []
        title = self.title.strip()
        content = (self.merged_content or self.raw_content or "").strip()

        if title and f"Title: {title}" not in content:
            parts.append(f"Title: {title}")

        if content:
            parts.append(content)

        return "\n\n".join(parts).strip()

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in dc_fields(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "CaseStudyState":
        valid = {f.name for f in dc_fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class AgentResponse:
    """Return value from agent_controller.handle_user_message."""

    # Messages to append to chat history (role/content/msg_type/review/download_path)
    assistant_messages: list = field(default_factory=list)

    # If set, update session phase to this value
    new_phase: Optional[str] = None

    # If True, chat layer should run generate after applying this response
    trigger_generate: bool = False

    # Arbitrary session_state key-value updates
    # (original_content, combined_content, review_result, layout_preference, etc.)
    state_updates: dict = field(default_factory=dict)

    # Debug info for sidebar panel (detected_intent, topic, section_coverage, etc.)
    debug_info: dict = field(default_factory=dict)
