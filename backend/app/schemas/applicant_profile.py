from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ApplicantProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)

    contact_line: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=160)
    linkedin_url: str = Field(default="", max_length=500)
    github_url: str = Field(default="", max_length=500)

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if not normalized:

            raise ValueError("display name cannot be blank")

        return normalized

    @field_validator("contact_line")
    @classmethod
    def normalize_contact(cls, value: str) -> str:

        return " ".join(value.split())

    @field_validator("email", "phone", "location", "linkedin_url", "github_url")
    @classmethod
    def normalize_structured_contact(cls, value: str) -> str:
        return " ".join(value.split())


class ApplicantProfileRead(ApplicantProfileUpdate):
    updated_at: datetime
