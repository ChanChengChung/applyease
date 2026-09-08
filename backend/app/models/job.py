from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), default="Untitled role")

    company: Mapped[str] = mapped_column(String(200), default="")

    # Preserve the public posting URL so tracked applications can reopen it.
    source_url: Mapped[str] = mapped_column(String(2048), default="")

    description: Mapped[str] = mapped_column(Text)

    required_skills: Mapped[list] = mapped_column(JSON, default=list)

    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)

    responsibilities: Mapped[list] = mapped_column(JSON, default=list)

    qualifications: Mapped[list] = mapped_column(JSON, default=list)

    # Only roles explicitly reviewed/imported from Opportunity Radar are
    # promoted into the role-library folders. Preview and manually saved
    # analyses remain private workspace drafts until that decision is made.
    library_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
