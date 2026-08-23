from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.starter_plan import StarterLearningPlan


def get(db: Session, user_id: int) -> StarterLearningPlan | None:
    return db.scalar(select(StarterLearningPlan).where(StarterLearningPlan.user_id == user_id))


def create_or_replace(db: Session, user_id: int, values: dict) -> StarterLearningPlan:
    item = get(db, user_id)
    if item is None:
        item = StarterLearningPlan(user_id=user_id, **values)
        db.add(item)
    else:
        for key, value in values.items():
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: StarterLearningPlan, values: dict) -> StarterLearningPlan:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item
