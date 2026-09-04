from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ManualJobBriefRequest(BaseModel):
    """Structured facts supplied when no usable public job posting exists."""

    title: str = Field(default="Untitled role", max_length=200)
    company: str = Field(default="", max_length=200)
    job_category: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    responsibilities: list[str] = Field(default_factory=list, max_length=20)
    additional_details: str = Field(default="", max_length=10000)

    @field_validator("title", "company", "job_category", "location", "additional_details")
    @classmethod
    def normalize_manual_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("required_skills", "responsibilities")
    @classmethod
    def normalize_manual_items(cls, values: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                " ".join(str(value).strip().split())[:500]
                for value in values
                if str(value).strip()
            )
        )

    def to_description(self) -> str:
        lines = [
            f"Job category: {self.job_category}" if self.job_category else "",
            f"Location: {self.location}" if self.location else "",
            f"Required skills: {', '.join(self.required_skills)}" if self.required_skills else "",
            *(f"Key responsibility: {item}" for item in self.responsibilities),
            self.additional_details,
        ]
        return "\n".join(line for line in lines if line).strip()

    @model_validator(mode="after")
    def require_sufficient_role_context(self):
        if len(self.to_description()) < 20:
            raise ValueError("manual job brief must contain at least 20 characters of role context")
        return self


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


class JobImportDraft(BaseModel):
    """A reviewable import result; the user may need to complete a dynamic page."""

    title: str = Field(default="Untitled role", max_length=200)
    company: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=50000)
    location: str = ""
    deadline: str = ""
    source_url: str = ""
    # JavaScript-rendered and anti-bot career pages can expose a page shell
    # without exposing the actual JD to a server-side importer.  This is an
    # expected, recoverable state rather than a malformed user request.
    needs_manual_description: bool = False


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


class EligibilityCheck(BaseModel):
    """A hard application constraint extracted from the job description."""

    kind: Literal["education", "graduation", "location", "work_authorization", "availability"]
    requirement: str
    status: Literal["met", "needs_confirmation"] = "needs_confirmation"
    evidence: str = ""


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

    eligibility_checks: list[EligibilityCheck] = Field(default_factory=list)

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
