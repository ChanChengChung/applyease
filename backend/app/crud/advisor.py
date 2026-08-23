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
    sources: list[str] | None = None,
    suggested_prompts: list[str] | None = None,
    used_fallback: bool = False,
) -> AdvisorConversationMessage:
    item = AdvisorConversationMessage(
        user_id=user_id,
        role=role,
        content=content,
        sources=sources or [],
        suggested_prompts=suggested_prompts or [],
        used_fallback=used_fallback,
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
