from datetime import datetime

from pydantic import BaseModel, Field


class AIProviderMetric(BaseModel):
    provider: str

    attempts: int

    successes: int

    errors: int

    success_rate: float = Field(ge=0, le=1)

    average_latency_ms: int

    p95_latency_ms: int


class AIFeatureMetric(BaseModel):
    feature: str

    total: int

    ai_successes: int

    rule_fallbacks: int

    errors: int

    success_rate: float = Field(ge=0, le=1)


class AIRecentEvent(BaseModel):
    feature: str

    provider: str

    model: str

    prompt_version: str

    status: str

    latency_ms: int

    error_category: str | None

    created_at: datetime


class AIMetrics(BaseModel):
    period_days: int

    generated_at: datetime

    total_feature_calls: int

    ai_successes: int

    rule_fallbacks: int

    errors: int

    success_rate: float = Field(ge=0, le=1)

    fallback_rate: float = Field(ge=0, le=1)

    provider_attempts: int

    prompt_versions: list[str]

    by_provider: list[AIProviderMetric]

    by_feature: list[AIFeatureMetric]

    recent_events: list[AIRecentEvent]

    privacy_notice: str
