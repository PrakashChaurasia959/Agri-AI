"""Crop record document model (crop recommendation + yield history)."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import Field

from app.models.base import MongoDocumentModel


class CropRecordDocument(MongoDocumentModel):
    """A row of the ``crop_records`` collection.

    Stores the measured soil / environmental parameters that produced a
    recommendation so a farmer can look back at the exact conditions behind
    a suggestion.
    """

    user_id: ObjectId
    crop_type: str = Field(description="Top recommended crop (or the requested crop for yield runs)")
    soil_parameters: dict[str, Any] = Field(default_factory=dict)
    environmental_parameters: dict[str, Any] = Field(default_factory=dict)
    prediction_summary: dict[str, Any] = Field(default_factory=dict)
