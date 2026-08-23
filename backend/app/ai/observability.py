from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraceContext:
    request_id: str

    feature: str

    prompt_version: str

    input_characters: int


_user_id: ContextVar[int | None] = ContextVar("ai_user_id", default=None)
_trace: ContextVar[TraceContext | None] = ContextVar("ai_trace", default=None)


@contextmanager
def ai_user_scope(user_id: int | None) -> Iterator[None]:
    token = _user_id.set(user_id)

    try:

        yield

    finally:
        _user_id.reset(token)


@contextmanager
def ai_trace(feature: str, prompt_version: str, input_characters: int) -> Iterator[TraceContext]:
    context = TraceContext(
        str(uuid.uuid4()), feature[:64], prompt_version[:64], max(input_characters, 0)
    )

    token = _trace.set(context)

    try:

        yield context

    finally:
        _trace.reset(token)


def current_trace(feature: str, prompt_version: str, input_characters: int) -> TraceContext:

    return _trace.get() or TraceContext(
        str(uuid.uuid4()), feature[:64], prompt_version[:64], max(input_characters, 0)
    )


def error_category(exc: BaseException) -> str:
    """Return a bounded category, never an exception message that could contain user content."""

    name = type(exc).__name__

    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    return re.sub(r"[^a-z0-9_]+", "_", snake).strip("_")[:64] or "unknown_error"


def record_event(
    *,
    trace: TraceContext,
    event_type: str,
    provider: str,
    model: str = "",
    status: str,
    latency_ms: int = 0,
    attempt: int = 1,
    output_characters: int | None = None,
    category: str | None = None,
    fallback_from: str | None = None,
) -> None:
    user_id = _user_id.get()

    if user_id is None:

        return

    try:
        # Imports stay local to prevent provider/model/session import cycles.

        from app.db.session import SessionLocal

        from app.models.ai_observation import AIInvocation

        with SessionLocal() as db:
            db.add(
                AIInvocation(
                    user_id=user_id,
                    request_id=trace.request_id,
                    event_type=event_type[:32],
                    feature=trace.feature,
                    provider=provider[:32],
                    model=model[:120],
                    prompt_version=trace.prompt_version,
                    status=status[:32],
                    latency_ms=max(int(latency_ms), 0),
                    attempt=max(int(attempt), 1),
                    input_characters=trace.input_characters,
                    output_characters=(
                        max(int(output_characters), 0) if output_characters is not None else None
                    ),
                    error_category=category[:64] if category else None,
                    fallback_from=fallback_from[:32] if fallback_from else None,
                )
            )

            db.commit()

    except Exception as exc:  # Telemetry must never break an application workflow.
        logger.warning("AI telemetry write failed (%s)", type(exc).__name__)


def record_outcome(
    *,
    status: str,
    provider: str,
    category: str | None = None,
    fallback_from: str | None = None,
    latency_started: float | None = None,
) -> None:
    trace = _trace.get()

    if trace is None:

        return
    latency = (
        round((time.monotonic() - latency_started) * 1000) if latency_started is not None else 0
    )

    record_event(
        trace=trace,
        event_type="feature_outcome",
        provider=provider,
        status=status,
        latency_ms=latency,
        category=category,
        fallback_from=fallback_from,
    )
