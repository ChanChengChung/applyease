from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (UniqueConstraint("user_id", "sha256", name="uq_documents_user_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    filename: Mapped[str] = mapped_column(String(255))

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")

    text_length: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    experiences = relationship(
        "Experience", back_populates="document", cascade="all, delete-orphan"
    )
