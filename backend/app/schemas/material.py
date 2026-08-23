from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceCitation(BaseModel):
    experience_id: int

    experience_title: str

    text: str

    claim: str = ""


class MaterialContent(BaseModel):
    material_type: Literal["resume", "cover_letter", "application_answer"]

    text: str

    character_count: int

    fact_check_passed: bool

    warnings: list[str] = Field(default_factory=list)

    sources: list[SourceCitation] = Field(default_factory=list)

    generation_method: str = "rules"

    max_characters: int | None = Field(default=None, ge=50, le=5000)
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en"


class MaterialRead(MaterialContent):
    id: int

    job_id: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnswerRequest(BaseModel):
    question: str = Field(min_length=5, max_length=3000)

    max_characters: int = Field(default=300, ge=50, le=5000)
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en"
    answer_tone: Literal["professional", "concise", "enthusiastic", "technical", "reflective"] = (
        "professional"
    )
    desired_content: str = Field(default="", max_length=1000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()

        if len(normalized) < 5:

            raise ValueError("question must contain at least 5 non-whitespace characters")

        return normalized

    @field_validator("desired_content")
    @classmethod
    def normalize_desired_content(cls, value: str) -> str:
        return " ".join(value.split())


class MaterialUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=50000)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:

            raise ValueError("material text cannot be blank")

        return normalized


class ResumeExportRequest(BaseModel):
    format: Literal["docx", "pdf"]

    template: Literal["classic", "modern", "compact"] = "classic"

    display_name: str = Field(min_length=1, max_length=100)

    contact_line: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=160)
    linkedin_url: str = Field(default="", max_length=500)
    github_url: str = Field(default="", max_length=500)

    include_sources: bool = False

    section_order: list[str] = Field(default_factory=list, max_length=30)

    hidden_sections: list[str] = Field(default_factory=list, max_length=30)

    # Appearance choices change presentation only. They never alter evidence
    # text, section selection, or the underlying saved material.
    font_style: Literal["default", "sans", "serif", "microsoft_yahei"] = "default"
    density: Literal["relaxed", "standard", "compact"] = "standard"
    accent: Literal["template", "navy", "black"] = "template"

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if not normalized:

            raise ValueError("display name cannot be blank")

        return normalized

    @field_validator("contact_line")
    @classmethod
    def normalize_contact_line(cls, value: str) -> str:

        return " ".join(value.split())

    @field_validator("email", "phone", "location", "linkedin_url", "github_url")
    @classmethod
    def normalize_contact_fields(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("section_order", "hidden_sections")
    @classmethod
    def valid_sections(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values]

        if any(not value or len(value) > 80 for value in cleaned) or len(set(cleaned)) != len(
            cleaned
        ):

            raise ValueError("section names must be unique non-empty labels")

        return cleaned
