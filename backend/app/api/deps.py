"""Shared FastAPI dependencies: authentication, authorisation, pagination."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.security import TokenError, decode_token
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.models.user import UserRole

logger = get_logger(__name__)

# ``auto_error=False`` so we can fall back to the cookie based session.
bearer_scheme = HTTPBearer(auto_error=False)

CSRF_HEADER_NAME = "x-csrf-token"
CSRF_COOKIE_NAME = "agrivision_csrf"

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Please sign in to continue.",
    headers={"WWW-Authenticate": "Bearer"},
)


class CurrentUser:
    """A lightweight authenticated principal."""

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    @property
    def id(self) -> ObjectId:
        return self.document["_id"]

    @property
    def id_str(self) -> str:
        return str(self.document["_id"])

    @property
    def email(self) -> str:
        return str(self.document.get("email", ""))

    @property
    def name(self) -> str:
        return str(self.document.get("name", ""))

    @property
    def role(self) -> UserRole:
        try:
            return UserRole(self.document.get("role", UserRole.USER))
        except ValueError:
            return UserRole.USER

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


async def _load_user(user_id: ObjectId) -> dict[str, Any] | None:
    try:
        return await db_manager.get_collection("users").find_one({"_id": user_id})
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is currently unavailable. Please try again shortly.",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load user: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify the session.",
        )


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    session_token: Annotated[str | None, Cookie(alias="agrivision_token")] = None,
) -> CurrentUser:
    """Resolve the signed-in user.

    Two authentication strategies are supported:

    * ``Authorization: Bearer <token>`` - used by API clients, scripts and
      mobile apps.  The token must be explicitly attached by the client, so
      it is not vulnerable to cross-site request forgery.
    * ``agrivision_token`` HTTP-only cookie - used by the browser SPA.  The
      cookie is *not* readable from JavaScript which limits the blast radius
      of an XSS bug, and because it is sent automatically by the browser we
      additionally require a CSRF token on state-changing requests.
    """
    token: str | None = None
    auth_source = "bearer"

    if credentials is not None and credentials.credentials:
        token = credentials.credentials
    elif session_token:
        token = session_token
        auth_source = "cookie"

    if not token:
        raise CREDENTIALS_ERROR

    try:
        payload = decode_token(token, expected_type="access")
    except TokenError:
        raise CREDENTIALS_ERROR

    subject = payload.get("sub")
    try:
        user_id = ObjectId(subject)
    except (InvalidId, TypeError):
        raise CREDENTIALS_ERROR

    user_document = await _load_user(user_id)
    if user_document is None:
        raise CREDENTIALS_ERROR

    # Attach the principal so rate limiting can key on the user id.
    request.state.user = user_document
    request.state.auth_source = auth_source

    return CurrentUser(user_document)


async def get_optional_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    session_token: Annotated[str | None, Cookie(alias="agrivision_token")] = None,
) -> CurrentUser | None:
    """Like :func:`get_current_user` but returns ``None`` instead of raising."""
    try:
        return await get_current_user(request, credentials, session_token)
    except HTTPException:
        return None


async def require_admin(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """Dependency that only administrators may pass through."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges are required for this action.",
        )
    return current_user


async def require_database() -> None:
    """Dependency that fails fast when MongoDB is unreachable."""
    if not db_manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The database is currently unavailable. "
                "Configure MONGODB_URI and restart the service."
            ),
        )


def verify_csrf(
    request: Request,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
) -> None:
    """Double-submit CSRF check for cookie-authenticated mutations.

    Only enforced when the request was authenticated through the browser
    cookie.  Bearer-authenticated clients manage their own token lifecycle and
    are not vulnerable to CSRF, so requiring the header there would break
    legitimate API usage.
    """
    settings = get_settings()
    if not settings.csrf_enabled:
        return

    if getattr(request.state, "auth_source", None) != "cookie":
        return

    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return

    if not csrf_header or not csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token. Refresh the page and try again.",
        )

    if not hmac.compare_digest(csrf_header.encode("utf-8"), csrf_cookie.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token. Refresh the page and try again.",
        )


async def require_csrf(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
) -> None:
    """Guard a state-changing endpoint with the double-submit CSRF check.

    Declared as a single dependency (rather than two independent ones) so
    that ``get_current_user`` has already run and populated
    ``request.state.auth_source`` before the CSRF comparison happens.
    """
    verify_csrf(request, csrf_header, csrf_cookie)


class PaginationParams:
    """Validated pagination query parameters.

    The parameters are declared with :func:`fastapi.Query` defaults rather
    than ``Annotated`` wrappers.  This module uses
    ``from __future__ import annotations``, which turns every annotation into
    a string; FastAPI cannot resolve a nested ``Annotated[ForwardRef(...)]``
    in that situation and raises a ``PydanticUserError`` at request time.
    Using plain defaults keeps the class-based dependency working.
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, le=100_000),
        page_size: int = Query(20, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]
PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]
DatabaseDep = Annotated[None, Depends(require_database)]
CsrfGuardDep = Annotated[None, Depends(require_csrf)]
