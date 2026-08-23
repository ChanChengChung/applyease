from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud import experience as experience_crud
from app.schemas.experience import (
    ExperienceBulkConfirm,
    ExperienceBulkConfirmRead,
    ExperienceCreate,
    ExperienceRead,
    ExperienceUpdate,
    ExperienceImpactRead,
)
from app.crud import job as job_crud
from app.crud import material as material_crud
from app.services.experience_impact_service import build_experience_impacts

router = APIRouter()


@router.get("/evidence-impact", response_model=list[ExperienceImpactRead])
def evidence_impact(db: Session = Depends(get_db)):
    """Show the concrete downstream effect of each confirmed fact."""
    return build_experience_impacts(
        experience_crud.list_all(db, confirmed=True, limit=100),
        job_crud.list_recent(db, db.info.get("current_user_id"), limit=40),
        material_crud.list_all(db),
    )


@router.get("", response_model=list[ExperienceRead])
def list_experiences(
    query: str | None = Query(default=None, max_length=200),
    confirmed: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):

    return experience_crud.list_all(
        db, query=query, confirmed=confirmed, limit=limit, offset=offset
    )


@router.post("", response_model=ExperienceRead)
def create_experience(payload: ExperienceCreate, db: Session = Depends(get_db)):
    item, duplicate = experience_crud.create(db, **payload.model_dump())

    if duplicate:

        raise HTTPException(
            status_code=409,
            detail=f"An experience with the same title and organization already exists (id={item.id})",
        )

    return item


@router.post("/bulk-confirm", response_model=ExperienceBulkConfirmRead)
def confirm_experiences(payload: ExperienceBulkConfirm, db: Session = Depends(get_db)):
    updated, missing_ids = experience_crud.bulk_confirm(db, payload.ids, payload.confirmed)

    return {"updated": updated, "missing_ids": missing_ids}


@router.patch("/{experience_id}", response_model=ExperienceRead)
def update_experience(experience_id: int, payload: ExperienceUpdate, db: Session = Depends(get_db)):
    item = experience_crud.get(db, experience_id)

    if not item:

        raise HTTPException(status_code=404, detail="Experience not found")
    updated, duplicate = experience_crud.update(db, item, payload.model_dump(exclude_unset=True))

    if duplicate:

        raise HTTPException(
            status_code=409,
            detail=f"An experience with the same title and organization already exists (id={updated.id})",
        )

    return updated


@router.delete("/{experience_id}", status_code=204)
def delete_experience(experience_id: int, db: Session = Depends(get_db)):
    item = experience_crud.get(db, experience_id)

    if not item:

        raise HTTPException(status_code=404, detail="Experience not found")
    experience_crud.delete(db, item)
