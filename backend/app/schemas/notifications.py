from __future__ import annotations

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


MailMode = Literal["file", "smtp", "disabled"]


class ReminderPreferencesRead(BaseModel):
    email: str
    timezone: str
    enabled: bool
    days_before: int
    local_hour: int
    delivery_mode: MailMode


class ReminderPreferencesUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    enabled: bool | None = None
    days_before: int | None = Field(default=None, ge=0, le=30)
    local_hour: int | None = Field(default=None, ge=0, le=23)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return normalized


class InterviewReviewCoachRequest(BaseModel):
    questions: str = Field(default="", max_length=12000)
    strengths: str = Field(default="", max_length=8000)
    improvements: str = Field(default="", max_length=8000)
    next_steps: str = Field(default="", max_length=8000)
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en"

    @field_validator("questions", "strengths", "improvements", "next_steps")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    def has_content(self) -> bool:
        return any(
            value.strip()
            for value in (self.questions, self.strengths, self.improvements, self.next_steps)
        )
