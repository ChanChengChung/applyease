from datetime import datetime

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
    sources: list[str] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    used_fallback: bool = False


class AdvisorHistoryMessage(BaseModel):
    id: int
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    sources: list[str] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    used_fallback: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
