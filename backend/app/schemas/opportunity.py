from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.job import JobRead
from app.schemas.tracker import TrackerRead


class OpportunitySearchRequest(BaseModel):
    """A deliberate, privacy-aware public job research request."""

    career_goal: str = Field(default="", max_length=1200)
    location: str = Field(default="", max_length=160)
    work_preference: Literal["any", "onsite", "hybrid", "remote"] = "any"
    timing: str = Field(default="", max_length=160)
    language: Literal["en", "zh-CN", "zh-TW"] = "zh-CN"
    search_modes: list[Literal["ai", "official_ats"]] = Field(
        default_factory=lambda: ["ai"], min_length=1, max_length=2
    )
    experience_ids: list[int] = Field(default_factory=list, max_length=500)
    consent_to_web_search: bool = False
    limit: int = Field(default=5, ge=3, le=8)

    @field_validator("career_goal", "location", "timing")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("search_modes")
    @classmethod
    def unique_search_modes(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class OpportunitySource(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    url: str = Field(pattern=r"^https://", max_length=2048)


class OpportunityMatch(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=200)
    employment_type: str = Field(default="", max_length=100)
    why_match: str = Field(min_length=1, max_length=1000)
    evidence_used: list[str] = Field(default_factory=list, max_length=5)
    gaps_to_address: list[str] = Field(default_factory=list, max_length=5)
    next_step: str = Field(default="", max_length=500)
    source_title: str = Field(min_length=1, max_length=240)
    source_url: str = Field(pattern=r"^https://", max_length=2048)


class OpportunitySearchRead(BaseModel):
    id: int
    career_goal: str
    location: str
    work_preference: str
    timing: str
    language: str
    search_modes: list[str] = Field(default_factory=list)
    experience_ids: list[int] = Field(default_factory=list)
    opportunities: list[OpportunityMatch] = Field(default_factory=list)
    sources: list[OpportunitySource] = Field(default_factory=list)
    used_fallback: bool = False
    unavailable_reason: str = ""
    strategy_outcomes: list[dict] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityImportTrackedRead(BaseModel):
    """A reviewed public role imported into both job analysis and tracking."""

    job: JobRead
    tracker: TrackerRead
