"""User document model and role definitions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import EmailStr, Field

from app.models.base import MongoDocumentModel


class UserRole(str, Enum):
    """Roles recognised by the authorisation layer."""

    USER = "user"
    ADMIN = "admin"


class UserDocument(MongoDocumentModel):
    """A row of the ``users`` collection.

    ``password_hash`` is never serialised into an API response - the public
    representation lives in :mod:`app.schemas.auth`.
    """

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password_hash: str = Field(min_length=20)
    role: UserRole = UserRole.USER
    location: str | None = Field(default=None, max_length=160)
    farm_size_hectares: float | None = Field(default=None, ge=0, le=1_000_000)
    primary_crops: list[str] = Field(default_factory=list, max_length=25)
    last_login_at: datetime | None = None
