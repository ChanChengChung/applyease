"""Route-level quota boundary for provider-backed actions."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.services.ai_usage_limit_service import AIUsageLimitExceeded, consume_ai_usage


def _reserve(db: Session, category: str, maximum: int, window_seconds: int) -> None:
    try:
        consume_ai_usage(
            db,
            user_id=int(db.info.get("current_user_id") or 0),
            category=category,
            maximum=maximum,
            window_seconds=window_seconds,
        )
    except AIUsageLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="AI request limit reached. Please try again after the indicated delay.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


def reserve_ai_generation(db: Session) -> None:
    _reserve(
        db,
        "generation",
        settings.ai_generation_max_requests,
        settings.ai_generation_rate_limit_window_seconds,
    )


def reserve_cloud_ocr(db: Session) -> None:
    _reserve(
        db,
        "cloud_ocr",
        settings.cloud_ocr_max_requests,
        settings.cloud_ocr_rate_limit_window_seconds,
    )


def reserve_job_import(db: Session) -> None:
    _reserve(
        db,
        "job_import",
        settings.job_import_max_requests,
        settings.job_import_rate_limit_window_seconds,
    )
