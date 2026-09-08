from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.starter_plan import StarterLearningPlan


def list_for_user(db: Session, user_id: int) -> list[StarterLearningPlan]:
    return list(
        db.scalars(
            select(StarterLearningPlan)
            .where(StarterLearningPlan.user_id == user_id)
            .order_by(StarterLearningPlan.updated_at.desc(), StarterLearningPlan.id.desc())
        ).all()
    )


def get_latest(db: Session, user_id: int) -> StarterLearningPlan | None:
    return next(iter(list_for_user(db, user_id)), None)


def get(db: Session, plan_id: int, user_id: int) -> StarterLearningPlan | None:
    return db.scalar(
        select(StarterLearningPlan).where(
            StarterLearningPlan.id == plan_id,
            StarterLearningPlan.user_id == user_id,
        )
    )


def create(db: Session, user_id: int, values: dict) -> StarterLearningPlan:
    item = StarterLearningPlan(user_id=user_id, **values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: StarterLearningPlan, values: dict) -> StarterLearningPlan:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: StarterLearningPlan) -> None:
    db.delete(item)
    db.commit()
