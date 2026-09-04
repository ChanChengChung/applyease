"""Database-backed quotas for operations that can invoke an AI provider.

The counter is held per account and category.  ``SELECT ... FOR UPDATE`` makes
the update serializable for the same account on PostgreSQL, unlike an
in-process limiter which would be bypassed by additional Uvicorn workers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings

from app.models.ai_observation import AIUsageBucket


class AIUsageLimitExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__("AI request quota exceeded")


def usage_summary(db: Session, user_id: int) -> dict:
    """Read current quota windows for the account-facing usage endpoint."""
    now = utc_now()
    limits = {
        "generation": (settings.ai_generation_max_requests, settings.ai_generation_rate_limit_window_seconds),
        "cloud_ocr": (settings.cloud_ocr_max_requests, settings.cloud_ocr_rate_limit_window_seconds),
        "job_import": (settings.job_import_max_requests, settings.job_import_rate_limit_window_seconds),
    }
    buckets = {
        bucket.category: bucket
        for bucket in db.scalars(select(AIUsageBucket).where(AIUsageBucket.user_id == user_id)).all()
    }
    result = {}
    for category, (maximum, window_seconds) in limits.items():
        bucket = buckets.get(category)
        active = bool(bucket and now - bucket.window_started_at < timedelta(seconds=window_seconds))
        used = bucket.request_count if active else 0
        result[category] = {
            "used": used, "limit": maximum, "remaining": max(0, maximum - used),
            "window_seconds": window_seconds,
            "window_started_at": bucket.window_started_at if active else None,
        }
    return result


def utc_now() -> datetime:
    # Keep timestamps compatible with the SQLite test database and PostgreSQL.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def consume_ai_usage(
    db: Session,
    *,
    user_id: int,
    category: str,
    maximum: int,
    window_seconds: int,
    now: datetime | None = None,
) -> None:
    """Atomically reserve one unit before an external request is made.

    A failed provider call is deliberately still charged: otherwise retries or
    malformed requests could be used to exhaust a provider free tier.
    """
    if user_id <= 0:
        # All protected routes set the current user.  Failing closed protects
        # production if a new route is accidentally wired incorrectly.
        raise RuntimeError("AI usage requires an authenticated user")
    if maximum <= 0 or window_seconds <= 0:
        raise ValueError("AI usage limits must be positive")

    now = now or utc_now()
    category = category[:32]
    window = timedelta(seconds=window_seconds)

    def _locked_bucket() -> AIUsageBucket | None:
        return db.scalar(
            select(AIUsageBucket)
            .where(
                AIUsageBucket.user_id == user_id,
                AIUsageBucket.category == category,
            )
            .with_for_update()
        )

    bucket = _locked_bucket()
    if bucket is None:
        bucket = AIUsageBucket(
            user_id=user_id, category=category, window_started_at=now, request_count=1
        )
        db.add(bucket)
        try:
            db.commit()
            return
        except IntegrityError:
            # Two first requests can race before either row exists.  Re-read
            # and lock the winning row rather than granting a second request.
            db.rollback()
            bucket = _locked_bucket()
            if bucket is None:  # defensive: surface a database problem safely
                raise

    elapsed = now - bucket.window_started_at
    if elapsed >= window:
        bucket.window_started_at = now
        bucket.request_count = 1
        db.commit()
        return

    if bucket.request_count >= maximum:
        retry_after = int((window - elapsed).total_seconds())
        db.rollback()  # release the row lock without changing the counter
        raise AIUsageLimitExceeded(retry_after)

    bucket.request_count += 1
    db.commit()
