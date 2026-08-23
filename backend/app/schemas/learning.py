from datetime import datetime
from pydantic import BaseModel, Field


class LearningSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    topic: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=5, ge=1, le=10)


class LearningCitation(BaseModel):
    id: int
    title: str
    topic: str
    content: str
    source_name: str
    source_url: str
    score: float


class LearningSearchResponse(BaseModel):
    query: str
    citations: list[LearningCitation]
    boundary: str = (
        "Public learning knowledge only; it is never used as applicant experience or application evidence."
    )


class LearningAnswerResponse(LearningSearchResponse):
    answer: str


class CurriculumModule(BaseModel):
    order: int
    slug: str
    title: str
    topics: list[str]
    outcome: str
    exercise: str
    acceptance: list[str]


class RAGEvaluationResult(BaseModel):
    query: str
    expected_slug: str
    retrieved_slug: str | None
    passed: bool


class RAGEvaluationResponse(BaseModel):
    total: int
    passed: int
    results: list[RAGEvaluationResult]
