"""Crop recommendation and yield estimation services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.logging_config import get_logger
from ml.crop_predictor import CropPredictionResult, recommend_crops
from ml.model_registry import ModelRegistry, registry as default_registry
from ml.yield_predictor import YieldPrediction, estimate_yield

logger = get_logger(__name__)


class CropService:
    """Runs the crop recommendation model and records the outcome."""

    def __init__(self, crop_records, model_registry: ModelRegistry | None = None) -> None:
        self._records = crop_records
        self._registry = model_registry or default_registry

    async def recommend(
        self,
        payload: Any,
        *,
        user_id: ObjectId | None = None,
    ) -> tuple[CropPredictionResult, ObjectId | None, datetime | None]:
        """Recommend crops for the supplied parameters and persist the result.

        Returns the prediction, the id of the persisted record (or ``None``
        when the caller is anonymous) and the timestamp of that record.
        """
        result = recommend_crops(
            payload.feature_vector,
            model_registry=self._registry,
        )

        if user_id is None:
            return result, None, None

        soil_parameters = {
            "nitrogen": payload.nitrogen,
            "phosphorus": payload.phosphorus,
            "potassium": payload.potassium,
            "ph": payload.ph,
            "soil_type": payload.soil_type,
        }
        environmental_parameters = {
            "temperature": payload.temperature,
            "humidity": payload.humidity,
            "rainfall": payload.rainfall,
            "location": payload.location,
        }
        prediction_summary = {
            "top_crop": result.top_crop,
            "top_score": result.top_score,
            "recommendations": [item.to_dict() for item in result.recommendations],
            "model_name": result.model_name,
            "model_version": result.model_version,
        }

        document = {
            "user_id": user_id,
            "crop_type": result.top_crop or "unknown",
            "soil_parameters": soil_parameters,
            "environmental_parameters": environmental_parameters,
            "prediction_summary": prediction_summary,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            stored = await self._records.create(document)
            return result, stored["_id"], document["created_at"]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Could not persist the crop record: %s", type(exc).__name__)
            return result, None, None


class YieldService:
    """Runs the yield regression model and records the outcome."""

    def __init__(self, crop_records, model_registry: ModelRegistry | None = None) -> None:
        self._records = crop_records
        self._registry = model_registry or default_registry

    async def predict(
        self,
        payload: Any,
        *,
        user_id: ObjectId | None = None,
    ) -> tuple[YieldPrediction, ObjectId | None, datetime | None]:
        """Estimate the yield and persist the outcome.

        Returns the prediction, the id of the persisted record (or ``None``
        when the caller is anonymous) and the timestamp of that record.
        """
        result = estimate_yield(
            payload.feature_vector,
            crop_type=payload.crop_type,
            area_ha=payload.area_ha,
            model_registry=self._registry,
        )

        if user_id is None:
            return result, None, None

        document = {
            "user_id": user_id,
            "crop_type": payload.crop_type,
            "soil_parameters": {
                "nitrogen": payload.nitrogen,
                "phosphorus": payload.phosphorus,
                "potassium": payload.potassium,
                "ph": payload.ph,
                "soil_type": payload.soil_type,
            },
            "environmental_parameters": {
                "temperature": payload.temperature,
                "humidity": payload.humidity,
                "rainfall": payload.rainfall,
                "irrigation": payload.irrigation,
                "season": payload.season,
                "area_ha": payload.area_ha,
            },
            "prediction_summary": {
                "estimated_yield": result.estimated_yield,
                "per_hectare_yield": result.per_hectare_yield,
                "yield_unit": result.yield_unit,
                "confidence_interval": list(result.confidence_interval)
                if result.confidence_interval
                else None,
                "model_name": result.model_name,
                "model_version": result.model_version,
            },
            "created_at": datetime.now(timezone.utc),
        }

        try:
            stored = await self._records.create(document)
            return result, stored["_id"], document["created_at"]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Could not persist the yield record: %s", type(exc).__name__)
            return result, None, None


__all__ = ["CropService", "YieldService"]
