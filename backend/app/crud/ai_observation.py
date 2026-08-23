from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_observation import AIInvocation


def list_since(db: Session, since: datetime) -> list[AIInvocation]:

    return list(
        db.scalars(
            select(AIInvocation)
            .where(AIInvocation.created_at >= since)
            .order_by(AIInvocation.created_at.desc(), AIInvocation.id.desc())
        ).all()
    )


def prune_before(db: Session, cutoff: datetime) -> int:
    result = db.execute(delete(AIInvocation).where(AIInvocation.created_at < cutoff))

    db.commit()

    return int(result.rowcount or 0)
