"""Disease detection endpoints."""

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUserDep, DatabaseDep, PaginationDep
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.disease import DiseasePredictionResponse, PredictionDetail, PredictionListItem
from app.services.disease_service import DiseaseService
from ml.model_registry import ModelUnavailableError
from ml.preprocessing import ImageValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/disease", tags=["Disease detection"])

MODEL_UNAVAILABLE_MESSAGE = (
    "Disease detection is not available yet: the MobileNetV2 classifier has not "
    "been trained and installed on this server. Run "
    "`python -m ml.train_cnn` after preparing the PlantVillage dataset to enable it."
)


def _repository() -> PredictionRepository:
    return PredictionRepository(db_manager.get_database())


def _object_id(value: str, label: str = "identifier") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label}.",
        ) from exc


async def _read_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload without letting an oversized body exhaust memory."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ImageValidationError(
                f"The image is larger than the {max_bytes / (1024 * 1024):.0f} MB limit.",
                "file_too_large",
            )
        chunks.append(chunk)
    if total == 0:
        raise ImageValidationError("The uploaded file is empty.", "empty_file")
    return b"".join(chunks)


@router.post(
    "/predict",
    response_model=DiseasePredictionResponse,
    summary="Classify a leaf image",
)
async def predict(
    file: Annotated[UploadFile, File(description="Leaf image (JPEG, PNG or WebP)")],
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> DiseasePredictionResponse:
    """Run the disease classifier on an uploaded leaf image."""
    settings = get_settings()

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file must be an image (JPEG, PNG or WebP).",
        )

    try:
        image_bytes = await _read_bounded(file, settings.max_upload_bytes)
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc

    service = DiseaseService(_repository())
    try:
        result, prediction_id, created_at = await service.predict(
            image_bytes, user_id=current_user.id
        )
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except ModelUnavailableError as exc:
        logger.warning("Disease model unavailable: %s", exc.code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MODEL_UNAVAILABLE_MESSAGE,
        ) from exc
    finally:
        await file.close()

    payload_dict = result.to_dict()
    return DiseasePredictionResponse(
        prediction_id=str(prediction_id) if prediction_id else None,
        predicted_class=payload_dict["predicted_class"],
        display_name=payload_dict["display_name"],
        confidence=payload_dict["confidence"],
        confidence_percent=payload_dict["confidence_percent"],
        is_healthy=payload_dict["is_healthy"],
        is_certain=payload_dict["is_certain"],
        uncertainty_message=payload_dict["uncertainty_message"],
        model_name=payload_dict["model_name"],
        model_version=payload_dict["model_version"],
        inference_ms=payload_dict["inference_ms"],
        top_predictions=payload_dict["top_predictions"],
        disease_info=payload_dict["disease_info"] or None,
        image=payload_dict["image"],
        saved=prediction_id is not None,
        created_at=created_at,
    )


@router.get(
    "/history",
    response_model=PaginatedResponse[PredictionListItem],
    summary="Prediction history",
)
async def history(
    pagination: PaginationDep = None,
    prediction_type: Annotated[str | None, Query(max_length=40)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> PaginatedResponse[PredictionListItem]:
    """Return the signed-in user's prediction history."""
    repository = _repository()
    documents, total = await repository.list_for_user(
        current_user.id,
        skip=pagination.skip,
        limit=pagination.limit,
        prediction_type=prediction_type,
        search=search,
    )
    items = [
        PredictionListItem(
            id=str(document["_id"]),
            prediction_type=document.get("prediction_type"),
            predicted_class=document.get("predicted_class", "unknown"),
            confidence=float(document.get("confidence", 0.0)),
            model_name=document.get("model_name", "unknown"),
            model_version=document.get("model_version", "unknown"),
            created_at=document.get("created_at"),
            input_summary=document.get("input_summary", {}),
        )
        for document in documents
    ]
    return PaginatedResponse.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get(
    "/history/{prediction_id}",
    response_model=PredictionDetail,
    summary="Prediction detail",
)
async def history_detail(
    prediction_id: str,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> PredictionDetail:
    """Return one of the signed-in user's saved predictions."""
    object_id = _object_id(prediction_id, "prediction id")
    repository = _repository()
    document = await repository.get_for_user(object_id, current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found.",
        )
    return PredictionDetail(
        id=str(document["_id"]),
        prediction_type=document.get("prediction_type"),
        predicted_class=document.get("predicted_class", "unknown"),
        confidence=float(document.get("confidence", 0.0)),
        model_name=document.get("model_name", "unknown"),
        model_version=document.get("model_version", "unknown"),
        created_at=document.get("created_at"),
        input_summary=document.get("input_summary", {}),
        details=document.get("details", {}),
        image_metadata=document.get("image_metadata", {}),
    )


@router.delete(
    "/history/{prediction_id}",
    response_model=MessageResponse,
    summary="Delete a saved prediction",
)
async def delete_history(
    prediction_id: str,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> MessageResponse:
    """Delete one of the signed-in user's saved predictions."""
    object_id = _object_id(prediction_id, "prediction id")
    repository = _repository()
    deleted = await repository.delete_for_user(object_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found.",
        )
    return MessageResponse(message="Prediction deleted.")
