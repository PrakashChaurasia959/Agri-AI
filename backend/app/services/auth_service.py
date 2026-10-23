"""Authentication and session management.

Token strategy
--------------
Two complementary mechanisms are supported:

1. **HTTP-only cookie (browser SPA).**  The access token is delivered in an
   ``HttpOnly`` cookie so that JavaScript cannot read it.  This limits the
   blast radius of an XSS bug - an injected script cannot exfiltrate the
   session token.  Because the browser attaches the cookie automatically, a
   double-submit CSRF token is required for state-changing requests
   (see :func:`app.api.deps.verify_csrf`).

2. **``Authorization: Bearer`` header (API clients).**  The token is returned
   in the login response body and attached explicitly by the client, so it is
   not automatically sent by the browser and CSRF protection is not needed.

The access token is short lived (60 minutes by default) and can be refreshed
with the refresh-token cookie.  The refresh token is scoped to
``/api/v1/auth`` so it is never sent to other endpoints.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, Response, status

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.user import UserDocument, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserResponse

logger = get_logger(__name__)

CSRF_COOKIE_NAME = "agrivision_csrf"


class AuthService:
    """Registration, login, profile and password operations."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def to_response(document: dict[str, Any]) -> UserResponse:
        """Project a user document onto the public schema.

        The password hash is intentionally *not* part of ``UserResponse``, so
        it can never leak through the API.
        """
        return UserResponse(
            id=str(document["_id"]),
            name=document.get("name", ""),
            email=document.get("email", ""),
            role=document.get("role", UserRole.USER),
            location=document.get("location"),
            farm_size_hectares=document.get("farm_size_hectares"),
            primary_crops=document.get("primary_crops", []),
            created_at=document.get("created_at"),
            last_login_at=document.get("last_login_at"),
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register(
        self,
        *,
        name: str,
        email: str,
        password: str,
        location: str | None = None,
        primary_crops: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new user account.

        The very first registered account is *not* auto-promoted to admin -
        administrators are bootstrapped explicitly through
        ``scripts/create_admin.py`` so that a public sign-up can never
        escalate privileges.
        """
        normalised_email = email.strip().lower()

        if await self._users.email_exists(normalised_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        document = UserDocument(
            name=name,
            email=normalised_email,
            password_hash=hash_password(password),
            role=UserRole.USER,
            location=location,
            primary_crops=primary_crops or [],
        ).to_mongo()

        try:
            created = await self._users.create(document)
        except Exception as exc:
            # A duplicate-key error means a concurrent registration won the
            # race - surface it as a conflict rather than a 500.
            if "DuplicateKeyError" in type(exc).__name__:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email address already exists.",
                ) from exc
            logger.error("Registration failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create the account right now. Please try again.",
            ) from exc

        logger.info("Registered new user %s", normalised_email)
        return created

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def authenticate(self, *, email: str, password: str) -> dict[str, Any]:
        """Verify credentials and return the user document."""
        normalised_email = email.strip().lower()
        user = await self._users.get_by_email(normalised_email)

        # Always run a hash verification so that the response time does not
        # reveal whether the account exists.
        stored_hash = user.get("password_hash") if user else _DUMMY_HASH
        password_ok = verify_password(password, stored_hash)

        if user is None or not password_ok:
            if user is not None and needs_rehash(user.get("password_hash", "")):
                await self._users.update_password(
                    user["_id"], hash_password(password)
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email address or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        await self._users.update_last_login(user["_id"], datetime.now(timezone.utc))
        user["last_login_at"] = datetime.now(timezone.utc)
        return user

    # ------------------------------------------------------------------
    # Tokens and cookies
    # ------------------------------------------------------------------
    @staticmethod
    def issue_tokens(user: dict[str, Any]) -> dict[str, Any]:
        """Create an access/refresh token pair plus a CSRF token."""
        settings = get_settings()
        subject = str(user["_id"])
        role = user.get("role", UserRole.USER)
        role_value = role.value if isinstance(role, UserRole) else str(role)

        return {
            "access_token": create_access_token(subject, role=role_value),
            "refresh_token": create_refresh_token(subject, role=role_value),
            "csrf_token": secrets.token_urlsafe(32),
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    @staticmethod
    def set_auth_cookies(
        response: Response,
        *,
        access_token: str,
        refresh_token: str,
        csrf_token: str,
    ) -> None:
        """Attach the session cookies to a response."""
        settings = get_settings()
        max_age = settings.access_token_expire_minutes * 60

        response.set_cookie(
            key=settings.cookie_name,
            value=access_token,
            max_age=max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/",
        )
        response.set_cookie(
            key=settings.refresh_cookie_name,
            value=refresh_token,
            max_age=settings.refresh_token_expire_days * 86400,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/api/v1/auth",
        )
        # The CSRF cookie is deliberately readable by JavaScript: the SPA
        # copies it into the X-CSRF-Token header on every mutating request.
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=max_age,
            httponly=False,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            domain=settings.cookie_domain,
            path="/",
        )

    @staticmethod
    def clear_auth_cookies(response: Response) -> None:
        """Remove the session cookies on logout."""
        settings = get_settings()
        response.delete_cookie(
            key=settings.cookie_name, path="/", domain=settings.cookie_domain
        )
        response.delete_cookie(
            key=settings.refresh_cookie_name,
            path="/api/v1/auth",
            domain=settings.cookie_domain,
        )
        response.delete_cookie(
            key=CSRF_COOKIE_NAME, path="/", domain=settings.cookie_domain
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def update_profile(
        self, user_id: ObjectId, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a validated partial update to a user profile."""
        clean: dict[str, Any] = {}
        for key in ("name", "location", "primary_crops", "farm_size_hectares"):
            if key in updates and updates[key] is not None:
                clean[key] = updates[key]
        if not clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No profile fields were provided to update.",
            )
        clean["updated_at"] = datetime.now(timezone.utc)
        updated = await self._users.update(user_id, clean)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )
        return updated

    async def change_password(
        self, user_id: ObjectId, *, current_password: str, new_password: str
    ) -> None:
        """Change a user's password after verifying the current one."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )
        if not verify_password(current_password, user.get("password_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The current password is incorrect.",
            )
        if current_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The new password must be different from the current password.",
            )
        await self._users.update_password(user_id, hash_password(new_password))

    async def request_password_reset(self, email: str) -> None:
        """Request a password reset - always returns without leaking account existence."""
        normalised_email = email.strip().lower()
        user = await self._users.get_by_email(normalised_email)
        if user is None:
            # Do not leak whether user exists
            return
        # For now, just log - in production would send email with token
        logger.info("Password reset requested for %s", normalised_email)
        return

    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset password with token."""
        if not token or not new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long.",
            )
        if not any(char.isalpha() for char in new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one letter.",
            )
        if not any(char.isdigit() for char in new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one number.",
            )
        # For now, reject - implement token storage in production
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )


# A syntactically valid Argon2 hash of a random value.  It is used so that
# the login path performs a real hash verification even when the account does
# not exist, which keeps the timing of the two failure modes comparable.
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=2$c29tZXNhbHRzb21lc2FsdA$"
    "Zx4vJ7Yq1n0Kk9tNn5mQhO0m0k8lq1sS8Zg1o0Rr7UuY"
)
