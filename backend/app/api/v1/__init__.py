"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    crops,
    dashboard,
    disease,
    history,
    system,
    weather,
    yield_estimate,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(disease.router)
api_router.include_router(history.router)
api_router.include_router(crops.router)
api_router.include_router(yield_estimate.router)
api_router.include_router(dashboard.router)
api_router.include_router(weather.router)
api_router.include_router(system.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
