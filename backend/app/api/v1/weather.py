"""Weather endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.logging_config import get_logger
from app.schemas.dashboard import (
    CurrentWeatherResponse,
    ForecastResponse,
    WeatherSearchResult,
)
from app.services.weather_service import WeatherServiceError, weather_service

logger = get_logger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather"])


def _fail(error: WeatherServiceError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


@router.get(
    "/search",
    response_model=list[WeatherSearchResult],
    summary="Search for a location",
)
async def search(
    query: Annotated[str, Query(min_length=2, max_length=120)],
) -> list[WeatherSearchResult]:
    """Geocode a place name into candidate coordinates."""
    try:
        return await weather_service.search_location(query)
    except WeatherServiceError as exc:
        raise _fail(exc) from exc


@router.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Current weather",
)
async def current(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    location_name: Annotated[str | None, Query(max_length=160)] = None,
) -> CurrentWeatherResponse:
    """Return the current conditions for a coordinate."""
    try:
        return await weather_service.get_current(
            latitude, longitude, location_name=location_name
        )
    except WeatherServiceError as exc:
        raise _fail(exc) from exc


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Weather forecast",
)
async def forecast(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    location_name: Annotated[str | None, Query(max_length=160)] = None,
    days: Annotated[int, Query(ge=1, le=16)] = 7,
    hourly: bool = False,
) -> ForecastResponse:
    """Return a daily (and optionally hourly) forecast for a coordinate."""
    try:
        return await weather_service.get_forecast(
            latitude,
            longitude,
            location_name=location_name,
            days=days,
            hourly=hourly,
        )
    except WeatherServiceError as exc:
        raise _fail(exc) from exc
