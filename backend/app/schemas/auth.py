from datetime import datetime
from typing import Literal

import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()

        if not EMAIL_RE.match(value):

            raise ValueError("email must be a valid email address")

        return value


class RegisterRequest(EmailRequest):
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(EmailRequest):
    # Existing accounts created under the earlier 8-character policy must be

    # allowed to log in and receive an automatic hash upgrade.

    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: int

    email: str

    is_active: bool

    email_verified: bool

    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str | None = None

    token_type: str = "bearer"

    user: UserRead

    mfa_required: bool = False

    mfa_token: str | None = None

    # Web clients use HttpOnly cookies, so `access_token` is intentionally null
    # in their JSON response. This explicit flag tells the UI whether a session
    # was actually created (registration may require email verification first).
    session_ready: bool = False


class SessionRead(BaseModel):
    id: str

    created_at: datetime

    last_seen_at: datetime

    expires_at: datetime

    current: bool


class TokenConfirmRequest(BaseModel):
    # Email links use a long URL-safe secret; password recovery also accepts
    # the separately issued 6-digit one-time code.
    token: str = Field(min_length=6, max_length=256)


class PasswordResetRequest(TokenConfirmRequest):
    new_password: str = Field(min_length=12, max_length=128)


class PublicMessage(BaseModel):
    message: str
    # This describes the application-wide transport only, never whether a
    # submitted email belongs to an account.
    delivery_channel: Literal["email", "local_mailbox", "disabled"] | None = None


class MFASetupRead(BaseModel):
    secret: str
    provisioning_uri: str


class MFASetupRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class MFACodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("code cannot be blank")
        return normalized


class MFALoginRequest(MFACodeRequest):
    mfa_token: str = Field(min_length=32, max_length=256)


class MFARecoveryCodes(BaseModel):
    recovery_codes: list[str]


class MFAStatus(BaseModel):
    enabled: bool
    recovery_codes_remaining: int = 0


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class SensitiveAccountActionRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)
