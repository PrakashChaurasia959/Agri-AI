"""Dashboard, weather and admin schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class DashboardOverview(BaseModel):
    """Aggregated counters for the signed-in user."""

    total_predictions: int = 0
    disease_predictions: int = 0
    crop_recommendations: int = 0
    yield_predictions: int = 0
    healthy_leaves: int = 0
    affected_leaves: int = 0
    saved_reports: int = 0
    distinct_crops_recommended: int = 0
    average_confidence: float | None = None
    first_prediction_at: datetime | None = None
    last_prediction_at: datetime | None = None


class RecentActivity(BaseModel):
    """One row of the dashboard activity feed."""

    id: str
    prediction_type: str
    predicted_class: str
    # A yield estimate has no class probability, so this is null for those
    # rows rather than an invented zero.
    confidence: float | None = None
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    """Full dashboard payload."""

    user: UserResponse
    overview: DashboardOverview
    recent_predictions: list[RecentActivity] = Field(default_factory=list)
    top_crop_recommendations: list[dict] = Field(default_factory=list)
    model_status: list[dict] = Field(default_factory=list)
    database_connected: bool = True
    generated_at: datetime


class TrendPoint(BaseModel):
    """A single point of a time-series chart."""

    date: str
    value: int


class ConfidencePoint(BaseModel):
    """A single point of the confidence distribution chart."""

    label: str
    value: int


class DashboardAnalytics(BaseModel):
    """Time series and distribution data used by the dashboard charts."""

    daily_predictions: list[TrendPoint] = Field(default_factory=list)
    prediction_type_breakdown: list[dict] = Field(default_factory=list)
    confidence_buckets: list[ConfidencePoint] = Field(default_factory=list)
    crop_distribution: list[dict] = Field(default_factory=list)
    total_records: int = 0
    window_days: int = 30


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
class WeatherLocation(BaseModel):
    """Resolved location metadata returned by the weather service."""

    name: str
    latitude: float
    longitude: float
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None


class CurrentWeather(BaseModel):
    """Current conditions."""

    temperature: float | None = None
    apparent_temperature: float | None = None
    humidity: float | None = None
    precipitation: float | None = None
    rainfall: float | None = None
    wind_speed: float | None = None
    wind_direction: int | None = None
    weather_code: int | None = None
    weather_description: str | None = None
    is_day: bool | None = None
    cloud_cover: float | None = None
    surface_pressure: float | None = None
    observed_at: datetime | None = None


class DailyForecastEntry(BaseModel):
    """One day of the daily forecast."""

    date: str
    temperature_max: float | None = None
    temperature_min: float | None = None
    precipitation_sum: float | None = None
    precipitation_probability_max: float | None = None
    wind_speed_max: float | None = None
    weather_code: int | None = None
    weather_description: str | None = None


class CurrentWeatherResponse(BaseModel):
    """Payload for ``GET /api/v1/weather/current``."""

    location: WeatherLocation
    current: CurrentWeather
    source: str
    fetched_at: datetime


class ForecastResponse(BaseModel):
    """Payload for ``GET /api/v1/weather/forecast``."""

    location: WeatherLocation
    daily: list[DailyForecastEntry] = Field(default_factory=list)
    hourly: list[dict] = Field(default_factory=list)
    source: str
    fetched_at: datetime


class WeatherSearchResult(BaseModel):
    """A geocoding candidate."""

    name: str
    latitude: float
    longitude: float
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class AdminUserListItem(UserResponse):
    """A user row in the admin table."""

    total_predictions: int = 0
    last_prediction_at: datetime | None = None


class AdminStats(BaseModel):
    """Platform-wide counters."""

    total_users: int = 0
    total_predictions: int = 0
    disease_predictions: int = 0
    crop_recommendations: int = 0
    yield_predictions: int = 0
    saved_reports: int = 0
    healthy_leaves: int = 0
    affected_leaves: int = 0
    new_users_7d: int = 0
    predictions_7d: int = 0


class AdminActivityItem(BaseModel):
    """One row of the admin activity feed."""

    id: str
    actor_email: str | None = None
    action: str
    target_type: str | None = None
    created_at: datetime
    ip_address: str | None = None


class HealthResponse(BaseModel):
    """Payload for ``GET /api/v1/health``."""

    status: str
    service: str
    version: str
    environment: str
    database: str
    database_message: str | None = None
    models: dict = Field(default_factory=dict)
    server_time: datetime


class ServiceStatus(BaseModel):
    """Health of one downstream dependency."""

    name: str
    status: str
    detail: str | None = None
    latency_ms: float | None = None
