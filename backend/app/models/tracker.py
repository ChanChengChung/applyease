from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class TrackedApplication(Base):
    __tablename__ = "tracked_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company: Mapped[str] = mapped_column(String(200))

    role: Mapped[str] = mapped_column(String(200))

    job_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)

    deadline: Mapped[datetime] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(40), default="saved")

    interview_date: Mapped[datetime] = mapped_column(Date, nullable=True)

    follow_up_at: Mapped[datetime] = mapped_column(Date, nullable=True)

    notes: Mapped[str] = mapped_column(Text, default="")

    # Structured interview reflection stays with the application record so it
    # can be reviewed before the next interview, rather than living only in
    # transient browser state.
    interview_review: Mapped[dict] = mapped_column(JSON, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class DeadlineReminderDelivery(Base):
    """Idempotency ledger for deadline reminder emails.

    A unique key per user/application/deadline means a second scheduler worker
    or a repeated scan cannot send the same reminder twice.
    """

    __tablename__ = "deadline_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tracked_application_id",
            "kind",
            "due_date",
            name="uq_deadline_reminder_delivery",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tracked_application_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="deadline")
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
