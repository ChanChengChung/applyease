from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200))

    organization: Mapped[str] = mapped_column(String(200), default="")

    description: Mapped[str] = mapped_column(Text, default="")

    skills: Mapped[list] = mapped_column(JSON, default=list)

    achievements: Mapped[list] = mapped_column(JSON, default=list)

    source_file: Mapped[str] = mapped_column(String(255), default="")

    # This is deliberately stored with the evidence rather than inferred only in
    # the browser.  It keeps an AI-extracted category stable after an edit and
    # makes the Experience Bank browsable in every client.
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="project")

    confirmed: Mapped[bool] = mapped_column(default=False)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    document = relationship("Document", back_populates="experiences")
