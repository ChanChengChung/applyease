from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.experience import Experience


def list_all(
    db: Session,
    *,
    query: str | None = None,
    confirmed: bool | None = None,
    limit: int = 100,
    offset: int = 0,
):
    statement = select(Experience)

    if query and query.strip():
        term = f"%{query.strip()}%"

        statement = statement.where(
            or_(
                Experience.title.ilike(term),
                Experience.organization.ilike(term),
                Experience.description.ilike(term),
            )
        )

    if confirmed is not None:
        statement = statement.where(Experience.confirmed == confirmed)

    return db.scalars(
        statement.order_by(Experience.created_at.desc(), Experience.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def get(db: Session, experience_id: int):
    return db.get(Experience, experience_id)


def create(db: Session, **values):
    title = (values.get("title") or "").strip().casefold()

    organization = (values.get("organization") or "").strip().casefold()

    duplicate = db.scalar(
        select(Experience).where(
            func.lower(func.trim(Experience.title)) == title,
            func.lower(func.trim(Experience.organization)) == organization,
        )
    )

    if duplicate:

        return duplicate, True
    item = Experience(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, False


def update(db: Session, item: Experience, values: dict):
    new_title = (values.get("title", item.title) or "").strip().casefold()

    new_organization = (values.get("organization", item.organization) or "").strip().casefold()

    duplicate = db.scalar(
        select(Experience).where(
            Experience.id != item.id,
            func.lower(func.trim(Experience.title)) == new_title,
            func.lower(func.trim(Experience.organization)) == new_organization,
        )
    )

    if duplicate:

        return duplicate, True

    for key, value in values.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item, False


def delete(db: Session, item: Experience):
    db.delete(item)
    db.commit()


def bulk_confirm(db: Session, ids: list[int], confirmed: bool):
    records = db.scalars(select(Experience).where(Experience.id.in_(set(ids)))).all()

    found = {item.id for item in records}

    for item in records:
        item.confirmed = confirmed

    db.commit()

    return len(records), sorted(set(ids) - found)
