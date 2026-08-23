from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:

    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create(db: Session, **values) -> User:
    item = User(**values)

    db.add(item)

    db.commit()

    db.refresh(item)

    return item


def update_password_hash(db: Session, user: User, password_hash: str) -> User:
    user.password_hash = password_hash

    db.commit()
    db.refresh(user)

    return user


def mark_email_verified(db: Session, user: User, when) -> User:
    user.email_verified_at = when

    db.commit()
    db.refresh(user)

    return user


def delete(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()
