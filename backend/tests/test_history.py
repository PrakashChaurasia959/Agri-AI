"""Unified history endpoint tests.

Disease predictions live in ``predictions`` while crop recommendations and
yield estimates live in ``crop_records``.  ``/api/v1/history`` must present one
merged list; before this endpoint existed the history page silently showed
disease predictions only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from tests.conftest import Account

API = "/api/v1"


async def _seed(memory_db, user_id: ObjectId, other_id: ObjectId):
    """Insert one disease prediction, one crop record and one yield record."""
    now = datetime.now(timezone.utc)
    database = memory_db.get_database()

    disease = await database["predictions"].insert_one(
        {
            "user_id": user_id,
            "prediction_type": "disease",
            "predicted_class": "Tomato___Late_blight",
            "confidence": 0.91,
            "model_name": "plant_disease_mobilenetv2",
            "model_version": "1.0.0",
            "input_summary": {"image_size": [224, 224]},
            "details": {"is_healthy": False},
            "image_metadata": {"width": 224, "height": 224},
            "created_at": now - timedelta(hours=2),
        }
    )
    crop = await database["crop_records"].insert_one(
        {
            "user_id": user_id,
            "crop_type": "rice",
            "soil_parameters": {"nitrogen": 90, "ph": 6.5, "soil_type": None},
            "environmental_parameters": {"temperature": 22.5, "humidity": 82.0},
            "prediction_summary": {
                "top_crop": "rice",
                "top_score": 0.93,
                "model_name": "crop_recommender_random_forest",
                "model_version": "1.0.0",
            },
            "created_at": now - timedelta(hours=1),
        }
    )
    yield_record = await database["crop_records"].insert_one(
        {
            "user_id": user_id,
            "crop_type": "maize",
            "soil_parameters": {"nitrogen": 60},
            "environmental_parameters": {"area_ha": 2.0},
            "prediction_summary": {
                "estimated_yield": 12.5,
                "per_hectare_yield": 6.25,
                "yield_unit": "tonnes per hectare",
                "model_name": "crop_yield_regressor",
                "model_version": "1.0.0",
            },
            "created_at": now,
        }
    )
    foreign = await database["crop_records"].insert_one(
        {
            "user_id": other_id,
            "crop_type": "cotton",
            "prediction_summary": {"top_crop": "cotton", "top_score": 0.8},
            "created_at": now,
        }
    )

    return {
        "disease": str(disease.inserted_id),
        "crop": str(crop.inserted_id),
        "yield": str(yield_record.inserted_id),
        "foreign": str(foreign.inserted_id),
    }


async def test_history_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API}/history")
    assert response.status_code == 401


async def test_history_merges_every_prediction_type(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.get(f"{API}/history", headers=account.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 3,
        "total_pages": 1,
        "has_next": False,
        "has_previous": False,
    }

    items = body["items"]
    # Newest first: yield, then crop recommendation, then disease.
    assert [item["id"] for item in items] == [ids["yield"], ids["crop"], ids["disease"]]
    assert {item["prediction_type"] for item in items} == {
        "disease",
        "crop_recommendation",
        "yield",
    }

    by_id = {item["id"]: item for item in items}
    assert by_id[ids["disease"]]["confidence"] == pytest.approx(0.91)
    assert by_id[ids["crop"]]["confidence"] == pytest.approx(0.93)
    # A yield estimate has no class probability, so it must be null rather
    # than a fabricated number.
    assert by_id[ids["yield"]]["confidence"] is None
    assert by_id[ids["crop"]]["model_name"] == "crop_recommender_random_forest"
    assert by_id[ids["yield"]]["model_name"] == "crop_yield_regressor"
    assert by_id[ids["crop"]]["input_summary"]["nitrogen"] == 90
    # Another user's record never leaks into the list.
    assert ids["foreign"] not in by_id


async def test_history_filters_by_prediction_type(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.get(
        f"{API}/history",
        params={"prediction_type": "yield"},
        headers=account.headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["id"] == ids["yield"]

    response = await client.get(
        f"{API}/history",
        params={"prediction_type": "disease"},
        headers=account.headers,
    )
    assert [item["id"] for item in response.json()["items"]] == [ids["disease"]]


async def test_history_search_is_case_insensitive(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    await _seed(memory_db, ObjectId(account.id), ObjectId(other_account.id))

    response = await client.get(
        f"{API}/history", params={"search": "LATE_BLIGHT"}, headers=account.headers
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["predicted_class"] == "Tomato___Late_blight"


async def test_history_rejects_an_unknown_prediction_type(
    client: httpx.AsyncClient, account: Account
) -> None:
    response = await client.get(
        f"{API}/history",
        params={"prediction_type": "banana"},
        headers=account.headers,
    )

    assert response.status_code == 422
    assert "prediction_type" in response.json()["detail"]


async def test_history_paginates(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    await _seed(memory_db, ObjectId(account.id), ObjectId(other_account.id))

    first = await client.get(
        f"{API}/history", params={"page": 1, "page_size": 2}, headers=account.headers
    )
    second = await client.get(
        f"{API}/history", params={"page": 2, "page_size": 2}, headers=account.headers
    )

    assert first.status_code == 200 and second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert len(first_body["items"]) == 2
    assert len(second_body["items"]) == 1
    assert first_body["pagination"]["has_next"] is True
    assert second_body["pagination"]["has_previous"] is True
    assert (
        first_body["pagination"]["total"] == second_body["pagination"]["total"] == 3
    )


async def test_history_detail_reads_a_crop_record(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.get(
        f"{API}/history/{ids['yield']}", headers=account.headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prediction_type"] == "yield"
    assert body["predicted_class"] == "maize"
    assert body["confidence"] is None
    assert body["details"]["estimated_yield"] == pytest.approx(12.5)


async def test_history_hides_another_users_record(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.get(
        f"{API}/history/{ids['foreign']}", headers=account.headers
    )
    assert response.status_code == 404

    response = await client.delete(
        f"{API}/history/{ids['foreign']}", headers=account.headers
    )
    assert response.status_code == 404

    # The record still exists for its real owner.
    document = await memory_db.get_database()["crop_records"].find_one(
        {"_id": ObjectId(ids["foreign"])}
    )
    assert document is not None


async def test_history_delete_removes_a_crop_record(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.delete(
        f"{API}/history/{ids['crop']}", headers=account.headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True

    document = await memory_db.get_database()["crop_records"].find_one(
        {"_id": ObjectId(ids["crop"])}
    )
    assert document is None

    # Deleting it again is a 404, not a silent success.
    again = await client.delete(f"{API}/history/{ids['crop']}", headers=account.headers)
    assert again.status_code == 404


async def test_history_delete_removes_a_disease_prediction(
    client: httpx.AsyncClient, account: Account, other_account: Account, memory_db
) -> None:
    ids = await _seed(
        memory_db, ObjectId(account.id), ObjectId(other_account.id)
    )

    response = await client.delete(
        f"{API}/history/{ids['disease']}", headers=account.headers
    )

    assert response.status_code == 200, response.text
    document = await memory_db.get_database()["predictions"].find_one(
        {"_id": ObjectId(ids["disease"])}
    )
    assert document is None


async def test_history_rejects_a_malformed_id(
    client: httpx.AsyncClient, account: Account
) -> None:
    response = await client.get(f"{API}/history/not-an-object-id", headers=account.headers)
    assert response.status_code == 400
