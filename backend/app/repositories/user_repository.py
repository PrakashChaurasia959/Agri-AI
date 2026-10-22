"""User repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING

from app.database.connection import COLLECTION_USERS
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Data access for the ``users`` collection."""

    collection_name = COLLECTION_USERS

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def get_by_id(self, user_id: ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": user_id})

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email.lower()})

    async def email_exists(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def update(self, user_id: ObjectId, update: dict[str, Any]) -> dict[str, Any] | None:
        await self.collection.update_one({"_id": user_id}, {"$set": update})
        return await self.get_by_id(user_id)

    async def update_password(self, user_id: ObjectId, password_hash: str) -> bool:
        result = await self.collection.update_one(
            {"_id": user_id}, {"$set": {"password_hash": password_hash}}
        )
        return bool(result.matched_count)

    async def update_last_login(self, user_id: ObjectId, when: datetime) -> None:
        await self.collection.update_one({"_id": user_id}, {"$set": {"last_login_at": when}})

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        role: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if search:
            safe = self.escape_regex(search)
            if safe:
                query["$or"] = [
                    {"name": {"$regex": safe, "$options": "i"}},
                    {"email": {"$regex": safe, "$options": "i"}},
                ]
        if role:
            query["role"] = role

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        documents = [doc async for doc in cursor]
        return documents, total

    async def count_all(self) -> int:
        return await self.collection.count_documents({})

    async def count_by_role(self, role: str) -> int:
        return await self.collection.count_documents({"role": role})

    async def count_created_since(self, since: datetime) -> int:
        return await self.collection.count_documents({"created_at": {"$gte": since}})

    async def count_by_ids(self, user_ids: list[ObjectId]) -> int:
        if not user_ids:
            return 0
        return await self.collection.count_documents({"_id": {"$in": user_ids}})
