"""The in-memory emulator must behave like the real async driver.

The test-suite runs against :mod:`app.database.memory`, a ``mongomock``
facade.  A facade is only useful if it is *contract-identical* to the thing it
replaces.  If the facade is more forgiving than the real driver, a defect can
pass the entire suite and fail the first time the application meets a real
cluster.

That is not hypothetical: ``AsyncCollection.aggregate`` is a **coroutine** in
:class:`pymongo.asynchronous.collection.AsyncCollection`, while ``find`` is a
plain method that returns an async cursor.  The facade originally implemented
``aggregate`` synchronously, so three repositories that iterated

    [doc async for doc in self.collection.aggregate(pipeline)]

without awaiting it passed every test and raised

    TypeError: 'async for' requires an object with __aiter__ method, got coroutine

in production.  The tests below pin the contract so it cannot drift again.
"""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.asyncio


# Methods the repositories actually call.  ``find`` is deliberately included
# because it is the outlier: the one read on the collection that is *not* a
# coroutine.
COLLECTION_METHODS = (
    "find",
    "find_one",
    "find_one_and_update",
    "aggregate",
    "count_documents",
    "distinct",
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "delete_one",
    "delete_many",
    "create_index",
    "drop",
    "index_information",
)


def test_the_emulator_matches_the_real_drivers_awaitability() -> None:
    """Every facade method must be awaitable exactly when the real one is."""
    from pymongo.asynchronous.collection import AsyncCollection as RealAsyncCollection

    from app.database.memory import AsyncCollection as MemoryAsyncCollection

    mismatches: list[str] = []
    for name in COLLECTION_METHODS:
        real = getattr(RealAsyncCollection, name, None)
        fake = getattr(MemoryAsyncCollection, name, None)
        if real is None or fake is None:
            mismatches.append(f"{name}: missing on one of the two classes")
            continue

        real_is_coroutine = inspect.iscoroutinefunction(real)
        fake_is_coroutine = inspect.iscoroutinefunction(fake)
        if real_is_coroutine != fake_is_coroutine:
            expected = "a coroutine" if real_is_coroutine else "a plain method"
            mismatches.append(
                f"{name}: the real driver exposes {expected}, "
                f"the emulator does not"
            )

    assert not mismatches, (
        "The in-memory emulator has drifted from the real driver's contract:\n  "
        + "\n  ".join(mismatches)
    )


def test_find_is_synchronous_and_aggregate_is_awaitable_in_both() -> None:
    """State the two facts the contract test above is protecting."""
    from pymongo.asynchronous.collection import AsyncCollection as RealAsyncCollection

    from app.database.memory import AsyncCollection as MemoryAsyncCollection

    assert not inspect.iscoroutinefunction(RealAsyncCollection.find)
    assert not inspect.iscoroutinefunction(MemoryAsyncCollection.find)

    assert inspect.iscoroutinefunction(RealAsyncCollection.aggregate)
    assert inspect.iscoroutinefunction(MemoryAsyncCollection.aggregate)


# ---------------------------------------------------------------------------
# The aggregating repository methods, exercised through the emulator.
# ---------------------------------------------------------------------------
async def _seed(memory_db, user_id) -> None:
    from datetime import datetime, timedelta, timezone

    from bson import ObjectId

    records = memory_db.get_database()["crop_records"]
    now = datetime.now(timezone.utc)
    crop_time = now - timedelta(minutes=10)
    documents = [
        {
            "user_id": user_id,
            "crop_type": crop,
            "prediction_summary": {"top_crop": crop, "top_score": score},
            "created_at": crop_time,
        }
        for crop, score in (
            ("rice", 0.90),
            ("rice", 0.80),
            ("rice", 0.70),
            ("maize", 0.85),
            ("maize", 0.75),
            ("wheat", 0.65),
        )
    ]
    documents.extend(
        [
            # A yield record: it names a crop but must not be ranked as a
            # recommendation.  It is the newest row so the feed includes it.
            {
                "user_id": user_id,
                "crop_type": "sorghum",
                "prediction_summary": {
                    "estimated_yield": 42.0,
                    "per_hectare_yield": 42.0,
                },
                "created_at": now,
            },
            # Another user's records must never appear in the result.
            {
                "user_id": ObjectId(),
                "crop_type": "cotton",
                "prediction_summary": {"top_crop": "cotton", "top_score": 0.99},
                "created_at": now,
            },
        ]
    )
    await records.insert_many(documents)

    predictions = memory_db.get_database()["predictions"]
    await predictions.insert_many(
        [
            {
                "user_id": user_id,
                "prediction_type": "disease",
                "predicted_class": "Tomato___Early_blight",
                "confidence": 0.91,
                "model_name": "plant_disease_mobilenetv2",
                "model_version": "1.0.0",
                "details": {"is_healthy": False},
                "created_at": now - timedelta(days=1),
            },
            {
                "user_id": user_id,
                "prediction_type": "disease",
                "predicted_class": "Tomato___healthy",
                "confidence": 0.97,
                "model_name": "plant_disease_mobilenetv2",
                "model_version": "1.0.0",
                "details": {"is_healthy": True},
                "created_at": now,
            },
            {
                "user_id": user_id,
                "prediction_type": "disease",
                "predicted_class": "Potato___Late_blight",
                "confidence": 0.72,
                "model_name": "plant_disease_mobilenetv2",
                "model_version": "1.0.0",
                "details": {"is_healthy": False},
                "created_at": now,
            },
        ]
    )


async def test_top_crops_for_user_awaits_the_aggregation(memory_db) -> None:
    """A missing ``await`` on ``aggregate`` fails here, not only on a cluster."""
    from bson import ObjectId

    from app.repositories.record_repository import CropRecordRepository

    user_id = ObjectId()
    await _seed(memory_db, user_id)

    repository = CropRecordRepository(memory_db.get_database())
    rows = await repository.top_crops_for_user(user_id, limit=6)

    assert [row["_id"] for row in rows] == ["rice", "maize", "wheat"]
    assert [row["count"] for row in rows] == [3, 2, 1]


async def test_aggregate_type_breakdown_awaits_the_aggregation(memory_db) -> None:
    from bson import ObjectId

    from app.repositories.prediction_repository import PredictionRepository

    await _seed(memory_db, ObjectId())

    repository = PredictionRepository(memory_db.get_database())
    rows = await repository.aggregate_type_breakdown()

    counts = {row["_id"]: row["count"] for row in rows}
    assert counts == {"disease": 3}


async def test_aggregate_daily_counts_awaits_the_aggregation(memory_db) -> None:
    from datetime import datetime, timedelta, timezone

    from bson import ObjectId

    from app.repositories.prediction_repository import PredictionRepository

    user_id = ObjectId()
    await _seed(memory_db, user_id)

    repository = PredictionRepository(memory_db.get_database())
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await repository.aggregate_daily_counts(user_id, since)

    assert rows, "the aggregation returned no buckets"
    assert all({"count"} <= set(row) for row in rows)
    assert sum(row["count"] for row in rows) == 3


async def test_the_dashboard_overview_works_end_to_end(
    client, account, memory_db
) -> None:
    """The endpoint that surfaced the missing ``await`` in the first place."""
    from bson import ObjectId

    await _seed(memory_db, ObjectId(account.id))

    response = await client.get(
        "/api/v1/dashboard/overview", headers=account.headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overview"]["total_predictions"] >= 3
    assert body["top_crop_recommendations"], body
    assert {
        row["crop"] for row in body["top_crop_recommendations"]
    } == {"rice", "maize", "wheat"}


async def test_the_overview_counts_every_prediction_type(
    client, account, memory_db
) -> None:
    """Crop and yield records live in ``crop_records``; they must be counted."""
    from bson import ObjectId

    await _seed(memory_db, ObjectId(account.id))

    response = await client.get(
        "/api/v1/dashboard/overview", headers=account.headers
    )

    assert response.status_code == 200, response.text
    overview = response.json()["overview"]
    assert overview["disease_predictions"] == 3
    assert overview["crop_recommendations"] == 6
    assert overview["yield_predictions"] == 1
    assert overview["total_predictions"] == 10
    assert overview["healthy_leaves"] == 1
    assert overview["affected_leaves"] == 2
    assert overview["distinct_crops_recommended"] == 3
    assert overview["average_confidence"] is not None


async def test_the_activity_feed_includes_crop_and_yield_rows(
    client, account, memory_db
) -> None:
    from bson import ObjectId

    await _seed(memory_db, ObjectId(account.id))

    response = await client.get(
        "/api/v1/dashboard/overview", headers=account.headers
    )

    assert response.status_code == 200, response.text
    feed = response.json()["recent_predictions"]
    assert feed, "the feed must not be empty when records exist"
    assert {row["prediction_type"] for row in feed} <= {
        "disease",
        "crop_recommendation",
        "yield",
    }
    # A yield estimate has no class probability, so its confidence is null
    # rather than a fabricated number.
    yield_rows = [row for row in feed if row["prediction_type"] == "yield"]
    assert yield_rows, feed
    assert all(row["confidence"] is None for row in yield_rows), yield_rows
    # The feed is newest first.
    created = [row["created_at"] for row in feed]
    assert created == sorted(created, reverse=True)


async def test_analytics_include_crop_and_yield_records(
    client, account, memory_db
) -> None:
    from bson import ObjectId

    await _seed(memory_db, ObjectId(account.id))

    response = await client.get(
        "/api/v1/dashboard/analytics",
        params={"window_days": 7},
        headers=account.headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    breakdown = {row["type"]: row["value"] for row in body["prediction_type_breakdown"]}
    assert breakdown["disease"] == 3
    assert breakdown["crop_recommendation"] == 6
    assert breakdown["yield"] == 1
    assert body["total_records"] == 10
    assert sum(row["value"] for row in body["daily_predictions"]) == 10

    crops = {row["crop"] for row in body["crop_distribution"]}
    assert crops == {"rice", "maize", "wheat"}
    assert "sorghum" not in crops, "a yield record must not appear as a recommendation"


# ---------------------------------------------------------------------------
# Timestamp normalisation.
# ---------------------------------------------------------------------------
def test_ensure_utc_normalises_naive_and_aware_datetimes() -> None:
    """PyMongo returns naive UTC datetimes; comparisons need awareness.

    ``build_analytics`` compared a stored ``created_at`` (naive) with
    ``datetime.now(timezone.utc)`` (aware) and raised

        TypeError: can't compare offset-naive and offset-aware datetimes

    as soon as the user had a record inside the window.  The helper below is
    what every such comparison must go through.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.base import ensure_utc

    assert ensure_utc(None) is None

    naive = datetime(2026, 1, 2, 3, 4, 5)
    normalised = ensure_utc(naive)
    assert normalised is not None
    assert normalised.tzinfo is timezone.utc
    assert normalised.replace(tzinfo=None) == naive

    aware = datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    assert ensure_utc(aware) == datetime(2026, 1, 1, 21, 34, 5, tzinfo=timezone.utc)
