from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobAnalyzeRequest(BaseModel):
    title: str = Field(default="Untitled role", max_length=200)

    company: str = Field(default="", max_length=200)

    description: str = Field(min_length=20, max_length=50000)

    @field_validator("title", "company")
    @classmethod
    def normalize_text(cls, value: str) -> str:

        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()

        if len(normalized) < 20:

            raise ValueError("description must contain at least 20 non-whitespace characters")

        return normalized


class JobSaveAnalyzedRequest(JobAnalyzeRequest):
    """Server-derived analysis a user has explicitly chosen to keep."""

    required_skills: list[str] = Field(default_factory=list, max_length=30)
    preferred_skills: list[str] = Field(default_factory=list, max_length=30)
    responsibilities: list[str] = Field(default_factory=list, max_length=20)
    qualifications: list[str] = Field(default_factory=list, max_length=20)

    @field_validator(
        "required_skills", "preferred_skills", "responsibilities", "qualifications"
    )
    @classmethod
    def normalize_analysis_items(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = " ".join(str(value).strip().split())[:500]
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                cleaned.append(text)
        return cleaned


class JobImportUrlRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2048)


class JobImportDraft(JobAnalyzeRequest):
    location: str = ""

    deadline: str = ""

    source_url: str = ""


class JobRead(JobAnalyzeRequest):
    id: int

    required_skills: list[str]

    preferred_skills: list[str]

    responsibilities: list[str]

    qualifications: list[str]

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Evidence(BaseModel):
    requirement: str

    experience_id: int

    experience_title: str

    evidence: str


class MatchReport(BaseModel):
    job: JobRead

    overall_score: int = Field(ge=0, le=100)

    matched_skills: list[str]

    missing_skills: list[str]

    evidence: list[Evidence]

    considered_experience_ids: list[int]

    matched_required_skills: list[str] = Field(default_factory=list)

    missing_required_skills: list[str] = Field(default_factory=list)

    matched_preferred_skills: list[str] = Field(default_factory=list)

    missing_preferred_skills: list[str] = Field(default_factory=list)

    score_breakdown: dict[str, int] = Field(default_factory=dict)

    warnings: list[str] = Field(default_factory=list)


class ReadinessItem(BaseModel):
    code: str
    severity: str
    title: str
    detail: str
    target: str
    params: dict[str, Any] = Field(default_factory=dict)


class ApplicationReadiness(BaseModel):
    job_id: int
    ready_to_submit: bool
    blockers: int
    warnings: int
    match_score: int
    missing_required_skills: list[str] = Field(default_factory=list)
    items: list[ReadinessItem]
    verdict: str = "prepare"
    verdict_reason: str = ""
    verdict_reason_code: str = ""
    verdict_reason_params: dict[str, Any] = Field(default_factory=dict)
    primary_action: ReadinessItem | None = None
