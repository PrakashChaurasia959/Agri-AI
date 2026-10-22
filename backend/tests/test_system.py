"""System-level tests: health, model status, documentation and error shapes."""

from __future__ import annotations

import httpx

API = "/api/v1"


# ---------------------------------------------------------------------------
# Health and status
# ---------------------------------------------------------------------------
async def test_health_reports_the_service_state(client: httpx.AsyncClient):
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] in {"ok", "degraded"}
    assert body["service"] == "AgriVision AI"
    assert body["version"]
    assert body["environment"] == "test"
    assert body["database"] in {"connected", "disconnected"}
    assert body["models"]["total"] == 3
    assert body["server_time"]


async def test_health_is_reported_as_connected_when_the_database_is_up(
    client: httpx.AsyncClient,
):
    response = await client.get(f"{API}/health")
    body = response.json()
    assert body["database"] == "connected"
    assert body["status"] == "ok"


async def test_the_model_status_endpoint_lists_every_model(
    client: httpx.AsyncClient,
):
    response = await client.get(f"{API}/models/status")
    assert response.status_code == 200
    body = response.json()

    assert body["total_count"] == 3
    assert len(body["models"]) == 3
    assert body["model_dir"]
    for model in body["models"]:
        assert model["key"]
        assert model["display_name"]
        assert model["task"]
        assert isinstance(model["available"], bool)


async def test_the_root_banner_advertises_the_api(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "AgriVision AI"
    assert body["api"] == "/api/v1"
    assert body["docs"] == "/docs"


async def test_the_api_banner_lists_the_main_endpoints(client: httpx.AsyncClient):
    response = await client.get("/api")
    assert response.status_code == 200
    body = response.json()
    assert "/api/v1/auth/login" in body["endpoints"]
    assert "/api/v1/health" in body["endpoints"]


async def test_the_processing_time_header_is_present(client: httpx.AsyncClient):
    response = await client.get(f"{API}/health")
    assert "X-Process-Time-Ms" in response.headers


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
async def test_the_openapi_schema_is_generated(client: httpx.AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    assert schema["info"]["title"] == "AgriVision AI"
    paths = schema["paths"]
    for expected in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/disease/predict",
        "/api/v1/disease/history",
        "/api/v1/crops/recommend",
        "/api/v1/yield/predict",
        "/api/v1/dashboard/overview",
        "/api/v1/dashboard/analytics",
        "/api/v1/weather/current",
        "/api/v1/weather/forecast",
        "/api/v1/weather/search",
        "/api/v1/health",
        "/api/v1/models/status",
        "/api/v1/admin/users",
        "/api/v1/admin/stats",
    ):
        assert expected in paths, f"{expected} is missing from the OpenAPI schema"


async def test_the_swagger_ui_is_served(client: httpx.AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
async def test_an_unknown_route_returns_a_json_404(client: httpx.AsyncClient):
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]
    assert body["status_code"] == 404
    assert body["path"] == "/api/v1/does-not-exist"


async def test_a_validation_error_lists_the_offending_fields(
    client: httpx.AsyncClient, account
):
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json={"nitrogen": 90}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert isinstance(body["field_errors"], dict)
    assert body["field_errors"]


async def test_the_error_body_never_contains_a_stack_trace(
    client: httpx.AsyncClient,
):
    response = await client.get("/api/v1/does-not-exist")
    assert "Traceback" not in response.text
    assert "File \"" not in response.text


async def test_a_method_not_allowed_returns_405(client: httpx.AsyncClient):
    response = await client.get(f"{API}/auth/register")
    assert response.status_code == 405
    assert response.json()["detail"]
