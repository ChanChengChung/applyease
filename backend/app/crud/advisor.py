from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.advisor import AdvisorConversationMessage


def list_recent(db: Session, user_id: int, limit: int = 40) -> list[AdvisorConversationMessage]:
    return list(
        reversed(
            db.scalars(
                select(AdvisorConversationMessage)
                .where(AdvisorConversationMessage.user_id == user_id)
                .order_by(AdvisorConversationMessage.id.desc())
                .limit(limit)
            ).all()
        )
    )


def append(
    db: Session,
    user_id: int,
    role: str,
    content: str,
    *,
    summary: str = "",
    sources: list[str] | None = None,
    evidence: list[dict] | None = None,
    gaps: list[str] | None = None,
    next_actions: list[dict] | None = None,
    suggested_prompts: list[str] | None = None,
    used_fallback: bool = False,
    mode: str = "ai",
) -> AdvisorConversationMessage:
    item = AdvisorConversationMessage(
        user_id=user_id,
        role=role,
        content=content,
        summary=summary,
        sources=sources or [],
        evidence=evidence or [],
        gaps=gaps or [],
        next_actions=next_actions or [],
        suggested_prompts=suggested_prompts or [],
        used_fallback=used_fallback,
        mode=mode if mode in {"ai", "fallback"} else "ai",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def clear(db: Session, user_id: int) -> None:
    db.execute(
        delete(AdvisorConversationMessage).where(AdvisorConversationMessage.user_id == user_id)
    )
    db.commit()
