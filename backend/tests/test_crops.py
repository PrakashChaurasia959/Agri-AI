"""Crop recommendation and yield estimation tests."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from bson import ObjectId

from tests.conftest import Account

API = "/api/v1"

VALID_SOIL = {
    "nitrogen": 90,
    "phosphorus": 45,
    "potassium": 40,
    "temperature": 22.5,
    "humidity": 82.0,
    "rainfall": 210.0,
    "ph": 6.5,
}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "field,value",
    [
        ("nitrogen", -1),
        ("phosphorus", 500),
        ("potassium", -3),
        ("temperature", 120),
        ("humidity", 150),
        ("rainfall", -5),
        ("ph", 22),
    ],
)
async def test_out_of_range_parameters_are_rejected(
    client: httpx.AsyncClient, account: Account, field: str, value: float
):
    payload = {**VALID_SOIL, field: value}
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json=payload
    )
    assert response.status_code == 422
    assert field in response.json()["field_errors"]


async def test_missing_parameters_are_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json={"nitrogen": 90}
    )
    assert response.status_code == 422
    errors = response.json()["field_errors"]
    for field in ("phosphorus", "potassium", "temperature", "humidity", "rainfall", "ph"):
        assert field in errors


async def test_non_numeric_parameters_are_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/crops/recommend",
        headers=account.headers,
        json={**VALID_SOIL, "nitrogen": "lots"},
    )
    assert response.status_code == 422


async def test_the_recommendation_endpoint_requires_authentication(
    client: httpx.AsyncClient
):
    response = await client.post(f"{API}/crops/recommend", json=VALID_SOIL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
def _crop_model_installed() -> bool:
    from ml.model_registry import registry

    return registry.is_crop_model_available()


@pytest.mark.skipif(
    not _crop_model_installed(),
    reason="The crop recommendation model has not been trained on this machine.",
)
async def test_recommendations_are_ranked_with_scores(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json=VALID_SOIL
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["recommendations"]) == 5
    for index, item in enumerate(body["recommendations"], start=1):
        assert item["rank"] == index
        assert 0.0 <= item["score"] <= 1.0
        assert item["crop"]

    scores = [item["score"] for item in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    assert body["top_crop"] == body["recommendations"][0]["crop"]
    assert body["top_score"] == body["recommendations"][0]["score"]
    assert body["model_name"]
    assert body["model_version"]
    assert body["explanation"]
    assert body["disclaimer"]
    assert body["metrics"]
    # A saved prediction must report when it was created; the endpoint used
    # to leave this null even though the record was persisted.
    assert body["record_id"]
    assert body["created_at"], "a persisted prediction must report created_at"


@pytest.mark.skipif(
    not _crop_model_installed(),
    reason="The crop recommendation model has not been trained on this machine.",
)
async def test_a_recommendation_is_persisted(
    client: httpx.AsyncClient, account: Account, memory_db
):
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json=VALID_SOIL
    )
    assert response.status_code == 200
    record_id = response.json()["record_id"]
    assert record_id

    records = memory_db.get_database()["crop_records"]
    document = await records.find_one({"_id": ObjectId(record_id)})
    assert document is not None
    assert document["crop_type"]
    assert document["soil_parameters"]["nitrogen"] == 90
    assert document["environmental_parameters"]["temperature"] == 22.5
    assert document["created_at"] is not None
    # The response timestamp must be the one that was stored, not a separate
    # clock reading or null.
    response_created = datetime.fromisoformat(
        response.json()["created_at"].replace("Z", "+00:00")
    )
    stored_created = document["created_at"]
    if stored_created.tzinfo is None:
        stored_created = stored_created.replace(tzinfo=timezone.utc)
    assert abs((response_created - stored_created).total_seconds()) < 1.0


@pytest.mark.skipif(
    not _crop_model_installed(),
    reason="The crop recommendation model has not been trained on this machine.",
)
async def test_the_history_lists_the_stored_recommendations(
    client: httpx.AsyncClient, account: Account
):
    await client.post(f"{API}/crops/recommend", headers=account.headers, json=VALID_SOIL)
    await client.post(f"{API}/crops/recommend", headers=account.headers, json=VALID_SOIL)

    response = await client.get(f"{API}/crops/history", headers=account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["crop_type"]


async def test_recommendation_returns_503_when_the_model_is_missing(
    client: httpx.AsyncClient, account: Account, empty_model_dir
):
    response = await client.post(
        f"{API}/crops/recommend", headers=account.headers, json=VALID_SOIL
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "train_crop_model" in detail
    assert "not available" in detail.lower()


# ---------------------------------------------------------------------------
# Yield estimation
# ---------------------------------------------------------------------------
def _yield_model_installed() -> bool:
    from ml.model_registry import registry

    return registry.is_yield_model_available()


@pytest.mark.parametrize(
    "field,value",
    [
        ("nitrogen", -1),
        ("humidity", 101),
        ("ph", -1),
        ("rainfall", 900),
        ("temperature", 100),
    ],
)
async def test_yield_parameters_are_validated(
    client: httpx.AsyncClient, account: Account, field: str, value: float
):
    payload = {**VALID_SOIL, "crop_type": "rice", field: value}
    response = await client.post(
        f"{API}/yield/predict", headers=account.headers, json=payload
    )
    assert response.status_code == 422
    assert field in response.json()["field_errors"]


async def test_yield_requires_a_crop_type(client: httpx.AsyncClient, account: Account):
    response = await client.post(
        f"{API}/yield/predict", headers=account.headers, json=VALID_SOIL
    )
    assert response.status_code == 422
    assert "crop_type" in response.json()["field_errors"]


async def test_yield_rejects_a_non_positive_area(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/yield/predict",
        headers=account.headers,
        json={**VALID_SOIL, "crop_type": "rice", "area_ha": 0},
    )
    assert response.status_code == 422


@pytest.mark.skipif(
    not _yield_model_installed(),
    reason="The yield model has not been trained on this machine.",
)
async def test_yield_estimation_returns_an_estimate(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/yield/predict",
        headers=account.headers,
        json={**VALID_SOIL, "crop_type": "rice", "area_ha": 2.5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["crop_type"] == "rice"
    assert body["available"] is True
    assert body["per_hectare_yield"] is not None
    assert body["per_hectare_yield"] > 0
    assert body["yield_unit"] == "tonnes per hectare"
    assert body["model_name"]
    assert body["metrics"]
    assert body["disclaimer"]
    assert body["record_id"]
    assert body["created_at"], "a persisted prediction must report created_at"

    # The total is the per-hectare figure scaled by the area.
    assert body["estimated_yield"] == pytest.approx(
        body["per_hectare_yield"] * 2.5, rel=1e-3
    )


@pytest.mark.skipif(
    not _yield_model_installed(),
    reason="The yield model has not been trained on this machine.",
)
async def test_yield_estimation_reports_a_confidence_interval(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/yield/predict",
        headers=account.headers,
        json={**VALID_SOIL, "crop_type": "wheat", "area_ha": 1.0},
    )
    assert response.status_code == 200
    interval = response.json()["confidence_interval"]
    assert interval is not None
    lower, upper = interval
    assert lower <= upper


async def test_yield_returns_503_when_the_model_is_missing(
    client: httpx.AsyncClient, account: Account, empty_model_dir
):
    response = await client.post(
        f"{API}/yield/predict",
        headers=account.headers,
        json={**VALID_SOIL, "crop_type": "rice"},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "train_yield_model" in detail
