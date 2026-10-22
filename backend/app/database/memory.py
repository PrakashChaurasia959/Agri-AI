"""In-memory MongoDB emulator used by the automated test-suite.

The project targets MongoDB Atlas, but the test-suite must run on a machine
with no MongoDB server available.  ``mongomock`` implements the MongoDB
query, update and aggregation semantics in pure Python, so wrapping it behind
the same async surface as :class:`pymongo.asynchronous.collection.AsyncCollection`
lets the repositories - and therefore the endpoint tests - exercise the real
production code paths.

This emulator is **only** used when ``AGRIVISION_TEST_MEMORY_DB`` is enabled
or when the test-suite explicitly asks for it.  It is never used in production.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import mongomock

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AsyncCursor:
    """Async iterator over a mongomock cursor.

    The chaining helpers (``sort`` / ``skip`` / ``limit``) mirror the PyMongo
    cursor API used by the repositories.
    """

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def __aiter__(self) -> "AsyncCursor":
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._cursor)
        except StopIteration as exc:  # pragma: no cover - normal loop end
            raise StopAsyncIteration from exc

    def sort(self, key_or_list: Any, direction: Any = None) -> "AsyncCursor":
        self._cursor = self._cursor.sort(key_or_list, direction)
        return self

    def skip(self, count: int) -> "AsyncCursor":
        self._cursor = self._cursor.skip(count)
        return self

    def limit(self, count: int) -> "AsyncCursor":
        self._cursor = self._cursor.limit(count)
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        docs = list(self._cursor)
        if length is not None:
            docs = docs[:length]
        return docs


class AsyncCollection:
    """Async facade over a mongomock collection."""

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    # -- reads -----------------------------------------------------------
    async def find_one(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        return self._collection.find_one(filter or {}, *args, **kwargs)

    def find(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> AsyncCursor:
        return AsyncCursor(self._collection.find(filter or {}, *args, **kwargs))

    async def find_one_and_update(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return self._collection.find_one_and_update(filter, update, *args, **kwargs)

    async def count_documents(self, filter: dict[str, Any] | None = None, **kwargs: Any) -> int:
        return int(self._collection.count_documents(filter or {}, **kwargs))

    async def distinct(self, key: str, filter: dict[str, Any] | None = None) -> list[Any]:
        return list(self._collection.distinct(key, filter or {}))

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> AsyncCursor:
        """Return an async cursor, matching the real async driver.

        ``AsyncCollection.aggregate`` is a **coroutine** in PyMongo's async
        driver (unlike ``find``, which is synchronous and returns the cursor
        directly).  This facade deliberately mirrors that contract: if it
        were synchronous, a repository that forgot the ``await`` would pass
        every test and fail only against a real cluster.
        """
        return AsyncCursor(self._collection.aggregate(pipeline))

    # -- writes ----------------------------------------------------------
    async def insert_one(self, document: dict[str, Any]) -> Any:
        return self._collection.insert_one(document)

    async def insert_many(self, documents: list[dict[str, Any]]) -> Any:
        return self._collection.insert_many(documents)

    async def update_one(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return self._collection.update_one(filter, update, *args, **kwargs)

    async def update_many(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return self._collection.update_many(filter, update, *args, **kwargs)

    async def delete_one(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        return self._collection.delete_one(filter, *args, **kwargs)

    async def delete_many(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        return self._collection.delete_many(filter, *args, **kwargs)

    async def create_index(self, keys: Any, **kwargs: Any) -> Any:
        return self._collection.create_index(keys, **kwargs)

    async def drop(self, *args: Any, **kwargs: Any) -> Any:
        return self._collection.drop(*args, **kwargs)

    async def index_information(self) -> dict[str, Any]:
        return dict(self._collection.index_information())


class AsyncMemoryDatabase:
    """Async facade over a mongomock database."""

    def __init__(self, database: Any) -> None:
        self._database = database

    def __getitem__(self, name: str) -> AsyncCollection:
        return AsyncCollection(self._database[name])

    def get_collection(self, name: str) -> AsyncCollection:
        return AsyncCollection(self._database[name])

    async def list_collection_names(self) -> list[str]:
        return list(self._database.list_collection_names())

    async def command(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ok": 1.0}

    async def drop_collection(self, name: str) -> None:
        self._database.drop_collection(name)


class MemoryDatabaseManager:
    """Drop-in replacement for :class:`app.database.connection.DatabaseManager`.

    It exposes exactly the same public API so the repositories do not need to
    know which backing store they are talking to.
    """

    def __init__(self) -> None:
        self._client: mongomock.MongoClient | None = None
        self._database: AsyncMemoryDatabase | None = None
        self._connected = False
        self._last_error: str | None = None

    async def connect(self) -> bool:
        self._client = mongomock.MongoClient()
        self._database = AsyncMemoryDatabase(self._client["agrivision_ai_test"])
        self._connected = True
        self._last_error = None
        logger.info("Connected to the in-memory MongoDB emulator")
        return True

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._database = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._database is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def get_database(self) -> AsyncMemoryDatabase:
        if not self.is_connected or self._database is None:
            raise RuntimeError(self._last_error or "Database is not connected")
        return self._database

    def get_collection(self, name: str) -> AsyncCollection:
        if not self.is_connected or self._database is None:
            raise RuntimeError(self._last_error or "Database is not connected")
        return self._database[name]

    @staticmethod
    async def ensure_indexes(database: AsyncMemoryDatabase) -> None:
        await database["users"].create_index("email", unique=True, name="uq_users_email")
        await database["users"].create_index("role", name="ix_users_role")
        await database["users"].create_index("created_at", name="ix_users_created_at")
        await database["predictions"].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_predictions_user_created"
        )
        await database["predictions"].create_index(
            [("prediction_type", 1), ("created_at", -1)], name="ix_predictions_type_created"
        )
        await database["predictions"].create_index(
            "created_at", name="ix_predictions_created_at"
        )
        await database["crop_records"].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_crop_records_user_created"
        )
        await database["crop_records"].create_index(
            "crop_type", name="ix_crop_records_crop_type"
        )
        await database["saved_reports"].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_reports_user_created"
        )
        await database["saved_reports"].create_index("report_type", name="ix_reports_type")
        await database["audit_events"].create_index(
            [("actor_id", 1), ("created_at", -1)], name="ix_audit_actor_created"
        )
        await database["audit_events"].create_index("action", name="ix_audit_action")


async def iter_documents(cursor: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    """Materialise an async cursor into a list."""
    return [document async for document in cursor]
