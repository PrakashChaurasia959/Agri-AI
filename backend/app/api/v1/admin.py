"""Administrative endpoints.

Every route in this module depends on :func:`app.api.deps.require_admin`,
so an ordinary user receives ``403`` before any data is read.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import AdminUserDep, CsrfGuardDep, DatabaseDep, PaginationDep
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.models.base import ensure_utc
from app.models.user import UserRole
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.record_repository import (
    AuditEventRepository,
    CropRecordRepository,
    SavedReportRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.dashboard import (
    AdminActivityItem,
    AdminStats,
    AdminUserListItem,
)
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from ml.model_registry import registry as model_registry

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[])


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id."
        ) from exc


@router.get(
    "/users",
    response_model=PaginatedResponse[AdminUserListItem],
    summary="List users",
)
async def list_users(
    pagination: PaginationDep = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query(max_length=20)] = None,
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> PaginatedResponse[AdminUserListItem]:
    """Return a paginated, searchable list of users."""
    database = db_manager.get_database()
    users = UserRepository(database)
    predictions = PredictionRepository(database)
    crop_records = CropRecordRepository(database)

    documents, total = await users.list_users(
        skip=pagination.skip,
        limit=pagination.limit,
        search=search,
        role=role,
    )

    items: list[AdminUserListItem] = []
    for document in documents:
        user_id = document["_id"]
        # A user's activity spans both collections: disease predictions in
        # ``predictions`` and crop/yield records in ``crop_records``.
        count = await predictions.count_for_user(
            user_id
        ) + await crop_records.count_for_user(user_id)
        recent = [
            *(await predictions.recent_for_user(user_id, limit=1)),
            *(await crop_records.recent_for_user(user_id, limit=1)),
        ]
        timestamps = [
            stamp for stamp in (ensure_utc(row.get("created_at")) for row in recent) if stamp
        ]
        last_at = max(timestamps) if timestamps else None
        items.append(
            AdminUserListItem(
                id=str(user_id),
                name=document.get("name", ""),
                email=document.get("email", ""),
                role=document.get("role", UserRole.USER),
                location=document.get("location"),
                farm_size_hectares=document.get("farm_size_hectares"),
                primary_crops=document.get("primary_crops", []),
                created_at=document.get("created_at"),
                last_login_at=document.get("last_login_at"),
                total_predictions=count,
                last_prediction_at=last_at,
            )
        )

    return PaginatedResponse.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/users/{user_id}", response_model=AdminUserListItem, summary="User detail")
async def get_user(
    user_id: str,
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> AdminUserListItem:
    """Return a single user record."""
    object_id = _object_id(user_id)
    database = db_manager.get_database()
    users = UserRepository(database)
    predictions = PredictionRepository(database)
    crop_records = CropRecordRepository(database)

    document = await users.get_by_id(object_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    count = await predictions.count_for_user(
        object_id
    ) + await crop_records.count_for_user(object_id)
    recent = [
        *(await predictions.recent_for_user(object_id, limit=1)),
        *(await crop_records.recent_for_user(object_id, limit=1)),
    ]
    timestamps = [
        stamp for stamp in (ensure_utc(row.get("created_at")) for row in recent) if stamp
    ]
    return AdminUserListItem(
        id=str(object_id),
        name=document.get("name", ""),
        email=document.get("email", ""),
        role=document.get("role", UserRole.USER),
        location=document.get("location"),
        farm_size_hectares=document.get("farm_size_hectares"),
        primary_crops=document.get("primary_crops", []),
        created_at=document.get("created_at"),
        last_login_at=document.get("last_login_at"),
        total_predictions=count,
        last_prediction_at=max(timestamps) if timestamps else None,
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=MessageResponse,
    summary="Change a user's role",
)
async def update_role(
    user_id: str,
    request: Request,
    role: Annotated[str, Query(description="user or admin")],
    _: AdminUserDep = None,
    __: DatabaseDep = None,
    ___: CsrfGuardDep = None,
) -> MessageResponse:
    """Promote or demote a user."""
    try:
        new_role = UserRole(role.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'user' or 'admin'.",
        ) from exc

    object_id = _object_id(user_id)
    database = db_manager.get_database()
    users = UserRepository(database)

    document = await users.get_by_id(object_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if document.get("role") == UserRole.ADMIN.value and new_role != UserRole.ADMIN:
        remaining = await users.count_by_role(UserRole.ADMIN.value)
        if remaining <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one administrator account must remain.",
            )

    await users.update(object_id, {"role": new_role.value})

    audit = AuditService(AuditEventRepository(database))
    actor_id, actor_email = _admin_context(request)
    await audit.record(
        action="user.role_changed",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="user",
        target_id=str(object_id),
        metadata={"role": new_role.value},
    )

    return MessageResponse(
        message=f"The role for this user is now '{new_role.value}'."
    )


@router.delete(
    "/users/{user_id}", response_model=MessageResponse, summary="Delete a user"
)
async def delete_user(
    user_id: str,
    request: Request,
    _: AdminUserDep = None,
    __: DatabaseDep = None,
    ___: CsrfGuardDep = None,
) -> MessageResponse:
    """Delete a user account and the records that belong to it."""
    object_id = _object_id(user_id)
    database = db_manager.get_database()
    users = UserRepository(database)

    document = await users.get_by_id(object_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if document.get("role") == UserRole.ADMIN.value:
        remaining = await users.count_by_role(UserRole.ADMIN.value)
        if remaining <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last administrator account cannot be deleted.",
            )

    await users.collection.delete_one({"_id": object_id})
    await PredictionRepository(database).collection.delete_many({"user_id": object_id})
    await CropRecordRepository(database).collection.delete_many({"user_id": object_id})
    await SavedReportRepository(database).collection.delete_many({"user_id": object_id})

    audit = AuditService(AuditEventRepository(database))
    actor_id, actor_email = _admin_context(request)
    await audit.record(
        action="user.deleted",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="user",
        target_id=str(object_id),
    )

    return MessageResponse(message="The user account and its records were deleted.")


@router.get("/stats", response_model=AdminStats, summary="Platform statistics")
async def stats(
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> AdminStats:
    """Return platform-wide counters derived from MongoDB."""
    database = db_manager.get_database()
    users = UserRepository(database)
    predictions = PredictionRepository(database)
    crop_records = CropRecordRepository(database)
    reports = SavedReportRepository(database)

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    healthy = 0
    affected = 0
    async for record in predictions.collection.find(
        {"prediction_type": "disease"}, {"details.is_healthy": 1, "predicted_class": 1}
    ):
        details = record.get("details") or {}
        is_healthy = details.get("is_healthy")
        if is_healthy is None:
            label = str(record.get("predicted_class", "")).lower()
            is_healthy = "healthy" in label
        if is_healthy:
            healthy += 1
        else:
            affected += 1

    # Disease predictions live in ``predictions``; crop recommendations and
    # yield estimates live in ``crop_records``.  Both collections have to be
    # counted or the platform totals under-report by two thirds.
    disease_total = await predictions.count_all("disease")
    crop_total = await crop_records.count_kind("crop_recommendation")
    yield_total = await crop_records.count_kind("yield")

    return AdminStats(
        total_users=await users.count_all(),
        total_predictions=(
            await predictions.count_all() + await crop_records.count_all()
        ),
        disease_predictions=disease_total,
        crop_recommendations=crop_total,
        yield_predictions=yield_total,
        saved_reports=await reports.count_all(),
        healthy_leaves=healthy,
        affected_leaves=affected,
        new_users_7d=await users.count_created_since(week_ago),
        predictions_7d=(
            await predictions.count_since(week_ago)
            + await crop_records.count_since(week_ago)
        ),
    )


@router.get("/analytics", summary="Platform analytics")
async def analytics(
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> dict:
    """Return activity breakdowns for the admin analytics page."""
    database = db_manager.get_database()
    predictions = PredictionRepository(database)
    crop_records = CropRecordRepository(database)

    breakdown = await predictions.aggregate_type_breakdown()
    type_totals: dict[str, int] = {
        str(entry.get("_id") or "unknown"): int(entry.get("count", 0))
        for entry in breakdown
    }
    type_totals["crop_recommendation"] = type_totals.get(
        "crop_recommendation", 0
    ) + await crop_records.count_kind("crop_recommendation")
    type_totals["yield"] = type_totals.get("yield", 0) + await crop_records.count_kind(
        "yield"
    )
    top_classes = await predictions.distinct_classes()

    counts: dict[str, int] = {}
    async for record in predictions.collection.find(
        {"prediction_type": "disease"}, {"predicted_class": 1}
    ):
        label = str(record.get("predicted_class", "unknown"))
        counts[label] = counts.get(label, 0) + 1

    top_diseases = [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[
            :10
        ]
    ]

    return {
        "prediction_type_breakdown": [
            {"type": key, "value": value}
            for key, value in sorted(
                type_totals.items(), key=lambda item: item[1], reverse=True
            )
        ],
        "top_disease_classes": top_diseases,
        "distinct_classes": len(top_classes),
        "generated_at": datetime.now(timezone.utc),
    }


@router.get(
    "/activity",
    response_model=PaginatedResponse[AdminActivityItem],
    summary="Audit activity feed",
)
async def activity(
    pagination: PaginationDep = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> PaginatedResponse[AdminActivityItem]:
    """Return the recent audit trail."""
    database = db_manager.get_database()
    audit = AuditService(AuditEventRepository(database))
    documents, total = await audit.recent(
        skip=pagination.skip, limit=pagination.limit, action=action
    )
    items = [
        AdminActivityItem(
            id=str(document["_id"]),
            actor_email=document.get("actor_email"),
            action=document.get("action", "unknown"),
            target_type=document.get("target_type"),
            created_at=document.get("created_at") or datetime.now(timezone.utc),
            ip_address=document.get("ip_address"),
        )
        for document in documents
    ]
    return PaginatedResponse.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/models", summary="Model and service status")
async def models(
    _: AdminUserDep = None,
    __: DatabaseDep = None,
) -> dict:
    """Return the ML model inventory and the health of each service."""
    from app.core.config import get_settings

    config = get_settings()
    models = model_registry.all_status()

    return {
        "models": models["models"],
        "available_count": models["available_count"],
        "total_count": models["total_count"],
        "model_dir": str(model_registry.model_dir),
        "environment": config.environment,
        "services": {
            "database": {
                "name": "MongoDB",
                "status": "healthy" if db_manager.is_connected else "unavailable",
                "detail": (
                    "Connected"
                    if db_manager.is_connected
                    else (db_manager.last_error or "MONGODB_URI is not configured")
                ),
            },
            "weather": {
                "name": config.weather_provider,
                "status": "configured",
                "detail": (
                    "No API key required for Open-Meteo."
                    if "open-meteo.com" in config.weather_api_base_url
                    else ("API key configured" if config.weather_api_key else "API key missing")
                ),
            },
        },
    }


# ---------------------------------------------------------------------------
# Small helpers - the acting administrator is taken from the request state
# that ``get_current_user`` populated.
# ---------------------------------------------------------------------------
def _admin_context(request: Request) -> tuple[ObjectId | None, str | None]:
    user = getattr(request.state, "user", None)
    if not user:
        return None, None
    return user.get("_id"), user.get("email")
