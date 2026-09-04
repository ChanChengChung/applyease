from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    password_hash: Mapped[str] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    email_verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Stored as an IANA timezone name (for example, ``Asia/Hong_Kong``).  The
    # browser settings page automatically offers the user's detected zone,
    # while keeping UTC as a safe server-side default.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default=text("'UTC'")
    )

    deadline_reminders_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )

    deadline_reminder_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7, server_default=text("7")
    )

    deadline_reminder_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=9, server_default=text("9")
    )

    @property
    def email_verified(self) -> bool:

        return self.email_verified_at is not None
