from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import (
    audit_auth,
    create_authenticated_session,
    enforce_login_rate_limit,
    get_current_user,
    hash_password,
    password_needs_rehash,
    utc_now,
    verify_password,
    _DUMMY_PASSWORD_HASH,
    _secret_hash,
)
from app.config import settings
from app.crud import security as security_crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, SessionRead, TokenResponse, UserRead
from app.schemas.auth import (
    EmailRequest,
    MFACodeRequest,
    MFALoginRequest,
    MFARecoveryCodes,
    MFASetupRead,
    MFASetupRequest,
    MFAStatus,
    PasswordChangeRequest,
    PasswordResetRequest,
    PublicMessage,
    TokenConfirmRequest,
)
from app.schemas.auth import SensitiveAccountActionRequest
from app.services import account_lifecycle_service as lifecycle
from app.services.email_service import MailDeliveryError
from app.services import mfa_service
from app.services.account_export_service import build_account_export
from app.services.rag_service import RAGPurgeError, purge_user_context

router = APIRouter()


def _mail_delivery_channel() -> str:
    """Return transport configuration without disclosing account existence."""
    if settings.mail_delivery_mode == "file":
        return "local_mailbox"
    if settings.mail_delivery_mode == "disabled":
        return "disabled"
    return "email"


def _set_session_cookies(response: Response, token: str, csrf: str) -> None:
    common = {
        "secure": settings.auth_cookie_secure,
        "samesite": "strict",
        "path": "/",
        "max_age": settings.auth_token_ttl_seconds,
    }
    response.set_cookie(settings.auth_cookie_name, token, httponly=True, **common)

    response.set_cookie(settings.auth_csrf_cookie_name, csrf, httponly=False, **common)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        settings.auth_cookie_name, path="/", secure=settings.auth_cookie_secure, samesite="strict"
    )

    response.delete_cookie(
        settings.auth_csrf_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


def _deliver_session(request: Request, response: Response, token: str, csrf: str):

    if request.headers.get("X-ApplyEase-Client", "").casefold() == "browser-extension":

        return token
    _set_session_cookies(response, token, csrf)

    return None


def _verify_sensitive_action(
    payload: SensitiveAccountActionRequest,
    request: Request,
    user: Any,
    db: Session,
    event_type: str,
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        audit_auth(db, request, event_type=event_type, outcome="failure", user_id=user.id)
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if mfa_service.mfa_enabled(db, user.id) and (
        not payload.mfa_code or not mfa_service.verify_factor(db, user.id, payload.mfa_code)
    ):
        audit_auth(db, request, event_type=event_type, outcome="failure", user_id=user.id)
        raise HTTPException(status_code=401, detail="A valid MFA code is required")


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    email = str(payload.email).casefold()

    lifecycle.enforce_account_email_rate_limit(db, request, email, "email_verification_request")

    if user_crud.get_by_email(db, email):
        audit_auth(db, request, event_type="register", outcome="conflict", subject=email)

        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = user_crud.create(db, email=email, password_hash=hash_password(payload.password))

    try:
        lifecycle.send_verification(db, user)

        delivery_outcome = "accepted"

    except MailDeliveryError:
        delivery_outcome = "delivery_failure"
    session_ready = not settings.auth_require_verified_email
    token = csrf = None
    if session_ready:
        token, csrf, _ = create_authenticated_session(db, user, request)

    audit_auth(
        db, request, event_type="register", outcome="success", subject=email, user_id=user.id
    )

    audit_auth(
        db,
        request,
        event_type="email_verification_request",
        outcome=delivery_outcome,
        subject=email,
        user_id=user.id,
    )

    return {
        "access_token": (
            _deliver_session(request, response, token, csrf) if token and csrf else None
        ),
        "token_type": "bearer",
        "user": user,
        "session_ready": session_ready,
    }


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    email = str(payload.email).casefold()

    enforce_login_rate_limit(db, request, email)

    user = user_crud.get_by_email(db, email)

    valid = (
        verify_password(payload.password, user.password_hash)
        if user
        else verify_password(payload.password, _DUMMY_PASSWORD_HASH)
    )

    if not user or not valid or not user.is_active:
        audit_auth(
            db,
            request,
            event_type="login",
            outcome="failure",
            subject=email,
            user_id=user.id if user else None,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_require_verified_email and not user.email_verified:
        audit_auth(
            db, request, event_type="login", outcome="unverified", subject=email, user_id=user.id
        )

        raise HTTPException(status_code=403, detail="Email verification required")

    if password_needs_rehash(user.password_hash):
        user_crud.update_password_hash(db, user, hash_password(payload.password))
    if mfa_service.mfa_enabled(db, user.id):
        challenge = lifecycle._issue_token(
            db, user, mfa_service.LOGIN_PURPOSE, settings.mfa_login_ttl_seconds
        )
        audit_auth(
            db,
            request,
            event_type="mfa_login_challenge",
            outcome="issued",
            subject=email,
            user_id=user.id,
        )
        return {
            "access_token": None,
            "token_type": "bearer",
            "user": user,
            "mfa_required": True,
            "mfa_token": challenge,
            "session_ready": False,
        }
    token, csrf, _ = create_authenticated_session(db, user, request)

    audit_auth(db, request, event_type="login", outcome="success", subject=email, user_id=user.id)

    return {
        "access_token": _deliver_session(request, response, token, csrf),
        "token_type": "bearer",
        "user": user,
        "session_ready": True,
    }


@router.post("/mfa/login/verify", response_model=TokenResponse)
def verify_mfa_login(
    payload: MFALoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    lifecycle.enforce_token_attempt_rate_limit(db, request, "mfa_login_verify")
    token = security_crud.get_active_account_token(
        db, _secret_hash(payload.mfa_token), mfa_service.LOGIN_PURPOSE, utc_now()
    )
    if (
        not token
        or not mfa_service.verify_factor(db, token.user_id, payload.code)
        or not security_crud.consume_account_token(db, token.id, utc_now())
    ):
        audit_auth(db, request, event_type="mfa_login_verify", outcome="failure")
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")
    user = user_crud.get_by_id(db, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication required")
    raw, csrf, _ = create_authenticated_session(db, user, request)
    audit_auth(db, request, event_type="mfa_login_verify", outcome="success", user_id=user.id)
    return {
        "access_token": _deliver_session(request, response, raw, csrf),
        "token_type": "bearer",
        "user": user,
        "session_ready": True,
    }


@router.get("/mfa", response_model=MFAStatus)
def mfa_status(user: Any = Depends(get_current_user), db: Session = Depends(get_db)):
    enabled = mfa_service.mfa_enabled(db, user.id)
    return {
        "enabled": enabled,
        "recovery_codes_remaining": (
            security_crud.remaining_recovery_codes(db, user.id) if enabled else 0
        ),
    }


@router.post("/mfa/setup", response_model=MFASetupRead)
def setup_mfa(
    payload: MFASetupRequest,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if mfa_service.mfa_enabled(db, user.id):
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    if not verify_password(payload.current_password, user.password_hash):
        audit_auth(db, request, event_type="mfa_setup", outcome="failure", user_id=user.id)
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    secret = mfa_service.generate_secret()
    now = utc_now()
    security_crud.save_mfa_configuration(
        db, user.id, mfa_service.encrypt_secret(secret), now, enabled=False
    )
    return {"secret": secret, "provisioning_uri": mfa_service.provisioning_uri(user, secret)}


@router.post("/mfa/confirm", response_model=MFARecoveryCodes)
def confirm_mfa(
    payload: MFACodeRequest,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = security_crud.get_mfa_configuration(db, user.id)
    if not config or config.enabled_at:
        raise HTTPException(status_code=409, detail="Start MFA setup before confirming it")
    if not mfa_service.valid_totp(
        mfa_service.decrypt_secret(config.encrypted_secret), payload.code
    ):
        audit_auth(db, request, event_type="mfa_setup", outcome="failure", user_id=user.id)
        raise HTTPException(status_code=422, detail="Invalid verification code")
    now = utc_now()
    security_crud.enable_mfa_configuration(db, config, now)
    codes = mfa_service.generate_recovery_codes()
    security_crud.replace_recovery_codes(
        db, user.id, [mfa_service.recovery_hash(code) for code in codes], now
    )
    audit_auth(db, request, event_type="mfa_setup", outcome="success", user_id=user.id)
    return {"recovery_codes": codes}


@router.post("/mfa/recovery-codes", response_model=MFARecoveryCodes)
def rotate_mfa_recovery_codes(
    payload: MFACodeRequest,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not mfa_service.verify_factor(db, user.id, payload.code):
        audit_auth(
            db, request, event_type="mfa_recovery_rotate", outcome="failure", user_id=user.id
        )
        raise HTTPException(status_code=422, detail="Invalid verification code")
    codes = mfa_service.generate_recovery_codes()
    security_crud.replace_recovery_codes(
        db, user.id, [mfa_service.recovery_hash(code) for code in codes], utc_now()
    )
    audit_auth(db, request, event_type="mfa_recovery_rotate", outcome="success", user_id=user.id)
    return {"recovery_codes": codes}


@router.post("/mfa/disable", status_code=204)
def disable_mfa(
    payload: MFACodeRequest,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not mfa_service.verify_factor(db, user.id, payload.code):
        audit_auth(db, request, event_type="mfa_disable", outcome="failure", user_id=user.id)
        raise HTTPException(status_code=422, detail="Invalid verification code")
    security_crud.delete_mfa_configuration(db, user.id)
    audit_auth(db, request, event_type="mfa_disable", outcome="success", user_id=user.id)


@router.get("/me", response_model=UserRead)
def me(user: Any = Depends(get_current_user)):

    return user


@router.get("/sessions", response_model=list[SessionRead])
def sessions(
    request: Request, user: Any = Depends(get_current_user), db: Session = Depends(get_db)
):
    current = getattr(request.state, "auth_session", None)

    return [
        {
            "id": item.id,
            "created_at": item.created_at,
            "last_seen_at": item.last_seen_at,
            "expires_at": item.expires_at,
            "current": bool(current and item.id == current.id),
        }
        for item in security_crud.list_active_sessions(db, user.id, utc_now())
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_other_session(
    session_id: str,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = getattr(request.state, "auth_session", None)
    if current and current.id == session_id:
        raise HTTPException(status_code=409, detail="Use logout to end the current session")
    if not security_crud.revoke_session_by_id(db, user.id, session_id, utc_now()):
        raise HTTPException(status_code=404, detail="Active session not found")
    audit_auth(db, request, event_type="session_revoke", outcome="success", user_id=user.id)


@router.post("/password/change", response_model=PublicMessage)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        audit_auth(db, request, event_type="password_change", outcome="failure", user_id=user.id)
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if mfa_service.mfa_enabled(db, user.id) and (
        not payload.mfa_code or not mfa_service.verify_factor(db, user.id, payload.mfa_code)
    ):
        audit_auth(db, request, event_type="password_change", outcome="failure", user_id=user.id)
        raise HTTPException(status_code=401, detail="A valid MFA code is required")
    user_crud.update_password_hash(db, user, hash_password(payload.new_password))
    security_crud.revoke_all(db, user.id, utc_now())
    audit_auth(db, request, event_type="password_change", outcome="success", user_id=user.id)
    _clear_session_cookies(response)
    return {"message": "Password changed. Sign in again on all devices."}


@router.post("/data-export")
def export_account_data(
    payload: SensitiveAccountActionRequest,
    request: Request,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_sensitive_action(payload, request, user, db, "account_export")
    content = build_account_export(db, user)
    audit_auth(db, request, event_type="account_export", outcome="success", user_id=user.id)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="ApplyEase-account-data.zip"'},
    )


@router.delete("/account", status_code=204)
def delete_account(
    payload: SensitiveAccountActionRequest,
    request: Request,
    response: Response,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_sensitive_action(payload, request, user, db, "account_delete")
    try:
        purge_user_context(user.id)
    except RAGPurgeError as exc:
        audit_auth(
            db,
            request,
            event_type="account_delete",
            outcome="vector_purge_failure",
            user_id=user.id,
        )
        raise HTTPException(
            status_code=503, detail="Account deletion is temporarily unavailable; please retry"
        ) from exc
    audit_auth(db, request, event_type="account_delete", outcome="success", user_id=user.id)
    user_crud.delete(db, user)
    _clear_session_cookies(response)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = getattr(request.state, "auth_session", None)

    if session:
        security_crud.revoke_session(db, session, utc_now())
    audit_auth(db, request, event_type="logout", outcome="success", user_id=user.id)

    _clear_session_cookies(response)


@router.post("/logout-all", status_code=204)
def logout_all(
    request: Request,
    response: Response,
    user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    security_crud.revoke_all(db, user.id, utc_now())

    audit_auth(db, request, event_type="logout_all", outcome="success", user_id=user.id)

    _clear_session_cookies(response)


@router.post("/email-verification/request", response_model=PublicMessage, status_code=202)
def request_email_verification(
    payload: EmailRequest, request: Request, db: Session = Depends(get_db)
):
    email = payload.email

    lifecycle.enforce_account_email_rate_limit(db, request, email, "email_verification_request")

    user = user_crud.get_by_email(db, email)

    outcome = "accepted"

    if user and user.is_active and not user.email_verified:

        try:
            lifecycle.send_verification(db, user)

        except MailDeliveryError:
            outcome = "delivery_failure"
    audit_auth(
        db,
        request,
        event_type="email_verification_request",
        outcome=outcome,
        subject=email,
        user_id=user.id if user else None,
    )

    return {"message": "If the account exists and needs verification, an email has been sent."}


@router.post("/email-verification/confirm", response_model=PublicMessage)
def confirm_email(payload: TokenConfirmRequest, request: Request, db: Session = Depends(get_db)):
    lifecycle.enforce_token_attempt_rate_limit(db, request, "email_verification_confirm")

    user = lifecycle.confirm_email(db, payload.token)

    if not user:
        audit_auth(db, request, event_type="email_verification_confirm", outcome="failure")

        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    audit_auth(
        db, request, event_type="email_verification_confirm", outcome="success", user_id=user.id
    )

    return {"message": "Email verified. You can now sign in."}


@router.post("/password/forgot", response_model=PublicMessage, status_code=202)
def forgot_password(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email

    lifecycle.enforce_account_email_rate_limit(db, request, email, "password_reset_request")

    user = user_crud.get_by_email(db, email)

    outcome = "accepted"

    if user and user.is_active:

        try:
            lifecycle.send_password_reset(db, user)

        except MailDeliveryError:
            outcome = "delivery_failure"
    audit_auth(
        db,
        request,
        event_type="password_reset_request",
        outcome=outcome,
        subject=email,
        user_id=user.id if user else None,
    )

    return {
        "message": "If the account exists, password reset instructions have been sent.",
        "delivery_channel": _mail_delivery_channel(),
    }


@router.post("/password/reset", response_model=PublicMessage)
def password_reset(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    lifecycle.enforce_token_attempt_rate_limit(db, request, "password_reset_confirm")

    user = lifecycle.reset_password(db, payload.token, payload.new_password)

    if not user:
        audit_auth(db, request, event_type="password_reset_confirm", outcome="failure")

        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    audit_auth(db, request, event_type="password_reset_confirm", outcome="success", user_id=user.id)

    _clear_session_cookies(response)

    return {"message": "Password reset. Sign in again on all devices."}
