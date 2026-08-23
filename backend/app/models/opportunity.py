from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OpportunitySearch(Base):
    """A user-owned, auditable public-web opportunity research run.

    We persist the reviewed result rather than silently re-running web searches
    whenever a page loads. This keeps the student's search history visible and
    avoids unexpected Gemini usage.
    """

    __tablename__ = "opportunity_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    career_goal: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    work_preference: Mapped[str] = mapped_column(String(40), default="")
    timing: Mapped[str] = mapped_column(String(160), default="")
    language: Mapped[str] = mapped_column(String(12), default="en")
    # The student may combine AI-grounded research with keyless official-ATS
    # discovery. Persist this exact choice so result messaging is auditable.
    search_modes: Mapped[list] = mapped_column(JSON, default=list)
    # Exact confirmed evidence IDs deliberately selected for this search. This
    # makes the web-search consent auditable instead of an opaque "all CV"
    # action, and lets a student revisit what was actually shared.
    experience_ids: Mapped[list] = mapped_column(JSON, default=list)
    opportunities: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    unavailable_reason: Mapped[str] = mapped_column(String(80), default="")
    strategy_outcomes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
