from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.security import (
    AccountToken,
    AuthSession,
    MFAConfiguration,
    MFARecoveryCode,
    SecurityAudit,
)


def get_session_by_hash(db: Session, token_hash: str) -> AuthSession | None:

    return db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))


def create_session(db: Session, **values) -> AuthSession:
    item = AuthSession(**values)

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def revoke_session(db: Session, session: AuthSession, when: datetime) -> None:
    session.revoked_at = when
    db.commit()


def revoke_all(db: Session, user_id: int, when: datetime) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=when)
    )

    db.commit()
    return int(result.rowcount or 0)


def revoke_session_by_id(db: Session, user_id: int, session_id: str, when: datetime) -> bool:
    result = db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=when)
    )
    db.commit()
    return int(result.rowcount or 0) == 1


def list_active_sessions(db: Session, user_id: int, now: datetime) -> list[AuthSession]:

    return list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.last_seen_at.desc())
        ).all()
    )


def add_audit(db: Session, **values) -> None:
    db.add(SecurityAudit(**values))
    db.commit()


def failed_attempt_counts(
    db: Session, subject_hash: str, ip_hash: str, since: datetime
) -> tuple[int, int]:
    base = (
        SecurityAudit.event_type == "login",
        SecurityAudit.outcome == "failure",
        SecurityAudit.created_at >= since,
    )

    subject_count = int(
        db.scalar(
            select(func.count(SecurityAudit.id)).where(
                *base, SecurityAudit.subject_hash == subject_hash
            )
        )
        or 0
    )
    ip_count = int(
        db.scalar(
            select(func.count(SecurityAudit.id)).where(*base, SecurityAudit.ip_hash == ip_hash)
        )
        or 0
    )

    return subject_count, ip_count


def event_counts(
    db: Session,
    event_type: str,
    subject_hash: str,
    ip_hash: str,
    since: datetime,
    outcome: str | None = None,
) -> tuple[int, int]:
    base = [SecurityAudit.event_type == event_type, SecurityAudit.created_at >= since]

    if outcome is not None:
        base.append(SecurityAudit.outcome == outcome)
    subject_count = int(
        db.scalar(
            select(func.count(SecurityAudit.id)).where(
                *base, SecurityAudit.subject_hash == subject_hash
            )
        )
        or 0
    )
    ip_count = int(
        db.scalar(
            select(func.count(SecurityAudit.id)).where(*base, SecurityAudit.ip_hash == ip_hash)
        )
        or 0
    )

    return subject_count, ip_count


def invalidate_account_tokens(db: Session, user_id: int, purpose: str, when: datetime) -> int:
    result = db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.consumed_at.is_(None),
        )
        .values(consumed_at=when)
    )

    db.commit()
    return int(result.rowcount or 0)


def create_account_token(db: Session, **values) -> AccountToken:
    item = AccountToken(**values)

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def get_active_account_token(
    db: Session, token_hash: str, purpose: str, now: datetime
) -> AccountToken | None:

    return db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == token_hash,
            AccountToken.purpose == purpose,
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > now,
        )
    )


def consume_account_token(db: Session, token_id: str, when: datetime) -> bool:
    result = db.execute(
        update(AccountToken)
        .where(
            AccountToken.id == token_id,
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > when,
        )
        .values(consumed_at=when)
    )

    db.commit()
    return int(result.rowcount or 0) == 1


def get_mfa_configuration(db: Session, user_id: int) -> MFAConfiguration | None:
    return db.get(MFAConfiguration, user_id)


def save_mfa_configuration(
    db: Session, user_id: int, encrypted_secret: str, now: datetime, *, enabled: bool
) -> MFAConfiguration:
    item = get_mfa_configuration(db, user_id)
    if item is None:
        item = MFAConfiguration(
            user_id=user_id,
            encrypted_secret=encrypted_secret,
            enabled_at=now if enabled else None,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
    else:
        item.encrypted_secret = encrypted_secret
        item.enabled_at = now if enabled else item.enabled_at
        item.updated_at = now
    db.commit()
    db.refresh(item)
    return item


def enable_mfa_configuration(
    db: Session, item: MFAConfiguration, now: datetime
) -> MFAConfiguration:
    item.enabled_at = now
    item.updated_at = now
    db.commit()
    db.refresh(item)
    return item


def delete_mfa_configuration(db: Session, user_id: int) -> None:
    item = get_mfa_configuration(db, user_id)
    if item:
        db.delete(item)
        db.commit()


def replace_recovery_codes(
    db: Session, user_id: int, code_hashes: list[str], now: datetime
) -> None:
    db.execute(
        update(MFARecoveryCode)
        .where(MFARecoveryCode.user_id == user_id, MFARecoveryCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    db.add_all(
        [MFARecoveryCode(user_id=user_id, code_hash=value, created_at=now) for value in code_hashes]
    )
    db.commit()


def consume_recovery_code(db: Session, user_id: int, code_hash: str, now: datetime) -> bool:
    result = db.execute(
        update(MFARecoveryCode)
        .where(
            MFARecoveryCode.user_id == user_id,
            MFARecoveryCode.code_hash == code_hash,
            MFARecoveryCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.commit()
    return int(result.rowcount or 0) == 1


def remaining_recovery_codes(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(MFARecoveryCode.id)).where(
                MFARecoveryCode.user_id == user_id, MFARecoveryCode.consumed_at.is_(None)
            )
        )
        or 0
    )
