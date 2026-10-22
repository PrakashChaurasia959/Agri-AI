"""Weather integration built on the Open-Meteo API.

Why Open-Meteo
--------------
Open-Meteo serves current conditions and forecasts **without an API key**
under a permissive (CC BY 4.0) attribution licence, which makes it usable
for a student or research deployment.  ``WEATHER_API_KEY`` is therefore
*optional* in this project - it is only consulted if the deployment is
switched to a keyed provider such as OpenWeatherMap.

Design rules
------------
* All HTTP happens in this backend service.  No key is ever shipped to the
  browser.
* Every request has an explicit timeout and a typed failure mode.
* When the upstream API is unreachable the service raises
  :class:`WeatherServiceError`, and the API layer turns that into a clear
  502/503 response.  Weather data is never fabricated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.schemas.dashboard import (
    CurrentWeather,
    CurrentWeatherResponse,
    DailyForecastEntry,
    ForecastResponse,
    WeatherLocation,
    WeatherSearchResult,
)

logger = get_logger(__name__)

# WMO weather interpretation codes used by Open-Meteo.
WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherServiceError(RuntimeError):
    """Raised when the upstream weather provider cannot be used."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def describe_weather_code(code: int | None) -> str | None:
    """Translate a WMO weather code into plain English."""
    if code is None:
        return None
    return WEATHER_CODES.get(int(code), f"Unknown weather code ({code})")


class WeatherService:
    """Thin async client for the Open-Meteo APIs."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # -- internals ------------------------------------------------------
    @property
    def provider(self) -> str:
        return self._settings.weather_provider

    def _require_api_key(self) -> None:
        """No key is required for Open-Meteo.

        The check exists so that switching ``weather_api_base_url`` to a keyed
        provider fails with an actionable message instead of an opaque 401.
        """
        if "open-meteo.com" in self._settings.weather_api_base_url:
            return
        if not self._settings.weather_api_key:
            raise WeatherServiceError(
                "This weather provider requires an API key. Set WEATHER_API_KEY "
                "in the backend environment and restart the service.",
                status_code=503,
            )

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api_key()
        timeout = httpx.Timeout(self._settings.weather_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise WeatherServiceError(
                "The weather provider did not respond in time. Please try again.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Weather provider returned HTTP %s", exc.response.status_code
            )
            raise WeatherServiceError(
                f"The weather provider returned an error (HTTP {exc.response.status_code}).",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Weather provider request failed: %s", type(exc).__name__)
            raise WeatherServiceError(
                "The weather provider could not be reached. Please try again later.",
                status_code=502,
            ) from exc
        except ValueError as exc:
            raise WeatherServiceError(
                "The weather provider returned an unreadable response.",
                status_code=502,
            ) from exc

    # -- public API -----------------------------------------------------
    async def search_location(self, query: str, count: int = 5) -> list[WeatherSearchResult]:
        """Geocode a place name into candidate coordinates."""
        params = {
            "name": query,
            "count": max(1, min(count, 20)),
            "language": "en",
            "format": "json",
        }
        payload = await self._get_json(self._settings.weather_geocoding_base_url, params)
        results: list[WeatherSearchResult] = []
        for item in payload.get("results", []) or []:
            try:
                results.append(
                    WeatherSearchResult(
                        name=str(item.get("name", "Unknown")),
                        latitude=float(item["latitude"]),
                        longitude=float(item["longitude"]),
                        country=item.get("country"),
                        admin1=item.get("admin1"),
                        timezone=item.get("timezone"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return results

    async def get_current(
        self, latitude: float, longitude: float, location_name: str | None = None
    ) -> CurrentWeatherResponse:
        """Fetch the current conditions for a coordinate."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,"
                "is_day,cloud_cover,surface_pressure"
            ),
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        payload = await self._get_json(self._settings.weather_api_base_url, params)
        current_raw = payload.get("current") or {}
        timezone_name = payload.get("timezone")

        observed_at: datetime | None = None
        raw_time = current_raw.get("time")
        if raw_time:
            try:
                observed_at = datetime.fromisoformat(str(raw_time))
            except ValueError:
                observed_at = None

        current = CurrentWeather(
            temperature=_maybe_float(current_raw.get("temperature_2m")),
            apparent_temperature=_maybe_float(current_raw.get("apparent_temperature")),
            humidity=_maybe_float(current_raw.get("relative_humidity_2m")),
            precipitation=_maybe_float(current_raw.get("precipitation")),
            rainfall=_maybe_float(current_raw.get("rain")),
            wind_speed=_maybe_float(current_raw.get("wind_speed_10m")),
            wind_direction=_maybe_int(current_raw.get("wind_direction_10m")),
            weather_code=_maybe_int(current_raw.get("weather_code")),
            weather_description=describe_weather_code(current_raw.get("weather_code")),
            is_day=_maybe_bool(current_raw.get("is_day")),
            cloud_cover=_maybe_float(current_raw.get("cloud_cover")),
            surface_pressure=_maybe_float(current_raw.get("surface_pressure")),
            observed_at=observed_at,
        )

        location = WeatherLocation(
            name=location_name or f"{latitude:.4f}, {longitude:.4f}",
            latitude=latitude,
            longitude=longitude,
            country=None,
            admin1=None,
            timezone=timezone_name,
        )

        return CurrentWeatherResponse(
            location=location,
            current=current,
            source=self.provider,
            fetched_at=datetime.now(timezone.utc),
        )

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str | None = None,
        days: int = 7,
        hourly: bool = False,
    ) -> ForecastResponse:
        """Fetch a daily (and optionally hourly) forecast for a coordinate."""
        days = max(1, min(days, 16))
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
            ),
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
            "forecast_days": days,
        }
        if hourly:
            params["hourly"] = "temperature_2m,precipitation,relative_humidity_2m"

        payload = await self._get_json(self._settings.weather_api_base_url, params)

        daily_raw = payload.get("daily") or {}
        daily_entries: list[DailyForecastEntry] = []
        dates = daily_raw.get("time") or []
        for index, date_value in enumerate(dates):
            code = _maybe_int(_safe_index(daily_raw.get("weather_code"), index))
            daily_entries.append(
                DailyForecastEntry(
                    date=str(date_value),
                    temperature_max=_maybe_float(
                        _safe_index(daily_raw.get("temperature_2m_max"), index)
                    ),
                    temperature_min=_maybe_float(
                        _safe_index(daily_raw.get("temperature_2m_min"), index)
                    ),
                    precipitation_sum=_maybe_float(
                        _safe_index(daily_raw.get("precipitation_sum"), index)
                    ),
                    precipitation_probability_max=_maybe_float(
                        _safe_index(
                            daily_raw.get("precipitation_probability_max"), index
                        )
                    ),
                    wind_speed_max=_maybe_float(
                        _safe_index(daily_raw.get("wind_speed_10m_max"), index)
                    ),
                    weather_code=code,
                    weather_description=describe_weather_code(code),
                )
            )

        hourly_entries: list[dict[str, Any]] = []
        hourly_raw = payload.get("hourly") or {}
        if hourly_raw:
            times = hourly_raw.get("time") or []
            for index, time_value in enumerate(times[:48]):
                hourly_entries.append(
                    {
                        "time": str(time_value),
                        "temperature": _maybe_float(
                            _safe_index(hourly_raw.get("temperature_2m"), index)
                        ),
                        "precipitation": _maybe_float(
                            _safe_index(hourly_raw.get("precipitation"), index)
                        ),
                        "humidity": _maybe_float(
                            _safe_index(hourly_raw.get("relative_humidity_2m"), index)
                        ),
                    }
                )

        location = WeatherLocation(
            name=location_name or f"{latitude:.4f}, {longitude:.4f}",
            latitude=latitude,
            longitude=longitude,
            country=None,
            admin1=None,
            timezone=payload.get("timezone"),
        )

        return ForecastResponse(
            location=location,
            daily=daily_entries,
            hourly=hourly_entries,
            source=self.provider,
            fetched_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Small coercion helpers - the upstream API sometimes omits a value.
# ---------------------------------------------------------------------------
def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _maybe_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "day"}
    return None


def _safe_index(values: Any, index: int) -> Any:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


weather_service = WeatherService()
