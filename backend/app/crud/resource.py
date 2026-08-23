from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.resource import LearningResource, ResourceFeedback, ResourceProgress


def list_all(db: Session):
    return db.scalars(select(LearningResource)).all()


def get(db: Session, resource_id: int):
    return db.get(LearningResource, resource_id)


def progress_map(db: Session):
    return {item.resource_id: item.completed for item in db.scalars(select(ResourceProgress)).all()}


def get_progress(db: Session, resource_id: int):
    return db.scalar(select(ResourceProgress).where(ResourceProgress.resource_id == resource_id))


def save_health(db: Session, resource):
    db.commit()
    db.refresh(resource)
    return resource


def create_feedback(db: Session, resource_id: int, category: str, message: str):
    item = ResourceFeedback(resource_id=resource_id, category=category, message=message.strip())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def set_completed(db: Session, resource_id: int, completed: bool):
    item = db.scalar(select(ResourceProgress).where(ResourceProgress.resource_id == resource_id))

    if not item:
        item = ResourceProgress(resource_id=resource_id)
        db.add(item)

    item.completed = completed

    item.completed_at = datetime.now(timezone.utc) if completed else None

    db.commit()
    db.refresh(item)
    return item


def seed_if_empty(db: Session, catalog: list[dict]) -> None:
    existing_titles = set(db.scalars(select(LearningResource.title)).all())

    missing = [item for item in catalog if item["title"] not in existing_titles]

    if missing:
        db.add_all([LearningResource(**item) for item in missing])

        db.commit()
