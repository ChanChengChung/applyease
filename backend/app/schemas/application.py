from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DetectQuestionsRequest(BaseModel):
    job_id: int = Field(gt=0)

    raw_text: str = Field(min_length=10, max_length=50000)

    @field_validator("raw_text")
    @classmethod
    def normalize_raw_text(cls, value: str) -> str:
        normalized = value.strip()

        if len(normalized) < 10:

            raise ValueError("raw_text must contain at least 10 non-whitespace characters")

        return normalized


class QuestionRead(BaseModel):
    id: int

    application_id: int

    question: str

    question_type: str

    max_characters: int

    required: bool

    answer: dict

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationRead(BaseModel):
    id: int

    job_id: int

    raw_text: str

    questions: list[QuestionRead]

    created_at: datetime


class ManualQuestionCreate(BaseModel):
    """A question added from the material builder, persisted as a draft."""

    job_id: int = Field(gt=0)
    question: str = Field(default="", max_length=5000)
    question_type: str = Field(default="general", max_length=80)
    max_characters: int = Field(default=300, ge=50, le=5000)
    required: bool = True
    answer_tone: Literal["professional", "concise", "enthusiastic", "technical", "reflective"] = "professional"
    desired_content: str = Field(default="", max_length=1000)

    @field_validator("question", "question_type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class ManualQuestionUpdate(BaseModel):
    question: str = Field(default="", max_length=5000)
    max_characters: int | None = Field(default=None, ge=50, le=5000)
    answer_tone: Literal["professional", "concise", "enthusiastic", "technical", "reflective"] | None = None
    desired_content: str | None = Field(default=None, max_length=1000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return value.strip()

    @field_validator("desired_content")
    @classmethod
    def normalize_desired_content(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AnswerRead(BaseModel):
    question_id: int

    question: str

    answer: str

    character_count: int

    max_characters: int

    fact_check_passed: bool

    warnings: list[str]

    sources: list[dict]

    status: str = "generated"

    generation_method: str = "rules"

    word_count: int = 0

    max_words: int | None = None

    template: Literal["concise_50", "standard_150", "detailed_300", "star"] | None = None

    recommended_template: Literal["concise_50", "standard_150", "detailed_300", "star"] | None = (
        None
    )

    template_target_characters: int | None = None

    structure_warnings: list[str] = Field(default_factory=list)


class AnswerGenerationRequest(BaseModel):
    template: Literal["auto", "concise_50", "standard_150", "detailed_300", "star"] = "auto"
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en"
    answer_tone: Literal["professional", "concise", "enthusiastic", "technical", "reflective"] = (
        "professional"
    )
    desired_content: str = Field(default="", max_length=1000)


class BatchAnswerRequest(BaseModel):
    regenerate: bool = False

    template: Literal["auto", "concise_50", "standard_150", "detailed_300", "star"] = "auto"
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en"
    answer_tone: Literal["professional", "concise", "enthusiastic", "technical", "reflective"] = (
        "professional"
    )
    desired_content: str = Field(default="", max_length=1000)


class BatchGenerationTask(BaseModel):
    """A pollable, short-lived batch-answer job for the application editor."""

    task_id: str
    status: Literal["queued", "running", "completed", "completed_with_errors", "failed"]
    completed: int = 0
    total: int = 0
    results: list[AnswerRead] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AnswerUpdate(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:

            raise ValueError("answer cannot be blank")

        return normalized


class DetectedFormField(BaseModel):
    field_id: str = Field(min_length=1, max_length=120)

    label: str = Field(default="", max_length=3000)

    name: str = Field(default="", max_length=300)

    html_id: str = Field(default="", max_length=300)

    placeholder: str = Field(default="", max_length=500)

    input_type: str = Field(default="text", max_length=30)

    max_characters: int | None = Field(default=None, ge=1, le=50000)

    options: list[str] = Field(default_factory=list, max_length=100)


class FillPreviewRequest(BaseModel):
    fields: list[DetectedFormField] = Field(min_length=1, max_length=300)


class FillPreviewItem(BaseModel):
    field_id: str

    label: str

    status: str

    answer: str = ""

    question_id: int | None = None

    question: str = ""

    warnings: list[str] = Field(default_factory=list)

    source_ids: list[int] = Field(default_factory=list)


class FillPreviewResponse(BaseModel):
    application_id: int

    items: list[FillPreviewItem]
