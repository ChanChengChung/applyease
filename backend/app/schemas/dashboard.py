from datetime import date
from typing import Literal

from pydantic import BaseModel


class DashboardJob(BaseModel):
    id: int

    title: str

    company: str


class DashboardDeadline(BaseModel):
    id: int

    job_id: int | None = None

    company: str

    role: str

    deadline: date

    status: str

    kind: Literal["deadline", "follow_up", "interview"] = "deadline"

    is_overdue: bool = False


class DashboardStep(BaseModel):
    key: str

    label: str

    description: str

    status: Literal["complete", "current", "pending"]

    target: str


class DashboardAction(BaseModel):
    title: str

    description: str

    target: str


class DashboardJobWorkspace(DashboardJob):
    """A compact, per-role command card that keeps application work together."""

    match_score: int
    evidence_count: int
    missing_skills: list[str]
    material_count: int
    answers_ready: int
    questions_total: int
    tracker_status: str | None = None
    next_target: str
    # Progress is deliberately scoped to this target role. Keeping the stage
    # objects in the response prevents a global dashboard score from being
    # mistaken for readiness across several applications.
    progress: int
    steps: list[DashboardStep]


class DashboardSummary(BaseModel):
    experience_total: int

    confirmed_experiences: int

    pending_experiences: int

    job_total: int

    latest_job: DashboardJob | None

    material_count: int

    material_types: list[str]

    # The dashboard count represents saved versions for the newest target role.
    # Keep the newest type separately so the UI does not misleadingly show an
    # alphabetically-sorted collection of types as if it were the latest one.
    latest_material_type: str | None

    application_id: int | None

    questions_total: int

    answers_ready: int

    tracker_total: int

    active_applications: int

    upcoming_deadlines: list[DashboardDeadline]

    steps: list[DashboardStep]

    next_action: DashboardAction
    job_workspaces: list[DashboardJobWorkspace] = []
