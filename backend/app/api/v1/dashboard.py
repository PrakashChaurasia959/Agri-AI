"""Dashboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DatabaseDep
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.record_repository import (
    AuditEventRepository,
    CropRecordRepository,
    SavedReportRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.dashboard import (
    DashboardAnalytics,
    DashboardOverviewResponse,
)
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService
from ml.model_registry import registry as model_registry

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Dashboard summary",
)
async def overview(
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> DashboardOverviewResponse:
    """Return the counters, recent activity and model status for the dashboard."""
    database = db_manager.get_database()
    service = DashboardService(
        PredictionRepository(database),
        CropRecordRepository(database),
        SavedReportRepository(database),
    )
    auth = AuthService(UserRepository(database))

    overview_data = await service.build_overview(current_user.id)
    recent = await service.recent_activity(current_user.id, limit=8)
    top_crops = await CropRecordRepository(database).top_crops_for_user(
        current_user.id, limit=6
    )

    model_status = model_registry.all_status()["models"]

    from datetime import datetime, timezone

    return DashboardOverviewResponse(
        user=auth.to_response(current_user.document),
        overview=overview_data,
        recent_predictions=recent,
        top_crop_recommendations=[
            {"crop": entry.get("_id"), "count": entry.get("count", 0)}
            for entry in top_crops
        ],
        model_status=model_status,
        database_connected=db_manager.is_connected,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/analytics",
    response_model=DashboardAnalytics,
    summary="Dashboard analytics series",
)
async def analytics(
    window_days: Annotated[int, Query(ge=1, le=365)] = 30,
    current_user: CurrentUserDep = None,
    _: DatabaseDep = None,
) -> DashboardAnalytics:
    """Return the time series used by the dashboard charts."""
    database = db_manager.get_database()
    service = DashboardService(
        PredictionRepository(database),
        CropRecordRepository(database),
        SavedReportRepository(database),
    )
    return await service.build_analytics(current_user.id, window_days=window_days)
