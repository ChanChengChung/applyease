from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.experience import Experience


def list_all(
    db: Session,
    *,
    query: str | None = None,
    confirmed: bool | None = None,
    category: str | None = None,
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

    if category:
        statement = statement.where(Experience.category == category)

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
    _refresh_rag_index(db, item.user_id)
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
    _refresh_rag_index(db, item.user_id)
    return item, False


def delete(db: Session, item: Experience):
    user_id = item.user_id
    db.delete(item)
    db.commit()
    _refresh_rag_index(db, user_id)


def bulk_confirm(db: Session, ids: list[int], confirmed: bool):
    records = db.scalars(select(Experience).where(Experience.id.in_(set(ids)))).all()

    found = {item.id for item in records}

    for item in records:
        item.confirmed = confirmed

    db.commit()

    for user_id in {item.user_id for item in records}:
        _refresh_rag_index(db, user_id)

    return len(records), sorted(set(ids) - found)


def _refresh_rag_index(db: Session, user_id: int | None) -> None:
    """Best-effort write-time indexing; derived vectors never block CRUD."""
    if user_id is None:
        return
    try:
        from app.services.rag_service import index_user_context

        index_user_context(db, int(user_id))
    except Exception:
        # The retrieval path reconciles stale records for deployments upgraded
        # from older versions, while user writes remain available offline.
        return
