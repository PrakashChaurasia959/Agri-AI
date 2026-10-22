"""Tests for the database failure behaviour.

The API must never pretend to work when MongoDB is unreachable - it has to
answer with a clear ``503`` and an actionable message.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from tests.conftest import Account

API = "/api/v1"


async def test_health_reports_a_disconnected_database(
    client: httpx.AsyncClient, disconnected_db
):
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "disconnected"
    assert body["status"] == "degraded"
    assert body["database_message"]


async def test_registration_returns_503_when_the_database_is_down(
    client: httpx.AsyncClient, disconnected_db
):
    response = await client.post(
        f"{API}/auth/register",
        json={
            "name": "No Database",
            "email": "nodb@example.com",
            "password": "StrongPass123",
        },
    )
    assert response.status_code == 503
    assert "database" in response.json()["detail"].lower()


async def test_login_returns_503_when_the_database_is_down(
    client: httpx.AsyncClient, disconnected_db
):
    response = await client.post(
        f"{API}/auth/login",
        json={"email": "nodb@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 503


async def test_authenticated_routes_return_503_when_the_database_is_down(
    client: httpx.AsyncClient, disconnected_db
):
    """A valid token cannot be verified without a database."""
    import jwt
    from bson import ObjectId

    from app.core.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(ObjectId()),
            "type": "access",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        },
        settings.effective_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 503
    assert "database" in response.json()["detail"].lower()


async def test_the_dashboard_returns_503_when_the_database_is_down(
    client: httpx.AsyncClient, disconnected_db
):
    import jwt
    from bson import ObjectId

    from app.core.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(ObjectId()),
            "type": "access",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        },
        settings.effective_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        f"{API}/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 503


async def test_the_model_status_endpoint_still_works_without_a_database(
    client: httpx.AsyncClient, disconnected_db
):
    """The health and model endpoints describe the system; they must not fail."""
    response = await client.get(f"{API}/models/status")
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 3
    assert len(body["models"]) == 3


async def test_data_is_persisted_and_read_back(
    client: httpx.AsyncClient, account: Account, memory_db
):
    """A round trip through the repository layer."""
    from datetime import datetime, timezone

    from bson import ObjectId

    predictions = memory_db.get_database()["predictions"]
    await predictions.insert_one(
        {
            "user_id": ObjectId(account.id),
            "prediction_type": "disease",
            "predicted_class": "Tomato___Early_blight",
            "confidence": 0.88,
            "model_name": "plant_disease_cnn",
            "model_version": "1.0.0",
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(f"{API}/disease/history", headers=account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["predicted_class"] == "Tomato___Early_blight"


async def test_the_unique_email_index_is_enforced(
    client: httpx.AsyncClient, memory_db
):
    users = memory_db.get_database()["users"]
    index_names = await users.index_information()
    assert any("email" in str(spec) for spec in index_names.values())
