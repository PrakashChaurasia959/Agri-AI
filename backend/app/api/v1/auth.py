"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import (
    CsrfGuardDep,
    CurrentUserDep,
    DatabaseDep,
    require_csrf,
)
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.core.rate_limit import RateLimitRule, enforce_rate_limit
from app.core.security import TokenError, decode_token
from app.database.connection import db_manager
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

AUTH_RATE_RULE = RateLimitRule(name="auth", limit=10, window_seconds=300)


def _get_service() -> AuthService:
    return AuthService(UserRepository(db_manager.get_database()))


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    _: DatabaseDep = None,
) -> TokenResponse:
    """Register a new user and start a session."""
    settings = get_settings()
    enforce_rate_limit(
        request, AUTH_RATE_RULE, enabled=settings.rate_limit_enabled
    )

    service = _get_service()
    user = await service.register(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        location=payload.location,
        primary_crops=payload.primary_crops,
    )

    tokens = service.issue_tokens(user)
    service.set_auth_cookies(
        response,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        csrf_token=tokens["csrf_token"],
    )

    logger.info("New account created for %s", payload.email)
    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        user=service.to_response(user),
        csrf_token=tokens["csrf_token"],
    )


@router.post("/login", response_model=TokenResponse, summary="Sign in")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    _: DatabaseDep = None,
) -> TokenResponse:
    """Authenticate with an email address and password."""
    settings = get_settings()
    enforce_rate_limit(
        request, AUTH_RATE_RULE, enabled=settings.rate_limit_enabled
    )

    service = _get_service()
    user = await service.authenticate(email=payload.email, password=payload.password)

    tokens = service.issue_tokens(user)
    service.set_auth_cookies(
        response,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        csrf_token=tokens["csrf_token"],
    )

    logger.info("User %s signed in", payload.email)
    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        user=service.to_response(user),
        csrf_token=tokens["csrf_token"],
    )


@router.post("/logout", response_model=MessageResponse, summary="Sign out")
async def logout(
    response: Response,
    current_user: CurrentUserDep = None,
    _: CsrfGuardDep = None,
) -> MessageResponse:
    """Clear the session cookies."""
    service = _get_service()
    service.clear_auth_cookies(response)
    logger.info("User %s signed out", current_user.email)
    return MessageResponse(message="Signed out successfully.")


@router.post("/refresh", response_model=TokenResponse, summary="Refresh the session")
async def refresh(
    request: Request,
    response: Response,
    _: DatabaseDep = None,
) -> TokenResponse:
    """Issue a new access token using the refresh cookie."""
    settings = get_settings()
    enforce_rate_limit(
        request, AUTH_RATE_RULE, enabled=settings.rate_limit_enabled
    )

    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session to refresh.",
        )

    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The session has expired. Please sign in again.",
        ) from exc

    try:
        user_id = ObjectId(payload["sub"])
    except (InvalidId, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The session is invalid. Please sign in again.",
        ) from exc

    users = UserRepository(db_manager.get_database())
    user = await users.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The session is no longer valid. Please sign in again.",
        )

    service = _get_service()
    tokens = service.issue_tokens(user)
    service.set_auth_cookies(
        response,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        csrf_token=tokens["csrf_token"],
    )
    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        user=service.to_response(user),
        csrf_token=tokens["csrf_token"],
    )


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(current_user: CurrentUserDep = None) -> UserResponse:
    """Return the profile of the signed-in user."""
    service = _get_service()
    return service.to_response(current_user.document)


@router.patch("/me", response_model=UserResponse, summary="Update the profile")
async def update_me(
    payload: UpdateProfileRequest,
    current_user: CurrentUserDep = None,
    _: CsrfGuardDep = None,
) -> UserResponse:
    """Update the signed-in user's profile fields."""
    service = _get_service()
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    updated = await service.update_profile(current_user.id, updates)
    return service.to_response(updated)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change the password",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserDep = None,
    _: CsrfGuardDep = None,
) -> MessageResponse:
    """Change the signed-in user's password."""
    service = _get_service()
    await service.change_password(
        current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Your password has been updated.")
