from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.opportunity import OpportunitySearch


def create(db: Session, **values) -> OpportunitySearch:
    item = OpportunitySearch(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get(db: Session, search_id: int) -> OpportunitySearch | None:
    return db.get(OpportunitySearch, search_id)


def list_recent(db: Session, *, limit: int = 10) -> list[OpportunitySearch]:
    return list(
        db.scalars(
            select(OpportunitySearch)
            .order_by(OpportunitySearch.created_at.desc(), OpportunitySearch.id.desc())
            .limit(limit)
        ).all()
    )


def delete(db: Session, item: OpportunitySearch) -> None:
    db.delete(item)
    db.commit()
