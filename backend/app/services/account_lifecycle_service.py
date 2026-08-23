from __future__ import annotations

import secrets
import uuid
from datetime import timedelta
from urllib.parse import quote

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import _request_hashes, _secret_hash, audit_auth, hash_password, utc_now
from app.config import settings
from app.crud import security as security_crud
from app.crud import user as user_crud
from app.models.user import User
from app.services.email_service import deliver_account_email

VERIFY_PURPOSE = "email_verification"
RESET_PURPOSE = "password_reset"
RESET_CODE_PURPOSE = "password_reset_code"


def enforce_account_email_rate_limit(
    db: Session, request: Request, email: str, event_type: str
) -> None:
    subject_hash, ip_hash, _ = _request_hashes(request, email)

    since = utc_now() - timedelta(seconds=settings.account_email_rate_limit_window_seconds)

    subject_count, ip_count = security_crud.event_counts(
        db, event_type, subject_hash, ip_hash, since
    )

    if (
        subject_count >= settings.account_email_max_requests
        or ip_count >= settings.account_email_max_ip_requests
    ):

        raise HTTPException(
            status_code=429,
            detail="Too many requests; try again later",
            headers={"Retry-After": str(settings.account_email_rate_limit_window_seconds)},
        )


def enforce_token_attempt_rate_limit(db: Session, request: Request, event_type: str) -> None:
    _, ip_hash, _ = _request_hashes(request)

    since = utc_now() - timedelta(seconds=settings.account_email_rate_limit_window_seconds)

    _, ip_count = security_crud.event_counts(db, event_type, "", ip_hash, since, outcome="failure")

    if ip_count >= settings.account_token_max_failed_attempts:

        raise HTTPException(
            status_code=429,
            detail="Too many invalid token attempts; try again later",
            headers={"Retry-After": str(settings.account_email_rate_limit_window_seconds)},
        )


def _issue_token(
    db: Session,
    user: User,
    purpose: str,
    ttl_seconds: int,
    *,
    raw_token: str | None = None,
) -> str:
    now = utc_now()

    security_crud.invalidate_account_tokens(db, user.id, purpose, now)

    raw = raw_token or secrets.token_urlsafe(32)

    security_crud.create_account_token(
        db,
        id=str(uuid.uuid4()),
        user_id=user.id,
        purpose=purpose,
        token_hash=_secret_hash(raw),
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        consumed_at=None,
    )

    return raw


def send_verification(db: Session, user: User) -> None:

    if user.email_verified:

        return
    token = _issue_token(db, user, VERIFY_PURPOSE, settings.email_verification_ttl_seconds)

    # Fragments are never sent in HTTP requests. Keeping this one-time secret
    # client-side prevents it from appearing in reverse-proxy/access logs.
    url = f"{settings.frontend_base_url.rstrip('/')}#verify_token={quote(token)}"

    deliver_account_email(
        user.email,
        "Verify your ApplyEase email",
        "Verify your ApplyEase email address by opening this link:\n\n"
        f"{url}\n\nThis one-time link expires automatically. If you did not create this account, ignore this message.",
    )


def send_password_reset(db: Session, user: User) -> None:
    token = _issue_token(db, user, RESET_PURPOSE, settings.password_reset_ttl_seconds)
    # Keep the URL as the strongest recovery option, and also supply a short
    # one-time code for local/dev mailboxes and users who open the app on a
    # different device.  It is stored hashed and has the exact same expiry.
    code = f"{secrets.randbelow(1_000_000):06d}"
    _issue_token(
        db,
        user,
        RESET_CODE_PURPOSE,
        settings.password_reset_ttl_seconds,
        raw_token=code,
    )

    # See send_verification: do not put account-recovery secrets in a URL query.
    url = f"{settings.frontend_base_url.rstrip('/')}#reset_token={quote(token)}"

    deliver_account_email(
        user.email,
        "Reset your ApplyEase password",
        "Reset your ApplyEase password by opening this link:\n\n"
        f"{url}\n\nOr enter this one-time 6-digit code in ApplyEase:\n\n{code}\n\n"
        "The link and code expire automatically. If you did not request them, ignore this message.",
    )


def confirm_email(db: Session, raw_token: str) -> User | None:
    now = utc_now()

    token = security_crud.get_active_account_token(db, _secret_hash(raw_token), VERIFY_PURPOSE, now)

    if not token or not security_crud.consume_account_token(db, token.id, now):

        return None
    user = db.get(User, token.user_id)

    if not user or not user.is_active:

        return None

    if not user.email_verified:
        user_crud.mark_email_verified(db, user, now)

    return user


def reset_password(db: Session, raw_token: str, new_password: str) -> User | None:
    now = utc_now()

    token = security_crud.get_active_account_token(
        db, _secret_hash(raw_token), RESET_PURPOSE, now
    ) or security_crud.get_active_account_token(
        db, _secret_hash(raw_token), RESET_CODE_PURPOSE, now
    )

    if not token or not security_crud.consume_account_token(db, token.id, now):

        return None
    user = db.get(User, token.user_id)

    if not user or not user.is_active:

        return None
    user_crud.update_password_hash(db, user, hash_password(new_password))

    security_crud.revoke_all(db, user.id, now)

    return user
