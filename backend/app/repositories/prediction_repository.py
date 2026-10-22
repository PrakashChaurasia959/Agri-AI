"""Prediction repository (disease detection, crop recommendation, yield)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.database.connection import COLLECTION_PREDICTIONS
from app.repositories.base import BaseRepository


class PredictionRepository(BaseRepository):
    """Data access for the ``predictions`` collection.

    Every read that can reach a user scoped record goes through
    :meth:`get_for_user` / :meth:`list_for_user` which always include the
    ``user_id`` in the filter.  This makes ownership enforcement a property
    of the repository rather than of each endpoint.
    """

    collection_name = COLLECTION_PREDICTIONS

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def get_by_id(self, prediction_id: ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": prediction_id})

    async def get_for_user(
        self, prediction_id: ObjectId, user_id: ObjectId
    ) -> dict[str, Any] | None:
        """Fetch a prediction only if it belongs to ``user_id``."""
        return await self.collection.find_one({"_id": prediction_id, "user_id": user_id})

    async def delete_for_user(self, prediction_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": prediction_id, "user_id": user_id})
        return bool(result.deleted_count)

    async def list_for_user(
        self,
        user_id: ObjectId,
        *,
        skip: int = 0,
        limit: int = 20,
        prediction_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if prediction_type:
            query["prediction_type"] = prediction_type
        if search:
            safe = self.escape_regex(search)
            if safe:
                query["predicted_class"] = {"$regex": safe, "$options": "i"}

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        documents = [doc async for doc in cursor]
        return documents, total

    async def count_for_user(
        self, user_id: ObjectId, prediction_type: str | None = None
    ) -> int:
        query: dict[str, Any] = {"user_id": user_id}
        if prediction_type:
            query["prediction_type"] = prediction_type
        return await self.collection.count_documents(query)

    async def all_for_user(self, user_id: ObjectId) -> list[dict[str, Any]]:
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", ASCENDING)
        return [doc async for doc in cursor]

    async def recent_for_user(
        self, user_id: ObjectId, limit: int = 10
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def count_all(self, prediction_type: str | None = None) -> int:
        query: dict[str, Any] = {}
        if prediction_type:
            query["prediction_type"] = prediction_type
        return await self.collection.count_documents(query)

    async def count_since(self, since: datetime) -> int:
        return await self.collection.count_documents({"created_at": {"$gte": since}})

    async def distinct_classes(self, user_id: ObjectId | None = None) -> list[str]:
        query: dict[str, Any] = {} if user_id is None else {"user_id": user_id}
        return await self.collection.distinct("predicted_class", query)

    async def aggregate_type_breakdown(self) -> list[dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$prediction_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        # ``AsyncCollection.aggregate`` is a coroutine: it must be awaited
        # before the resulting async cursor can be iterated.
        cursor = await self.collection.aggregate(pipeline)
        return [doc async for doc in cursor]

    async def aggregate_daily_counts(
        self, user_id: ObjectId, since: datetime
    ) -> list[dict[str, Any]]:
        """Daily prediction counts for the given user since ``since``."""
        pipeline = [
            {"$match": {"user_id": user_id, "created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        cursor = await self.collection.aggregate(pipeline)
        return [doc async for doc in cursor]
