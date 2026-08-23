from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


ExperienceCategory = Literal[
    "personal", "education", "internship", "leadership", "research", "project"
]


class Achievement(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    source: str = Field(default="", max_length=500)

    verified: bool = False


class ExperienceBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    organization: str = Field(default="", max_length=200)

    description: str = Field(default="", max_length=10000)

    skills: list[str] = Field(default_factory=list)

    achievements: list[Achievement] = Field(default_factory=list)

    source_file: str = Field(default="", max_length=255)

    category: ExperienceCategory = "project"

    confirmed: bool = False

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:

            raise ValueError("title cannot be blank")

        return normalized

    @field_validator("organization", "description", "source_file")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:

        return value.strip()

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:

        return list(dict.fromkeys(skill.strip() for skill in value if skill.strip()))


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    organization: str | None = Field(default=None, max_length=200)

    description: str | None = Field(default=None, max_length=10000)

    skills: list[str] | None = None

    achievements: list[Achievement] | None = None

    category: ExperienceCategory | None = None

    confirmed: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_update_title(cls, value: str | None) -> str | None:

        if value is None:

            return None
        normalized = value.strip()

        if not normalized:

            raise ValueError("title cannot be blank")

        return normalized

    @field_validator("organization", "description")
    @classmethod
    def normalize_update_optional_text(cls, value: str | None) -> str | None:

        return value.strip() if value is not None else None

    @field_validator("skills")
    @classmethod
    def normalize_update_skills(cls, value: list[str] | None) -> list[str] | None:

        if value is None:

            return None

        return list(dict.fromkeys(skill.strip() for skill in value if skill.strip()))


class ExperienceBulkConfirm(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)

    confirmed: bool = True


class ExperienceBulkConfirmRead(BaseModel):
    updated: int

    missing_ids: list[int]


class ExperienceRead(ExperienceBase):
    id: int

    document_id: int | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperienceImpactJob(BaseModel):
    job_id: int
    title: str
    company: str
    requirements_supported: int = Field(ge=1)


class ExperienceImpactMaterial(BaseModel):
    material_id: int
    job_id: int
    material_type: str


class ExperienceImpactRead(BaseModel):
    experience_id: int
    confirmed: bool
    skills_available: list[str] = Field(default_factory=list)
    supported_jobs: list[ExperienceImpactJob] = Field(default_factory=list)
    material_references: list[ExperienceImpactMaterial] = Field(default_factory=list)
