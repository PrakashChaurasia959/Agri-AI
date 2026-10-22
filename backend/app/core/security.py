"""Password hashing (Argon2id) and JWT issuing/verification."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TokenType = Literal["access", "refresh"]

# Argon2id parameters. Overridable through settings but deliberately bounded to
# keep hashing cost predictable and denial-of-service resistant.
_hasher: PasswordHasher | None = None


def get_password_hasher() -> PasswordHasher:
    global _hasher
    if _hasher is None:
        settings = get_settings()
        _hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            hash_len=32,
            salt_len=16,
        )
    return _hasher


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return get_password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns ``False`` for malformed hashes instead of raising, so callers can
    treat an invalid stored hash the same as a wrong password.
    """
    if not password or not password_hash:
        return False
    try:
        return bool(get_password_hasher().verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:  # pragma: no cover - defensive
        logger.warning("Password verification failed with an unexpected error")
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when a stored hash should be upgraded to current parameters."""
    try:
        return bool(get_password_hasher().check_needs_rehash(password_hash))
    except Exception:  # pragma: no cover - defensive
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def _build_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    role: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if role:
        payload["role"] = role
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.effective_jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    subject: str, role: str | None = None, expires_minutes: int | None = None
) -> str:
    settings = get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    return _build_token(subject, "access", timedelta(minutes=minutes), role=role)


def create_refresh_token(
    subject: str, role: str | None = None, expires_days: int | None = None
) -> str:
    settings = get_settings()
    days = expires_days if expires_days is not None else settings.refresh_token_expire_days
    return _build_token(subject, "refresh", timedelta(days=days), role=role)


class TokenError(Exception):
    """Raised when a token is invalid, expired or of the wrong type."""


def decode_token(token: str, expected_type: TokenType = "access") -> dict[str, Any]:
    """Decode and validate a JWT, raising :class:`TokenError` on any problem."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token is invalid") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    return payload


def hash_token(token: str) -> str:
    """Deterministic hash of a token, safe to store in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
