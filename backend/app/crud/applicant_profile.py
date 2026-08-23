from sqlalchemy.orm import Session

from app.models.applicant_profile import ApplicantProfile


def get(db: Session, user_id: int) -> ApplicantProfile | None:

    return db.get(ApplicantProfile, user_id)


def upsert(
    db: Session,
    user_id: int,
    display_name: str,
    contact_line: str,
    email: str = "",
    phone: str = "",
    location: str = "",
    linkedin_url: str = "",
    github_url: str = "",
) -> ApplicantProfile:
    item = get(db, user_id)

    if item is None:
        item = ApplicantProfile(
            user_id=user_id,
            display_name=display_name,
            contact_line=contact_line,
            email=email,
            phone=phone,
            location=location,
            linkedin_url=linkedin_url,
            github_url=github_url,
        )

        db.add(item)

    else:
        item.display_name = display_name

        item.contact_line = contact_line
        item.email = email
        item.phone = phone
        item.location = location
        item.linkedin_url = linkedin_url
        item.github_url = github_url
    db.commit()
    db.refresh(item)

    return item


def delete(db: Session, item: ApplicantProfile) -> None:
    db.delete(item)
    db.commit()
