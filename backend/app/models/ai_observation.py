from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AIInvocation(Base):
    """Content-free telemetry for one provider attempt or terminal feature outcome."""

    __tablename__ = "ai_invocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)

    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    input_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # SQLAlchemy 2.0.36 cannot resolve Optional annotations on Python 3.14;

    # database nullability remains explicit on each column.

    output_characters: Mapped[int] = mapped_column(Integer, nullable=True)

    error_category: Mapped[str] = mapped_column(String(64), nullable=True)

    fallback_from: Mapped[str] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )


class AIUsageBucket(Base):
    """A tenant-scoped, database-backed window counter for costly AI actions.

    This is intentionally separate from telemetry.  Telemetry is best-effort;
    quota accounting must succeed before an external provider is contacted.
    """

    __tablename__ = "ai_usage_buckets"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_ai_usage_buckets_user_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False)

    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
