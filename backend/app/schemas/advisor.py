from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdvisorMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=3000)


class AdvisorChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AdvisorMessage] = Field(default_factory=list, max_length=8)
    language: str = Field(default="zh-TW", pattern="^(en|zh-CN|zh-TW)$")
    active_page: str = Field(default="dashboard", min_length=1, max_length=64)
    active_job_id: int | None = Field(default=None, ge=1)


class AdvisorChatResponse(BaseModel):
    answer: str
    summary: str = ""
    sources: list[str] = Field(default_factory=list)
    evidence: list["AdvisorEvidence"] = Field(default_factory=list, max_length=5)
    gaps: list[str] = Field(default_factory=list, max_length=5)
    next_actions: list["AdvisorAction"] = Field(default_factory=list, max_length=4)
    suggested_prompts: list[str] = Field(default_factory=list)
    used_fallback: bool = False
    mode: Literal["ai", "fallback"] = "ai"


class AdvisorEvidence(BaseModel):
    type: Literal["experience", "job", "material", "tracker"]
    id: int | None = Field(default=None, ge=1)
    label: str = Field(min_length=1, max_length=240)
    detail: str = Field(default="", max_length=600)
    target_page: Literal["profile", "jobs", "builder", "tracker"] | None = None


class AdvisorAction(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    target_page: Literal["profile", "jobs", "builder", "form", "resources", "tracker"]
    target_id: int | None = Field(default=None, ge=1)


class AdvisorHistoryMessage(BaseModel):
    id: int
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    summary: str = ""
    sources: list[str] = Field(default_factory=list)
    evidence: list[AdvisorEvidence] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_actions: list[AdvisorAction] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    used_fallback: bool = False
    mode: Literal["ai", "fallback"] = "ai"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
