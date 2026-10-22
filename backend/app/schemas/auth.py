"""Authentication and user-profile schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/register``."""

    name: str = Field(min_length=2, max_length=120, examples=["Ananya Sharma"])
    email: EmailStr = Field(examples=["farmer@example.com"])
    password: str = Field(min_length=8, max_length=128)
    location: str | None = Field(default=None, max_length=160)
    primary_crops: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        """Require a minimum composition.

        These are baseline NIST-aligned composition rules, not an entropy
        requirement - length does the heavy lifting.
        """
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isalpha() for char in value):
            raise ValueError("Password must contain at least one letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number")
        return value

    @field_validator("primary_crops")
    @classmethod
    def _clean_crops(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for crop in value:
            item = crop.strip()
            if item and item not in cleaned:
                cleaned.append(item[:60])
        return cleaned[:25]


class LoginRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/login``."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/change-password``."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("New password must be at least 8 characters long")
        if not any(char.isalpha() for char in value):
            raise ValueError("New password must contain at least one letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("New password must contain at least one number")
        return value


class UpdateProfileRequest(BaseModel):
    """Payload for ``PATCH /api/v1/auth/me``."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    primary_crops: list[str] | None = Field(default=None, max_length=25)
    farm_size_hectares: float | None = Field(default=None, ge=0, le=1_000_000)


class UserResponse(BaseModel):
    """Public representation of a user - never contains the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    role: UserRole
    location: str | None = None
    farm_size_hectares: float | None = None
    primary_crops: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    """Payload returned after a successful login or registration."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    csrf_token: str | None = None
