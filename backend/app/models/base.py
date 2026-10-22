"""Shared helpers for MongoDB document models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Timezone-aware current UTC time (Mongo stores UTC)."""
    return datetime.now(timezone.utc)


def new_object_id() -> ObjectId:
    return ObjectId()


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to timezone-aware UTC.

    PyMongo returns BSON datetimes as **naive** values unless the client is
    created with ``tz_aware=True``, so a document read from MongoDB cannot be
    compared with ``datetime.now(timezone.utc)`` until it is normalised.  Any
    caller that mixes stored timestamps with the current time must run them
    through this helper first.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class MongoBaseModel(BaseModel):
    """Base model for documents stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    id: ObjectId | None = Field(default=None, alias="_id")

    def to_mongo(self, *, exclude_none: bool = True) -> dict[str, Any]:
        """Serialise to a MongoDB-ready document (ObjectId preserved)."""
        payload = self.model_dump(by_alias=True, exclude_none=exclude_none)
        return payload


class MongoDocumentModel(MongoBaseModel):
    """Adds the ``created_at`` / ``updated_at`` bookkeeping fields."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_utc(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value)
