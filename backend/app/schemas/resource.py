from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectSpec(BaseModel):
    title: str

    task: str

    estimated_days: int = Field(ge=1, le=90)

    deliverables: list[str]

    completion_criteria: list[str]

    cv_bullet_template: str


class ResourceRead(BaseModel):
    id: int

    title: str

    url: str

    provider: str

    skills: list[str]

    difficulty: str

    duration_hours: int

    free: bool

    description: str

    project: ProjectSpec

    verified: bool

    link_status: str = "unchecked"

    last_checked_at: datetime | None = None

    completed: bool = False

    match_score: int = Field(default=0, ge=0, le=100)

    matched_skills: list[str] = Field(default_factory=list)

    recommendation_reason: str = ""

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceComplete(BaseModel):
    completed: bool


class ResourceFeedbackCreate(BaseModel):
    category: Literal["broken_link", "outdated_content", "other"] = "broken_link"
    message: str = Field(min_length=3, max_length=1000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("message must contain at least 3 non-whitespace characters")
        return normalized


class ResourceExperienceDraftRequest(BaseModel):
    """User-authored evidence required before a learning plan can become an experience draft."""

    reflection: str = Field(min_length=10, max_length=6000)

    @field_validator("reflection")
    @classmethod
    def normalize_reflection(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 10:
            raise ValueError("reflection must contain at least 10 characters")
        return normalized


class StarterPlanRequest(BaseModel):
    """A no-CV, no-job entry point for students who are still exploring."""

    interest: str = Field(min_length=8, max_length=1000)
    weekly_hours: int = Field(default=3, ge=1, le=30)
    weeks: int = Field(default=4, ge=1, le=16)
    experience_level: Literal["none", "basic", "some"] = "none"
    goal: Literal["explore", "portfolio", "competition"] = "explore"
    # `competition` is retained for saved plans created before the UI wording
    # changed. New plans use `feedback` for the reflective learning route.
    preferred_formats: list[Literal["project", "competition", "feedback", "course"]] = Field(
        default_factory=lambda: ["project"]
    )
    experience_level_other: str = Field(default="", max_length=300)
    goal_other: str = Field(default="", max_length=300)
    preferred_format_other: str = Field(default="", max_length=300)
    language: Literal["en", "zh-CN", "zh-TW"] = "zh-CN"

    @field_validator("interest")
    @classmethod
    def normalize_interest(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("interest must contain at least 8 non-whitespace characters")
        return value

    @field_validator("experience_level_other", "goal_other", "preferred_format_other")
    @classmethod
    def normalize_optional_context(cls, value: str) -> str:
        return value.strip()

    @property
    def max_total_hours(self) -> int:
        return min(self.weekly_hours * self.weeks, 200)


class StarterPlanRead(BaseModel):
    id: int
    interest: str
    focus: str
    headline: str
    first_action: str
    milestones: list[str]
    resources: list[ResourceRead]
    used_fallback: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StarterPlanUpdate(BaseModel):
    """Human edits to a saved plan; recommended resources remain source-backed."""

    focus: str = Field(min_length=1, max_length=300)
    headline: str = Field(min_length=1, max_length=2000)
    first_action: str = Field(min_length=1, max_length=2000)
    milestones: list[str] = Field(min_length=1, max_length=20)

    @field_validator("focus", "headline", "first_action")
    @classmethod
    def normalize_plan_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("milestones")
    @classmethod
    def normalize_milestones(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one milestone is required")
        if any(len(value) > 1000 for value in cleaned):
            raise ValueError("each milestone must be at most 1000 characters")
        return cleaned


class StarterPlanRefineRequest(BaseModel):
    """Regenerate an exploration plan from the student's saved intent."""

    weekly_hours: int = Field(ge=1, le=30)
    weeks: int = Field(ge=1, le=16)
    goal: Literal["skills", "project", "interview"] = "skills"
    learning_style: Literal["hands_on", "guided", "intensive"] = "hands_on"
    language: Literal["en", "zh-CN", "zh-TW"] = "zh-TW"

    @property
    def max_total_hours(self) -> int:
        return min(self.weekly_hours * self.weeks, 200)


class ResearchPlanRequest(BaseModel):
    job_id: int = Field(gt=0)
    weekly_hours: int = Field(ge=1, le=30)
    weeks: int = Field(ge=1, le=16)
    goal: Literal["skills", "project", "interview"] = "project"
    learning_style: Literal["hands_on", "guided", "intensive"] = "hands_on"
    language: Literal["en", "zh-CN", "zh-TW"] = "zh-TW"


class ResearchSource(BaseModel):
    title: str
    url: str


class ResearchPlanRead(BaseModel):
    id: int
    job_id: int
    profile_summary: str
    gaps: list[str]
    method: list[str]
    sources: list[ResearchSource]
    searched_at: datetime
    used_fallback: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResearchPlanUpdate(BaseModel):
    profile_summary: str = Field(min_length=1, max_length=3000)
    gaps: list[str] = Field(default_factory=list, max_length=8)
    method: list[str] = Field(default_factory=list, max_length=8)
    sources: list[ResearchSource] = Field(default_factory=list, max_length=12)
