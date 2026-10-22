"""Authorisation tests: who may reach which route, and whose data is visible."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from bson import ObjectId

from tests.conftest import Account, csrf_headers

API = "/api/v1"


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------
PROTECTED_ROUTES: list[tuple[str, str]] = [
    ("GET", f"{API}/auth/me"),
    ("PATCH", f"{API}/auth/me"),
    ("POST", f"{API}/auth/change-password"),
    ("GET", f"{API}/disease/history"),
    ("GET", f"{API}/disease/history/000000000000000000000000"),
    ("DELETE", f"{API}/disease/history/000000000000000000000000"),
    ("GET", f"{API}/crops/history"),
    ("GET", f"{API}/dashboard/overview"),
    ("GET", f"{API}/dashboard/analytics"),
    ("GET", f"{API}/admin/users"),
    ("GET", f"{API}/admin/stats"),
    ("GET", f"{API}/admin/analytics"),
    ("GET", f"{API}/admin/activity"),
    ("GET", f"{API}/admin/models"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_protected_routes_reject_anonymous_access(
    client: httpx.AsyncClient, method: str, path: str
):
    response = await client.request(method, path)
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
    assert response.json()["detail"]


async def test_a_garbage_token_is_rejected(client: httpx.AsyncClient):
    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_a_token_signed_with_another_key_is_rejected(client: httpx.AsyncClient):
    import jwt

    forged = jwt.encode(
        {
            "sub": str(ObjectId()),
            "type": "access",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        },
        "a-completely-different-secret-key",
        algorithm="HS256",
    )

    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 401


async def test_an_expired_token_is_rejected(client: httpx.AsyncClient):
    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(ObjectId()),
            "type": "access",
            "exp": int(datetime.now(timezone.utc).timestamp()) - 10,
        },
        settings.effective_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


async def test_a_refresh_token_cannot_be_used_as_an_access_token(
    client: httpx.AsyncClient,
):
    from app.core.security import create_refresh_token

    token = create_refresh_token(str(ObjectId()))
    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_a_token_for_a_deleted_user_is_rejected(
    client: httpx.AsyncClient, account: Account, memory_db
):
    users = memory_db.get_database()["users"]
    await users.delete_one({"email": account.email})

    response = await client.get(f"{API}/auth/me", headers=account.headers)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Administrator-only routes
# ---------------------------------------------------------------------------
ADMIN_ROUTES: list[tuple[str, str]] = [
    ("GET", f"{API}/admin/users"),
    ("GET", f"{API}/admin/stats"),
    ("GET", f"{API}/admin/analytics"),
    ("GET", f"{API}/admin/activity"),
    ("GET", f"{API}/admin/models"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_admin_routes_reject_a_standard_user(
    client: httpx.AsyncClient, account: Account, method: str, path: str
):
    response = await client.request(method, path, headers=account.headers)
    assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
    assert "administrator" in response.json()["detail"].lower()


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_admin_routes_accept_an_administrator(
    client: httpx.AsyncClient, admin_account: Account, method: str, path: str
):
    response = await client.request(method, path, headers=admin_account.headers)
    assert response.status_code == 200, f"{method} {path} -> {response.text}"


async def test_an_admin_can_read_a_user_detail(
    client: httpx.AsyncClient, admin_account: Account, account: Account
):
    response = await client.get(
        f"{API}/admin/users/{account.id}", headers=admin_account.headers
    )
    assert response.status_code == 200
    assert response.json()["email"] == account.email


async def test_admin_user_list_is_paginated_and_searchable(
    client: httpx.AsyncClient, admin_account: Account, account: Account
):
    response = await client.get(
        f"{API}/admin/users?page=1&page_size=10&search=farmer",
        headers=admin_account.headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 10
    assert body["pagination"]["total"] >= 1
    assert any(item["email"] == account.email for item in body["items"])


async def test_an_admin_can_promote_a_user(
    client: httpx.AsyncClient, admin_account: Account, account: Account, memory_db
):
    response = await client.patch(
        f"{API}/admin/users/{account.id}/role?role=admin",
        headers={**admin_account.headers, **csrf_headers(client)},
    )
    assert response.status_code == 200, response.text

    users = memory_db.get_database()["users"]
    document = await users.find_one({"email": account.email})
    assert document is not None
    assert document["role"] == "admin"


async def test_an_admin_role_change_is_written_to_the_audit_trail(
    client: httpx.AsyncClient, admin_account: Account, account: Account, memory_db
):
    await client.patch(
        f"{API}/admin/users/{account.id}/role?role=admin",
        headers={**admin_account.headers, **csrf_headers(client)},
    )

    events = memory_db.get_database()["audit_events"]
    document = await events.find_one({"action": "user.role_changed"})
    assert document is not None
    assert document["target_id"] == account.id
    assert document["actor_email"] == admin_account.email


async def test_the_last_administrator_cannot_be_demoted(
    client: httpx.AsyncClient, admin_account: Account
):
    response = await client.patch(
        f"{API}/admin/users/{admin_account.id}/role?role=user",
        headers={**admin_account.headers, **csrf_headers(client)},
    )
    assert response.status_code == 400
    assert "administrator" in response.json()["detail"].lower()


async def test_the_last_administrator_cannot_be_deleted(
    client: httpx.AsyncClient, admin_account: Account
):
    response = await client.delete(
        f"{API}/admin/users/{admin_account.id}",
        headers={**admin_account.headers, **csrf_headers(client)},
    )
    assert response.status_code == 400


async def test_an_invalid_role_is_rejected(
    client: httpx.AsyncClient, admin_account: Account, account: Account
):
    response = await client.patch(
        f"{API}/admin/users/{account.id}/role?role=superuser",
        headers={**admin_account.headers, **csrf_headers(client)},
    )
    assert response.status_code == 400


async def test_admin_stats_report_real_counts(
    client: httpx.AsyncClient, admin_account: Account, account: Account
):
    response = await client.get(f"{API}/admin/stats", headers=admin_account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] >= 2
    assert body["total_predictions"] >= 0
    assert "disease_predictions" in body
    assert "new_users_7d" in body


# ---------------------------------------------------------------------------
# Record ownership
# ---------------------------------------------------------------------------
async def _insert_prediction(memory_db, user_id: str, label: str = "Tomato___Late_blight"):
    predictions = memory_db.get_database()["predictions"]
    result = await predictions.insert_one(
        {
            "user_id": ObjectId(user_id),
            "prediction_type": "disease",
            "predicted_class": label,
            "confidence": 0.91,
            "model_name": "plant_disease_cnn",
            "model_version": "1.0.0",
            "input_summary": {"width": 256, "height": 256},
            "details": {"is_healthy": False},
            "image_metadata": {"format": "PNG"},
            "created_at": datetime.now(timezone.utc),
        }
    )
    return str(result.inserted_id)


async def test_history_only_lists_the_signed_in_users_records(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
):
    mine = await _insert_prediction(memory_db, account.id, "Apple___Apple_scab")
    theirs = await _insert_prediction(memory_db, other_account.id, "Grape___Black_rot")

    response = await client.get(f"{API}/disease/history", headers=account.headers)
    assert response.status_code == 200
    body = response.json()

    ids = [item["id"] for item in body["items"]]
    assert mine in ids
    assert theirs not in ids
    assert body["pagination"]["total"] == 1


async def test_another_users_prediction_detail_is_not_readable(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
):
    theirs = await _insert_prediction(memory_db, other_account.id)

    response = await client.get(
        f"{API}/disease/history/{theirs}", headers=account.headers
    )
    assert response.status_code == 404


async def test_another_users_prediction_cannot_be_deleted(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
):
    theirs = await _insert_prediction(memory_db, other_account.id)

    response = await client.delete(
        f"{API}/disease/history/{theirs}", headers=account.headers
    )
    assert response.status_code == 404

    predictions = memory_db.get_database()["predictions"]
    assert await predictions.find_one({"_id": ObjectId(theirs)}) is not None


async def test_crop_history_is_scoped_to_the_owner(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
):
    records = memory_db.get_database()["crop_records"]
    await records.insert_one(
        {
            "user_id": ObjectId(account.id),
            "crop_type": "rice",
            "soil_parameters": {"nitrogen": 90},
            "environmental_parameters": {"temperature": 22},
            "prediction_summary": {"top_crop": "rice"},
            "created_at": datetime.now(timezone.utc),
        }
    )
    await records.insert_one(
        {
            "user_id": ObjectId(other_account.id),
            "crop_type": "maize",
            "soil_parameters": {"nitrogen": 70},
            "environmental_parameters": {"temperature": 25},
            "prediction_summary": {"top_crop": "maize"},
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(f"{API}/crops/history", headers=account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["crop_type"] == "rice"


async def test_the_dashboard_only_counts_the_signed_in_users_records(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
):
    await _insert_prediction(memory_db, other_account.id)

    response = await client.get(f"{API}/dashboard/overview", headers=account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overview"]["total_predictions"] == 0
    assert body["recent_predictions"] == []


async def test_an_invalid_object_id_is_a_bad_request_not_a_server_error(
    client: httpx.AsyncClient, account: Account
):
    response = await client.get(
        f"{API}/disease/history/not-an-object-id", headers=account.headers
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()
