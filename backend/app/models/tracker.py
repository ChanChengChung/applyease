from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
