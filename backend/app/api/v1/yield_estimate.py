"""Crop yield estimation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, DatabaseDep
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.repositories.record_repository import CropRecordRepository
from app.schemas.crop import YieldPredictionRequest, YieldPredictionResponse
from app.services.agriculture_service import YieldService
from ml.model_registry import ModelUnavailableError

logger = get_logger(__name__)

router = APIRouter(prefix="/yield", tags=["Yield estimation"])

MODEL_UNAVAILABLE_MESSAGE = (
    "Yield estimation is not available yet: the yield regression model has not "
    "been trained and installed on this server. Run "
    "`python -m ml.train_yield_model` after downloading the dataset to enable it."
)


@router.post(
    "/predict",
    response_model=YieldPredictionResponse,
    summary="Estimate the yield for a crop and a set of field conditions",
)
async def predict(
    payload: YieldPredictionRequest,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> YieldPredictionResponse:
    """Estimate the expected yield for the supplied conditions."""
    repository = CropRecordRepository(db_manager.get_database())
    service = YieldService(repository)

    try:
        result, record_id, created_at = await service.predict(
            payload, user_id=current_user.id
        )
    except ModelUnavailableError as exc:
        logger.warning("Yield model unavailable: %s", exc.code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MODEL_UNAVAILABLE_MESSAGE,
        ) from exc

    data = result.to_dict()
    interval = data.get("confidence_interval")
    return YieldPredictionResponse(
        record_id=str(record_id) if record_id else None,
        crop_type=data["crop_type"],
        estimated_yield=data["estimated_yield"],
        yield_unit=data["yield_unit"],
        per_hectare_yield=data["per_hectare_yield"],
        confidence_interval=(tuple(interval) if interval else None),
        model_name=data["model_name"],
        model_version=data["model_version"],
        metrics=data["metrics"],
        input_summary=data["input_summary"],
        disclaimer=data["disclaimer"],
        available=data["available"],
        created_at=created_at,
    )
