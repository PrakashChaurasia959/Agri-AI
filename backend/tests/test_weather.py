"""Weather integration tests.

The upstream Open-Meteo API is replaced by an ``httpx`` mock transport, so
the tests are deterministic and never touch the network.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

API = "/api/v1"

GEOCODING_PAYLOAD: dict[str, Any] = {
    "results": [
        {
            "name": "Nashik",
            "latitude": 19.9975,
            "longitude": 73.7898,
            "country": "India",
            "admin1": "Maharashtra",
            "timezone": "Asia/Kolkata",
        },
        {
            "name": "Nashville",
            "latitude": 36.1627,
            "longitude": -86.7816,
            "country": "United States",
            "admin1": "Tennessee",
            "timezone": "America/Chicago",
        },
    ]
}

CURRENT_PAYLOAD: dict[str, Any] = {
    "latitude": 19.9975,
    "longitude": 73.7898,
    "timezone": "Asia/Kolkata",
    "current": {
        "time": "2024-06-01T10:30",
        "temperature_2m": 29.4,
        "apparent_temperature": 32.1,
        "relative_humidity_2m": 68,
        "precipitation": 0.0,
        "rain": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 11.5,
        "wind_direction_10m": 245,
        "is_day": 1,
        "cloud_cover": 40,
        "surface_pressure": 1004.2,
    },
}

FORECAST_PAYLOAD: dict[str, Any] = {
    "latitude": 19.9975,
    "longitude": 73.7898,
    "timezone": "Asia/Kolkata",
    "daily": {
        "time": ["2024-06-01", "2024-06-02", "2024-06-03"],
        "weather_code": [0, 61, 95],
        "temperature_2m_max": [31.2, 28.9, 26.4],
        "temperature_2m_min": [23.1, 22.4, 21.9],
        "precipitation_sum": [0.0, 4.2, 12.8],
        "precipitation_probability_max": [5, 60, 90],
        "wind_speed_10m_max": [14.0, 18.5, 22.1],
    },
}


def _make_transport(
    *,
    geocoding: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
    forecast: dict[str, Any] | None = None,
    status_code: int = 200,
) -> httpx.MockTransport:
    """Build a transport that answers the three Open-Meteo endpoints."""

    def handler(request: httpx.Request) -> httpx.Response:
        # The geocoding service lives on a different *host* than the forecast
        # service, so the host has to be inspected - not only the path.
        if "geocoding" in request.url.host:
            payload = GEOCODING_PAYLOAD if geocoding is None else geocoding
        elif "current" in request.url.params:
            payload = CURRENT_PAYLOAD if current is None else current
        else:
            payload = FORECAST_PAYLOAD if forecast is None else forecast
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


@pytest.fixture()
def weather_transport(monkeypatch: pytest.MonkeyPatch) -> httpx.MockTransport:
    """Install a mock transport into the weather service."""
    transport = _make_transport()
    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(
        "app.services.weather_service.httpx.AsyncClient", factory, raising=True
    )
    return transport


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
async def test_location_search_returns_candidates(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(f"{API}/weather/search", params={"query": "Nashik"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["name"] == "Nashik"
    assert results[0]["latitude"] == pytest.approx(19.9975)
    assert results[0]["country"] == "India"


async def test_location_search_requires_a_query(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(f"{API}/weather/search")
    assert response.status_code == 422


async def test_location_search_rejects_a_too_short_query(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(f"{API}/weather/search", params={"query": "N"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Current conditions
# ---------------------------------------------------------------------------
async def test_current_weather_returns_the_observed_values(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(
        f"{API}/weather/current",
        params={
            "latitude": 19.9975,
            "longitude": 73.7898,
            "location_name": "Nashik",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["location"]["name"] == "Nashik"
    assert body["current"]["temperature"] == pytest.approx(29.4)
    assert body["current"]["humidity"] == pytest.approx(68.0)
    assert body["current"]["wind_speed"] == pytest.approx(11.5)
    assert body["current"]["weather_code"] == 2
    assert body["current"]["weather_description"] == "Partly cloudy"
    assert body["current"]["is_day"] is True
    assert body["source"] == "Open-Meteo"
    assert body["fetched_at"]


async def test_current_weather_validates_the_coordinates(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(
        f"{API}/weather/current", params={"latitude": 999, "longitude": 0}
    )
    assert response.status_code == 422


async def test_current_weather_requires_coordinates(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(f"{API}/weather/current")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------
async def test_the_forecast_returns_one_entry_per_day(
    client: httpx.AsyncClient, weather_transport
):
    response = await client.get(
        f"{API}/weather/forecast",
        params={"latitude": 19.9975, "longitude": 73.7898, "days": 3},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["daily"]) == 3
    first = body["daily"][0]
    assert first["date"] == "2024-06-01"
    assert first["temperature_max"] == pytest.approx(31.2)
    assert first["temperature_min"] == pytest.approx(23.1)
    assert first["weather_description"] == "Clear sky"
    assert body["daily"][2]["weather_description"] == "Thunderstorm"
    assert body["source"] == "Open-Meteo"


async def test_the_forecast_day_count_is_bounded(
    client: httpx.AsyncClient, weather_transport
):
    too_many = await client.get(
        f"{API}/weather/forecast",
        params={"latitude": 19.9975, "longitude": 73.7898, "days": 30},
    )
    assert too_many.status_code == 422

    too_few = await client.get(
        f"{API}/weather/forecast",
        params={"latitude": 19.9975, "longitude": 73.7898, "days": 0},
    )
    assert too_few.status_code == 422


# ---------------------------------------------------------------------------
# Failure handling - the service must never fabricate weather
# ---------------------------------------------------------------------------
async def test_an_upstream_server_error_becomes_a_502(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        transport = httpx.MockTransport(
            lambda request: httpx.Response(500, text="upstream failure")
        )
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", factory)

    response = await client.get(
        f"{API}/weather/current", params={"latitude": 19.9975, "longitude": 73.7898}
    )
    assert response.status_code == 502
    assert "weather provider" in response.json()["detail"].lower()


async def test_a_network_failure_becomes_a_502(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host", request=request)

        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", factory)

    response = await client.get(
        f"{API}/weather/forecast", params={"latitude": 19.9975, "longitude": 73.7898}
    )
    assert response.status_code == 502
    assert "could not be reached" in response.json()["detail"].lower()


async def test_an_unreadable_response_becomes_a_502(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>not json</html>")
        )
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", factory)

    response = await client.get(
        f"{API}/weather/current", params={"latitude": 19.9975, "longitude": 73.7898}
    )
    assert response.status_code == 502


async def test_a_missing_location_returns_an_empty_list_not_an_error(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"results": []})
        )
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("app.services.weather_service.httpx.AsyncClient", factory)

    response = await client.get(f"{API}/weather/search", params={"query": "Nowhere"})
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Provider contract
# ---------------------------------------------------------------------------
def test_the_weather_code_table_covers_the_wmo_codes():
    from app.services.weather_service import WEATHER_CODES, describe_weather_code

    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(95) == "Thunderstorm"
    assert describe_weather_code(61) == "Slight rain"
    assert describe_weather_code(None) is None
    assert "Unknown" in (describe_weather_code(1234) or "")
    assert len(WEATHER_CODES) >= 25


def test_the_weather_service_does_not_require_an_api_key_for_open_meteo():
    from app.services.weather_service import WeatherService

    service = WeatherService()
    # No exception - Open-Meteo works without a key.
    service._require_api_key()


def test_a_keyed_provider_without_a_key_raises_an_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.core.config import get_settings
    from app.services.weather_service import WeatherService, WeatherServiceError

    settings = get_settings()
    monkeypatch.setattr(settings, "weather_api_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(settings, "weather_api_key", "")

    with pytest.raises(WeatherServiceError) as excinfo:
        WeatherService()._require_api_key()
    assert excinfo.value.status_code == 503
    assert "WEATHER_API_KEY" in excinfo.value.message


def test_the_weather_payload_is_valid_json():
    """A guard against a malformed fixture."""
    assert json.loads(json.dumps(CURRENT_PAYLOAD))["current"]["temperature_2m"] == 29.4
