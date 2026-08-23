from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(250))

    url: Mapped[str] = mapped_column(String(500))

    provider: Mapped[str] = mapped_column(String(100))

    skills: Mapped[list] = mapped_column(JSON, default=list)

    difficulty: Mapped[str] = mapped_column(String(30), default="beginner")

    duration_hours: Mapped[int] = mapped_column(Integer, default=5)

    free: Mapped[bool] = mapped_column(Boolean, default=True)

    description: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[dict] = mapped_column(JSON, default=dict)

    verified: Mapped[bool] = mapped_column(Boolean, default=True)

    link_status: Mapped[str] = mapped_column(String(20), default="unchecked")

    last_checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ResourceProgress(Base):
    __tablename__ = "resource_progress"

    __table_args__ = (
        UniqueConstraint("user_id", "resource_id", name="uq_resource_progress_user_resource"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    resource_id: Mapped[int] = mapped_column(Integer, index=True)

    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ResourceFeedback(Base):
    __tablename__ = "resource_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(30), default="broken_link")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
