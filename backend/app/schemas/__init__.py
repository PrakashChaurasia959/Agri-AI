"""API schema package."""

from app.schemas.common import (
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)

__all__ = [
    "ChangePasswordRequest",
    "ErrorResponse",
    "LoginRequest",
    "MessageResponse",
    "PaginatedResponse",
    "PaginationMeta",
    "RegisterRequest",
    "TokenResponse",
    "UpdateProfileRequest",
    "UserResponse",
]
