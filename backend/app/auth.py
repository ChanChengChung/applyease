from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.crud import security as security_crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.security import AuthSession
from app.models.user import User

PASSWORD_ROUNDS = 310_000
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def utc_now() -> datetime:
    # Models use portable timezone-naive UTC so SQLite and PostgreSQL compare identically.

    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ROUNDS)

    return f"pbkdf2_sha256${PASSWORD_ROUNDS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(24))


def verify_password(password: str, encoded: str) -> bool:

    try:
        algorithm, rounds, salt, digest = encoded.split("$", 3)

        if algorithm != "pbkdf2_sha256":

            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds)
        )

        return hmac.compare_digest(actual, base64.urlsafe_b64decode(digest))

    except (ValueError, TypeError):

        return False


def password_needs_rehash(encoded: str) -> bool:

    try:
        algorithm, rounds, *_ = encoded.split("$", 3)

        return algorithm != "pbkdf2_sha256" or int(rounds) < PASSWORD_ROUNDS

    except (ValueError, TypeError):

        return True


def _secret_hash(value: str) -> str:

    return hmac.new(settings.auth_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _request_hashes(request: Request, subject: str = "") -> tuple[str, str, str]:
    # In production the backend is private: Caddy overwrites X-Real-IP with
    # the external peer and Nginx passes it through unchanged. Development and
    # tests deliberately ignore forwarding headers so local callers cannot
    # spoof rate-limit/audit identities.
    forwarded_ip = request.headers.get("X-Real-IP", "").strip()
    ip = (
        forwarded_ip
        if settings.app_env == "production" and forwarded_ip
        else (request.client.host if request.client else "unknown")
    )

    agent = request.headers.get("user-agent", "")[:1000]

    return _secret_hash(subject.casefold()), _secret_hash(ip), _secret_hash(agent)


def create_authenticated_session(
    db: Session, user: User, request: Request
) -> tuple[str, str, AuthSession]:
    raw_token = secrets.token_urlsafe(32)

    csrf_token = secrets.token_urlsafe(24)

    _, ip_hash, agent_hash = _request_hashes(request)

    now = utc_now()

    item = security_crud.create_session(
        db,
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=_secret_hash(raw_token),
        csrf_hash=_secret_hash(csrf_token),
        user_agent_hash=agent_hash,
        ip_hash=ip_hash,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=settings.auth_token_ttl_seconds),
    )

    return raw_token, csrf_token, item


def audit_auth(
    db: Session,
    request: Request,
    *,
    event_type: str,
    outcome: str,
    subject: str = "",
    user_id: int | None = None,
) -> None:
    subject_hash, ip_hash, agent_hash = _request_hashes(request, subject)

    security_crud.add_audit(
        db,
        user_id=user_id,
        event_type=event_type,
        outcome=outcome,
        subject_hash=subject_hash,
        ip_hash=ip_hash,
        user_agent_hash=agent_hash,
        created_at=utc_now(),
    )


def enforce_login_rate_limit(db: Session, request: Request, email: str) -> None:
    subject_hash, ip_hash, _ = _request_hashes(request, email)

    since = utc_now() - timedelta(seconds=settings.auth_rate_limit_window_seconds)

    subject_count, ip_count = security_crud.failed_attempt_counts(db, subject_hash, ip_hash, since)

    if (
        subject_count >= settings.auth_max_failed_attempts
        or ip_count >= settings.auth_max_failed_ip_attempts
    ):

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts; try again later",
            headers={"Retry-After": str(settings.auth_rate_limit_window_seconds)},
        )


def _presented_token(request: Request) -> tuple[str, str]:
    authorization = request.headers.get("Authorization", "")

    if authorization.startswith("Bearer "):

        return authorization.removeprefix("Bearer ").strip(), "bearer"
    cookie = request.cookies.get(settings.auth_cookie_name, "")

    return (cookie, "cookie") if cookie else ("", "none")


def _require_csrf(request: Request, session: AuthSession, source: str) -> None:

    if source != "cookie" or request.method.upper() in SAFE_METHODS:

        return
    cookie = request.cookies.get(settings.auth_csrf_cookie_name, "")

    header = request.headers.get("X-CSRF-Token", "")

    if (
        not cookie
        or not header
        or not hmac.compare_digest(cookie, header)
        or not hmac.compare_digest(_secret_hash(header), session.csrf_hash)
    ):

        raise HTTPException(status_code=403, detail="CSRF validation failed")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token, source = _presented_token(request)

    session = security_crud.get_session_by_hash(db, _secret_hash(token)) if token else None

    now = utc_now()

    if session and session.revoked_at is None and session.expires_at > now:
        _require_csrf(request, session, source)

        user = db.get(User, session.user_id)

        if user and user.is_active:

            if settings.auth_require_verified_email and not user.email_verified:

                raise HTTPException(status_code=403, detail="Email verification required")

            if (now - session.last_seen_at).total_seconds() >= 300:
                session.last_seen_at = now
                db.commit()
            request.state.auth_session = session

            request.state.auth_source = source

            db.info["current_user_id"] = user.id

            return user
    # Compatibility applies only when no credential was presented. Invalid or

    # expired credentials must never silently become the local account.

    if not token and settings.app_env in {"development", "test"}:
        user = user_crud.get_by_email(db, "local@applyease.dev")

        if not user:
            user = user_crud.create(
                db,
                email="local@applyease.dev",
                password_hash=hash_password(secrets.token_urlsafe(24)),
                email_verified_at=now,
            )
        db.info["current_user_id"] = user.id

        request.state.auth_session = None

        request.state.auth_source = "local"

        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
