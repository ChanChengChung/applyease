"""Business rules for replacing a duplicate experience record."""

from sqlalchemy.orm import Session

from app.crud import experience as experience_crud


def replace_experience(db: Session, experience_id: int, replacement: dict):
    """Persist reviewed replacement content while preserving the record ID.

    A changed evidence record is intentionally returned to the unconfirmed
    state.  It cannot be used for matching or AI generation until the user
    reviews the replacement.
    """
    item = experience_crud.get(db, experience_id)
    if not item:
        return None, None

    values = dict(replacement)
    values["confirmed"] = False
    return experience_crud.update(db, item, values)
