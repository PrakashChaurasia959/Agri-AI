"""Crop record, saved report and audit event repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING

from app.database.connection import (
    COLLECTION_AUDIT_EVENTS,
    COLLECTION_CROP_RECORDS,
    COLLECTION_SAVED_REPORTS,
)
from app.models.prediction import PredictionType
from app.repositories.base import BaseRepository


class CropRecordRepository(BaseRepository):
    """Data access for the ``crop_records`` collection."""

    collection_name = COLLECTION_CROP_RECORDS

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def list_for_user(
        self, user_id: ObjectId, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        query = {"user_id": user_id}
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        documents = [doc async for doc in cursor]
        return documents, total

    async def get_for_user(self, record_id: ObjectId, user_id: ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": record_id, "user_id": user_id})

    async def delete_for_user(self, record_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": record_id, "user_id": user_id})
        return bool(result.deleted_count)

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    async def count_all(self) -> int:
        return await self.collection.count_documents({})

    async def count_kind(self, kind: str) -> int:
        """Count crop recommendations or yield estimates, across all users."""
        if kind == PredictionType.YIELD.value:
            query: dict[str, Any] = {
                "prediction_summary.estimated_yield": {"$exists": True}
            }
        else:
            query = {"prediction_summary.top_crop": {"$exists": True, "$ne": None}}
        return await self.collection.count_documents(query)

    async def all_for_user(self, user_id: ObjectId) -> list[dict[str, Any]]:
        """Every crop record that belongs to the user (bounded in practice)."""
        cursor = self.collection.find({"user_id": user_id})
        return [doc async for doc in cursor]

    async def recent_for_user(
        self, user_id: ObjectId, *, limit: int = 8
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def count_since(self, since: datetime) -> int:
        return await self.collection.count_documents({"created_at": {"$gte": since}})

    async def distinct_crops(self, user_id: ObjectId) -> list[str]:
        """Distinct *recommended* crops.

        Yield records also carry a ``crop_type``; they are excluded so that the
        dashboard's "distinct crops recommended" counter means what it says.
        """
        return await self.collection.distinct(
            "crop_type",
            {
                "user_id": user_id,
                "prediction_summary.top_crop": {"$exists": True, "$ne": None},
            },
        )

    async def top_crops_for_user(self, user_id: ObjectId, limit: int = 6) -> list[dict[str, Any]]:
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    # Only genuine recommendations feed this ranking; a yield
                    # estimate names a crop but does not recommend one.
                    "prediction_summary.top_crop": {"$exists": True, "$ne": None},
                }
            },
            {"$group": {"_id": "$crop_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": limit},
        ]
        # ``AsyncCollection.aggregate`` is a coroutine returning an async
        # cursor (unlike ``find``, which returns the cursor directly).
        # Forgetting the ``await`` raises at runtime on a real cluster while
        # an emulator with a synchronous ``aggregate`` hides the defect.
        cursor = await self.collection.aggregate(pipeline)
        return [doc async for doc in cursor]


class SavedReportRepository(BaseRepository):
    """Data access for the ``saved_reports`` collection."""

    collection_name = COLLECTION_SAVED_REPORTS

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def list_for_user(
        self, user_id: ObjectId, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        query = {"user_id": user_id}
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        documents = [doc async for doc in cursor]
        return documents, total

    async def get_for_user(self, report_id: ObjectId, user_id: ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": report_id, "user_id": user_id})

    async def delete_for_user(self, report_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": report_id, "user_id": user_id})
        return bool(result.deleted_count)

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    async def count_all(self) -> int:
        return await self.collection.count_documents({})


class AuditEventRepository(BaseRepository):
    """Data access for the ``audit_events`` collection."""

    collection_name = COLLECTION_AUDIT_EVENTS

    async def record(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def list_recent(
        self, *, skip: int = 0, limit: int = 50, action: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if action:
            query["action"] = action
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        documents = [doc async for doc in cursor]
        return documents, total
