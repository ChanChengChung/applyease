from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StarterLearningPlan(Base):
    """A persisted learning plan for students who do not yet have a target role.

    It is deliberately separate from ResearchPlan: research plans are grounded
    in a saved job, while this plan is an honest exploration starting point.
    """

    __tablename__ = "starter_learning_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    interest: Mapped[str] = mapped_column(Text)
    focus: Mapped[str] = mapped_column(String(300))
    headline: Mapped[str] = mapped_column(Text)
    first_action: Mapped[str] = mapped_column(Text)
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    resource_ids: Mapped[list] = mapped_column(JSON, default=list)
    used_fallback: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
