"""System endpoints: health checks and model status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.database.connection import db_manager
from app.schemas.dashboard import HealthResponse
from ml.model_registry import registry as model_registry

logger = get_logger(__name__)

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health() -> HealthResponse:
    """Report the health of the API, the database and the ML models.

    The endpoint always returns ``200`` - it describes the state of the
    system rather than failing.  A failing dependency is visible in the
    ``database`` / ``models`` fields so a monitoring system can act on it.
    """
    settings = get_settings()
    models = model_registry.all_status()

    database_status = "connected" if db_manager.is_connected else "disconnected"
    database_message = (
        "MongoDB connection is active."
        if db_manager.is_connected
        else (
            db_manager.last_error
            or "MONGODB_URI is not configured - data endpoints are unavailable."
        )
    )

    overall = "ok"
    if not db_manager.is_connected:
        overall = "degraded"

    return HealthResponse(
        status=overall,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database_status,
        database_message=database_message,
        models={
            "available": models["available_count"],
            "total": models["total_count"],
            "detail": {model["key"]: model["available"] for model in models["models"]},
        },
        server_time=datetime.now(timezone.utc),
    )


@router.get("/models/status", summary="Machine learning model status")
async def models_status() -> dict:
    """Return the availability and metadata of every ML model."""
    settings = get_settings()
    models = model_registry.all_status()
    return {
        "available_count": models["available_count"],
        "total_count": models["total_count"],
        "models": models["models"],
        "model_dir": str(model_registry.model_dir),
        "device": settings.device,
        "note": (
            "Models report themselves as unavailable until the training "
            "pipeline has been run on this server."
        ),
    }
