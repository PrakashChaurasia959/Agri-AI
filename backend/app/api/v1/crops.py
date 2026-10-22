"""Crop recommendation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, DatabaseDep, PaginationDep
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.repositories.record_repository import CropRecordRepository
from app.schemas.common import PaginatedResponse
from app.schemas.crop import (
    CropRecommendationItem,
    CropRecommendationRequest,
    CropRecommendationResponse,
    CropRecordListItem,
)
from app.services.agriculture_service import CropService
from ml.model_registry import ModelUnavailableError

logger = get_logger(__name__)

router = APIRouter(prefix="/crops", tags=["Crop recommendation"])

MODEL_UNAVAILABLE_MESSAGE = (
    "Crop recommendations are not available yet: the recommendation model has "
    "not been trained and installed on this server. Run "
    "`python -m ml.train_crop_model` after downloading the dataset to enable it."
)


@router.post(
    "/recommend",
    response_model=CropRecommendationResponse,
    summary="Recommend crops for a set of soil and climate parameters",
)
async def recommend(
    request_model: CropRecommendationRequest,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> CropRecommendationResponse:
    """Recommend the most suitable crops for the supplied parameters."""
    repository = CropRecordRepository(db_manager.get_database())
    service = CropService(repository)

    try:
        result, record_id, created_at = await service.recommend(
            request_model, user_id=current_user.id
        )
    except ModelUnavailableError as exc:
        logger.warning("Crop model unavailable: %s", exc.code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MODEL_UNAVAILABLE_MESSAGE,
        ) from exc

    return CropRecommendationResponse(
        record_id=str(record_id) if record_id else None,
        recommendations=[
            CropRecommendationItem(
                crop=item.crop, score=item.score, rank=item.rank
            )
            for item in result.recommendations
        ],
        top_crop=result.top_crop,
        top_score=result.top_score,
        input_summary=result.input_summary,
        explanation=result.explanation,
        model_name=result.model_name,
        model_version=result.model_version,
        metrics=result.metrics,
        disclaimer=result.disclaimer,
        created_at=created_at,
    )


@router.get(
    "/history",
    response_model=PaginatedResponse[CropRecordListItem],
    summary="Crop recommendation history",
)
async def history(
    pagination: PaginationDep = None,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> PaginatedResponse[CropRecordListItem]:
    """Return the signed-in user's crop recommendation history."""
    repository = CropRecordRepository(db_manager.get_database())
    documents, total = await repository.list_for_user(
        current_user.id, skip=pagination.skip, limit=pagination.limit
    )
    items = [
        CropRecordListItem(
            id=str(document["_id"]),
            crop_type=document.get("crop_type", "unknown"),
            soil_parameters=document.get("soil_parameters", {}),
            environmental_parameters=document.get("environmental_parameters", {}),
            prediction_summary=document.get("prediction_summary", {}),
            created_at=document.get("created_at"),
        )
        for document in documents
    ]
    return PaginatedResponse.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )
