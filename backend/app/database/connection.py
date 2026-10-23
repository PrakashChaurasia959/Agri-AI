"""MongoDB connection management.

The application uses PyMongo's async driver (``AsyncMongoClient``).  A single
client is created during the FastAPI lifespan and reused for the whole
process - creating a client per request is an anti-pattern that exhausts
sockets.

If no ``MONGODB_URI`` is configured, the API still boots and serves the
health / models endpoints, but every data route returns a clear
``503 database_unavailable`` error rather than pretending to work.
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Collections used across the application.
COLLECTION_USERS = "users"
COLLECTION_PREDICTIONS = "predictions"
COLLECTION_CROP_RECORDS = "crop_records"
COLLECTION_SAVED_REPORTS = "saved_reports"
COLLECTION_AUDIT_EVENTS = "audit_events"

ALL_COLLECTIONS = (
    COLLECTION_USERS,
    COLLECTION_PREDICTIONS,
    COLLECTION_CROP_RECORDS,
    COLLECTION_SAVED_REPORTS,
    COLLECTION_AUDIT_EVENTS,
)


class DatabaseManager:
    """Owns the MongoDB client lifecycle."""

    def __init__(self) -> None:
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._database: AsyncDatabase[dict[str, Any]] | None = None
        self._connected = False
        self._last_error: str | None = None

    # -- lifecycle -------------------------------------------------------
    async def connect(self) -> bool:
        """Open the connection and verify it with a ping.

        Returns ``True`` when the database is reachable.  Failures are logged
        (without the URI) and swallowed so the API can still boot and report
        an honest health status.
        """
        settings = get_settings()
        if not settings.mongodb_uri:
            self._last_error = "MONGODB_URI is not configured"
            logger.warning("MongoDB URI is not configured - running without a database")
            self._connected = False
            return False

        try:
            self._client = AsyncMongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
                connectTimeoutMS=settings.mongodb_timeout_ms,
                maxPoolSize=settings.mongodb_max_pool_size,
                retryWrites=True,
                tz_aware=True,
                appname="agrivision-ai",
            )
            # Force a server selection so failures surface immediately.
            await self._client.admin.command("ping")
            self._database = self._client[settings.mongodb_db_name]
            await self.ensure_indexes(self._database)
            self._connected = True
            self._last_error = None
            logger.info(
                "Connected to MongoDB database '%s'", settings.mongodb_db_name
            )
            return True
        except PyMongoError as exc:
            err_type = type(exc).__name__
            category = self._classify_error(exc)
            # Store the human-readable category (never the URI) so the health
            # endpoint and 503 responses explain *why* the database is down.
            self._last_error = category
            # Log safe diagnostics without exposing secrets
            msg = str(exc)
            # Avoid leaking connection strings in logs
            if "mongodb://" in msg.lower() or "mongodb+srv://" in msg.lower():
                msg = err_type
            logger.error(
                "Failed to connect to MongoDB: %s (%s) - %s", err_type, category, msg
            )
            self._connected = False
            self._database = None
            if self._client is not None:
                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None
            return False

    @staticmethod
    def _classify_error(exc: PyMongoError) -> str:
        """Return a safe, human-readable failure category.

        Never includes the URI or credentials.
        """
        name = type(exc).__name__
        text = str(exc).lower()

        # TLS problems surface inside ServerSelectionTimeoutError, so they must
        # be checked before the generic server-selection branch.
        if "tlsv1_alert" in text or "ssl handshake failed" in text or "certificate" in text:
            return (
                "TLS handshake rejected (check the Atlas IP access list, "
                "cluster paused state, or a proxy/NAT64/VPN interfering with TLS)"
            )
        if "authentication" in text or "auth failed" in text:
            return "Authentication failure (check the database user credentials)"
        if "name or service not known" in text or "nodename" in text or "dns" in text:
            return "DNS/cluster hostname resolution failure"
        if "timed out" in text or "timeout" in text:
            return "Network timeout or blocked outbound connection"
        if name == "ServerSelectionTimeoutError":
            return "Server selection failed (Atlas IP access list / cluster availability)"
        if "ConfigurationError" in name:
            return "Invalid MongoDB URI or configuration"
        return "Unknown connection error"

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("MongoDB connection closed")
            except PyMongoError:  # pragma: no cover - defensive
                logger.warning("Error while closing the MongoDB connection")
        self._client = None
        self._database = None
        self._connected = False

    # -- accessors -------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._connected and self._database is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def get_database(self) -> AsyncDatabase[dict[str, Any]]:
        """Return the active database handle.

        Raises :class:`RuntimeError` when the database is not available so
        that callers surface a 503 instead of a 500.
        """
        if not self.is_connected or self._database is None:
            raise RuntimeError(self._last_error or "Database is not connected")
        return self._database

    def get_collection(self, name: str) -> Any:
        if not self.is_connected or self._database is None:
            raise RuntimeError(self._last_error or "Database is not connected")
        return self._database[name]

    # -- index management ------------------------------------------------
    @staticmethod
    async def ensure_indexes(database: AsyncDatabase[dict[str, Any]]) -> None:
        """Create the indexes the application relies on.

        Index creation is idempotent, so this runs safely on every boot.
        """
        await database[COLLECTION_USERS].create_index("email", unique=True, name="uq_users_email")
        await database[COLLECTION_USERS].create_index("role", name="ix_users_role")
        await database[COLLECTION_USERS].create_index("created_at", name="ix_users_created_at")

        await database[COLLECTION_PREDICTIONS].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_predictions_user_created"
        )
        await database[COLLECTION_PREDICTIONS].create_index(
            [("prediction_type", 1), ("created_at", -1)], name="ix_predictions_type_created"
        )
        await database[COLLECTION_PREDICTIONS].create_index(
            "created_at", name="ix_predictions_created_at"
        )

        await database[COLLECTION_CROP_RECORDS].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_crop_records_user_created"
        )
        await database[COLLECTION_CROP_RECORDS].create_index(
            "crop_type", name="ix_crop_records_crop_type"
        )

        await database[COLLECTION_SAVED_REPORTS].create_index(
            [("user_id", 1), ("created_at", -1)], name="ix_reports_user_created"
        )
        await database[COLLECTION_SAVED_REPORTS].create_index(
            "report_type", name="ix_reports_type"
        )

        await database[COLLECTION_AUDIT_EVENTS].create_index(
            [("actor_id", 1), ("created_at", -1)], name="ix_audit_actor_created"
        )
        await database[COLLECTION_AUDIT_EVENTS].create_index(
            "action", name="ix_audit_action"
        )


db_manager = DatabaseManager()
