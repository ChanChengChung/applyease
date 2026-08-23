from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.crud import applicant_profile as profile_crud
from app.db.session import get_db
from app.schemas.applicant_profile import ApplicantProfileRead, ApplicantProfileUpdate

router = APIRouter()


@router.get("", response_model=ApplicantProfileRead)
def get_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = profile_crud.get(db, current_user.id)

    if not item:

        raise HTTPException(status_code=404, detail="Applicant profile not found")

    return item


@router.put("", response_model=ApplicantProfileRead)
def save_profile(
    payload: ApplicantProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):

    return profile_crud.upsert(
        db,
        current_user.id,
        payload.display_name,
        payload.contact_line,
        payload.email,
        payload.phone,
        payload.location,
        payload.linkedin_url,
        payload.github_url,
    )


@router.delete("", status_code=204)
def delete_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = profile_crud.get(db, current_user.id)

    if item:
        profile_crud.delete(db, item)

    return Response(status_code=204)
