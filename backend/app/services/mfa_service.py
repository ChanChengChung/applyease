"""Minimal TOTP implementation with encrypted-at-rest secrets and hashed recovery codes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime, timezone
from urllib.parse import quote

from app.auth import _secret_hash, utc_now
from app.config import settings
from app.crud import security as security_crud
from app.models.user import User

ISSUER = "ApplyEase"
LOGIN_PURPOSE = "mfa_login"


def _key(label: bytes) -> bytes:
    return hmac.new(settings.auth_secret.encode(), label, hashlib.sha256).digest()


def encrypt_secret(secret: str) -> str:
    nonce = secrets.token_bytes(16)
    raw = secret.encode()
    stream = b""
    counter = 0
    while len(stream) < len(raw):
        stream += hmac.new(
            _key(b"mfa-encryption"), nonce + counter.to_bytes(4, "big"), hashlib.sha256
        ).digest()
        counter += 1
    cipher = bytes(a ^ b for a, b in zip(raw, stream))
    mac = hmac.new(_key(b"mfa-integrity"), nonce + cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + cipher).decode()


def decrypt_secret(value: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(value.encode())
        nonce, mac, cipher = raw[:16], raw[16:48], raw[48:]
        if not hmac.compare_digest(
            mac, hmac.new(_key(b"mfa-integrity"), nonce + cipher, hashlib.sha256).digest()
        ):
            raise ValueError("invalid MAC")
        stream = b""
        counter = 0
        while len(stream) < len(cipher):
            stream += hmac.new(
                _key(b"mfa-encryption"), nonce + counter.to_bytes(4, "big"), hashlib.sha256
            ).digest()
            counter += 1
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode()
    except Exception as exc:
        raise ValueError("Stored MFA secret is invalid") from exc


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def provisioning_uri(user: User, secret: str) -> str:
    return f"otpauth://totp/{quote(ISSUER)}:{quote(user.email)}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits=6&period=30"


def valid_totp(secret: str, code: str, *, now: datetime | None = None) -> bool:
    normalized = "".join(code.split())
    if len(normalized) != 6 or not normalized.isdigit():
        return False
    # utc_now() is intentionally timezone-naive for SQLite/PostgreSQL parity;
    # restore UTC before converting it to the RFC 6238 Unix counter.
    moment = int((now or utc_now()).replace(tzinfo=timezone.utc).timestamp()) // 30
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    for counter in (moment - 1, moment, moment + 1):
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        offset = digest[-1] & 15
        expected = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if hmac.compare_digest(f"{expected:06d}", normalized):
            return True
    return False


def generate_recovery_codes() -> list[str]:
    return [
        f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        for _ in range(settings.mfa_recovery_code_count)
    ]


def recovery_hash(code: str) -> str:
    return _secret_hash(code.strip().upper())


def mfa_enabled(db, user_id: int) -> bool:
    config = security_crud.get_mfa_configuration(db, user_id)
    return bool(config and config.enabled_at)


def verify_factor(db, user_id: int, code: str) -> bool:
    config = security_crud.get_mfa_configuration(db, user_id)
    if not config or not config.enabled_at:
        return False
    try:
        if valid_totp(decrypt_secret(config.encrypted_secret), code):
            return True
    except ValueError:
        return False
    return security_crud.consume_recovery_code(db, user_id, recovery_hash(code), utc_now())
