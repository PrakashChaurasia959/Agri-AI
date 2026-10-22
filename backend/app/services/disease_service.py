"""Disease detection service.

Bridges the ML layer and the persistence layer: run inference, then persist a
prediction record for an authenticated user.  If persistence fails the
prediction is *not* silently swallowed - the caller is told the prediction
succeeded but could not be saved.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.models.prediction import PredictionType
from ml.config import InferenceConfig
from ml.model_registry import ModelRegistry, ModelUnavailableError, registry as default_registry
from ml.predict import InferenceResult, predict_disease
from ml.preprocessing import ImageValidationError

logger = get_logger(__name__)


class DiseaseService:
    """Runs disease inference and records the outcome."""

    def __init__(
        self,
        predictions,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        self._predictions = predictions
        self._registry = model_registry or default_registry

    async def predict(
        self,
        image_bytes: bytes,
        *,
        user_id: ObjectId | None = None,
    ) -> tuple[InferenceResult, ObjectId | None, datetime | None]:
        """Classify a leaf image and persist the result when possible.

        Returns the inference result, the id of the stored record and the
        timestamp of that record.  Both are ``None`` when the record could
        not be persisted (or the caller is anonymous).
        """
        settings = get_settings()
        result = predict_disease(
            image_bytes,
            model_registry=self._registry,
            confidence_threshold=settings.inference_confidence_threshold,
            max_bytes=settings.max_upload_bytes,
            min_dimension=settings.image_min_dimension,
            max_dimension=settings.image_max_dimension,
            allowed_mime_types=settings.allowed_image_mimes,
        )

        if user_id is None:
            return result, None, None

        document = {
            "user_id": user_id,
            "prediction_type": PredictionType.DISEASE.value,
            "input_summary": {
                "file_name": result.image_info.get("format"),
                "width": result.image_info.get("width"),
                "height": result.image_info.get("height"),
                "file_size": result.image_info.get("file_size"),
            },
            "predicted_class": result.predicted_class,
            "confidence": round(float(result.confidence), 6),
            "model_name": result.model_name,
            "model_version": result.model_version,
            "details": {
                "display_name": result.display_name,
                "is_healthy": result.is_healthy,
                "is_certain": result.is_certain,
                "uncertainty_message": result.uncertainty_message,
                "top_predictions": result.top_predictions,
                "disease_info": result.disease_info,
                "inference_ms": result.inference_ms,
            },
            # Image binaries are never stored inside a MongoDB document.
            "image_metadata": result.image_info,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            stored = await self._predictions.create(document)
            return result, stored["_id"], document["created_at"]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Could not persist the disease prediction: %s", type(exc).__name__)
            return result, None, None


__all__ = ["DiseaseService", "ImageValidationError", "ModelUnavailableError"]
