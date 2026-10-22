"""Unified prediction history.

The application stores two kinds of prediction:

* a **disease** detection in the ``predictions`` collection;
* a **crop recommendation** or **yield estimate** in ``crop_records``.

Users do not care about that split - the history page promises "every prediction
you have made" - so this router merges the two collections into one paginated,
searchable list and routes detail/delete requests to whichever collection owns
the record.
"""

from __future__ import annotations

from typing import Annotated, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import (
    CsrfGuardDep,
    CurrentUserDep,
    DatabaseDep,
    PaginationDep,
)
from app.database.connection import db_manager
from app.models.base import ensure_utc
from app.models.prediction import PredictionType
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.record_repository import CropRecordRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.disease import PredictionDetail, PredictionListItem

router = APIRouter(prefix="/history", tags=["History"])

VALID_TYPES = {item.value for item in PredictionType}


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid record id."
        ) from exc


def _crop_row(document: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    """Normalise a ``crop_records`` document into the history shape.

    A yield estimate has no class probability, so its ``confidence`` is
    ``None`` instead of a fabricated number.
    """
    summary = document.get("prediction_summary") or {}
    is_yield = "estimated_yield" in summary
    top_score = summary.get("top_score")

    payload: dict[str, Any] = {
        "id": str(document["_id"]),
        "prediction_type": (
            PredictionType.YIELD.value
            if is_yield
            else PredictionType.CROP_RECOMMENDATION.value
        ),
        "predicted_class": str(document.get("crop_type") or "unknown"),
        "confidence": (
            None
            if is_yield
            else (float(top_score) if isinstance(top_score, (int, float)) else None)
        ),
        "model_name": str(summary.get("model_name") or "unknown"),
        "model_version": str(summary.get("model_version") or "unknown"),
        "created_at": ensure_utc(document.get("created_at")),
        "input_summary": {
            **(document.get("soil_parameters") or {}),
            **(document.get("environmental_parameters") or {}),
        },
    }
    if detail:
        payload["details"] = summary
        payload["image_metadata"] = {}
    return payload


def _prediction_row(document: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    confidence = document.get("confidence")
    payload: dict[str, Any] = {
        "id": str(document["_id"]),
        "prediction_type": document.get("prediction_type", PredictionType.DISEASE),
        "predicted_class": str(document.get("predicted_class") or "unknown"),
        "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
        "model_name": str(document.get("model_name") or "unknown"),
        "model_version": str(document.get("model_version") or "unknown"),
        "created_at": ensure_utc(document.get("created_at")),
        "input_summary": document.get("input_summary") or {},
    }
    if detail:
        payload["details"] = document.get("details") or {}
        payload["image_metadata"] = document.get("image_metadata") or {}
    return payload


@router.get(
    "",
    response_model=PaginatedResponse[PredictionListItem],
    summary="Every prediction the signed-in user has made",
)
async def list_history(
    prediction_type: Annotated[str | None, Query(max_length=40)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    pagination: PaginationDep = None,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> PaginatedResponse[PredictionListItem]:
    """Return disease, crop and yield records as one newest-first list."""
    requested_type = (prediction_type or "").strip().lower() or None
    if requested_type is not None and requested_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="prediction_type must be one of: " + ", ".join(sorted(VALID_TYPES)),
        )

    database = db_manager.get_database()
    user_id = current_user.id

    rows: list[dict[str, Any]] = [
        _prediction_row(document)
        for document in await PredictionRepository(database).all_for_user(user_id)
    ]
    rows.extend(
        _crop_row(document)
        for document in await CropRecordRepository(database).all_for_user(user_id)
    )

    if requested_type is not None:
        rows = [row for row in rows if str(row["prediction_type"]) == requested_type]

    term = (search or "").strip().lower()
    if term:
        rows = [row for row in rows if term in str(row["predicted_class"]).lower()]

    rows.sort(key=lambda row: row["created_at"], reverse=True)

    start = pagination.skip
    page_rows = rows[start : start + pagination.limit]

    return PaginatedResponse.build(
        [PredictionListItem(**row) for row in page_rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=len(rows),
    )


async def _owned_record(
    user_id: ObjectId, record_id: ObjectId
) -> tuple[str, dict[str, Any]]:
    """Locate a record in either collection, scoped to the signed-in user."""
    database = db_manager.get_database()

    document = await PredictionRepository(database).collection.find_one(
        {"_id": record_id, "user_id": user_id}
    )
    if document is not None:
        return "prediction", document

    document = await CropRecordRepository(database).collection.find_one(
        {"_id": record_id, "user_id": user_id}
    )
    if document is not None:
        return "crop_record", document

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found."
    )


@router.get(
    "/{record_id}",
    response_model=PredictionDetail,
    summary="One prediction in full",
)
async def get_history_record(
    record_id: str,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> PredictionDetail:
    """Return a record the signed-in user owns; another user's id yields 404."""
    kind, document = await _owned_record(current_user.id, _object_id(record_id))
    row = (
        _prediction_row(document, detail=True)
        if kind == "prediction"
        else _crop_row(document, detail=True)
    )
    return PredictionDetail(**row)


@router.delete(
    "/{record_id}",
    response_model=MessageResponse,
    summary="Delete one prediction",
)
async def delete_history_record(
    record_id: str,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
    __: CsrfGuardDep = None,
) -> MessageResponse:
    """Delete a record from whichever collection owns it."""
    kind, document = await _owned_record(current_user.id, _object_id(record_id))

    database = db_manager.get_database()
    if kind == "prediction":
        collection = PredictionRepository(database).collection
    else:
        collection = CropRecordRepository(database).collection

    await collection.delete_one({"_id": document["_id"], "user_id": current_user.id})
    return MessageResponse(message="The prediction was deleted.")


__all__ = ["router"]
