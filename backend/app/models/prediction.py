"""Prediction document models (disease detection, crop recommendation, yield)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from bson import ObjectId
from pydantic import Field

from app.models.base import MongoDocumentModel


class PredictionType(str, Enum):
    DISEASE = "disease"
    CROP_RECOMMENDATION = "crop_recommendation"
    YIELD = "yield"


class PredictionDocument(MongoDocumentModel):
    """A row of the ``predictions`` collection.

    Only metadata and model output are persisted.  The uploaded image itself is
    never stored inside a MongoDB document - see
    :mod:`app.services.image_service` for the image handling policy.
    """

    user_id: ObjectId
    prediction_type: PredictionType
    input_summary: dict[str, Any] = Field(default_factory=dict)
    predicted_class: str
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str
    model_version: str
    # Optional extra context (disease id, recommended crops, yield value...).
    details: dict[str, Any] = Field(default_factory=dict)
    image_metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionSummary(MongoDocumentModel):
    """Light-weight projection used by list endpoints."""

    user_id: ObjectId
    prediction_type: PredictionType
    predicted_class: str
    confidence: float
    model_name: str
    model_version: str
    created_at: datetime
