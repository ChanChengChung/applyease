from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    job_id: Mapped[int] = mapped_column(Integer, index=True)

    raw_text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ApplicationQuestion(Base):
    __tablename__ = "application_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    application_id: Mapped[int] = mapped_column(Integer, index=True)

    question: Mapped[str] = mapped_column(Text)

    question_type: Mapped[str] = mapped_column(Text, default="general")

    max_characters: Mapped[int] = mapped_column(Integer, default=300)

    required: Mapped[bool] = mapped_column(default=True)

    answer: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
