from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATUSES = ("saved", "applied", "assessment", "interview", "offer", "rejected", "withdrawn")
Status = Literal["saved", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]


class TrackerCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)

    role: str = Field(min_length=1, max_length=200)

    job_id: int | None = Field(default=None, gt=0)

    deadline: date | None = None

    status: Status = "saved"

    interview_date: date | None = None

    follow_up_at: date | None = None

    notes: str = Field(default="", max_length=10000)

    @field_validator("company", "role")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:

            raise ValueError("company and role cannot be blank")

        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:

        return value.strip()


class TrackerUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=200)

    role: str | None = Field(default=None, min_length=1, max_length=200)

    job_id: int | None = Field(default=None, gt=0)

    deadline: date | None = None

    status: Status | None = None

    interview_date: date | None = None

    follow_up_at: date | None = None

    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("company", "role")
    @classmethod
    def normalize_required_optional_text(cls, value: str | None) -> str | None:

        if value is None:

            return None
        normalized = value.strip()

        if not normalized:

            raise ValueError("company and role cannot be blank")

        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_optional_notes(cls, value: str | None) -> str | None:

        return value.strip() if value is not None else None


class TrackerRead(TrackerCreate):
    id: int

    created_at: datetime

    is_overdue: bool = False

    is_follow_up_due: bool = False

    next_action: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TrackerSummary(BaseModel):
    total: int

    by_status: dict[str, int]

    active: int

    overdue: int

    follow_ups_due: int

    next_action: TrackerRead | None = None


class TrackerReminder(BaseModel):
    application_id: int
    kind: Literal["deadline", "follow_up", "interview"]
    due_date: date
    state: Literal["overdue", "today", "upcoming"]
    company: str
    role: str
    title: str


class ApplicationWorkspaceRead(BaseModel):
    """One honest, job-linked view for the Tracker workspace card."""

    application_id: int
    job_id: int | None = None
    match_score: int | None = None
    evidence_count: int = 0
    missing_skills: list[str] = Field(default_factory=list)
    material_types: list[str] = Field(default_factory=list)
    questions_total: int = 0
    answers_ready: int = 0
    # A saved research plan is the bridge from a role's identified gaps to an
    # actionable learning path.  Keep it as lightweight metadata here: the
    # full editable plan remains owned by the Learning Plan workspace.
    learning_plan_id: int | None = None
    learning_plan_steps: int = 0
    learning_plan_sources: int = 0
    learning_plan_updated_at: datetime | None = None
    application_status: str = "saved"
    material_versions: list["MaterialVersionRead"] = Field(default_factory=list)


class MaterialVersionRead(BaseModel):
    """Metadata for comparison only; this deliberately makes no causal claim."""

    id: int
    material_type: str
    generation_method: str
    created_at: datetime
    fact_check_passed: bool
    source_count: int
