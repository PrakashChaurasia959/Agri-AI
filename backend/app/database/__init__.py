"""Database package exports."""

from app.database.connection import (
    ALL_COLLECTIONS,
    COLLECTION_AUDIT_EVENTS,
    COLLECTION_CROP_RECORDS,
    COLLECTION_PREDICTIONS,
    COLLECTION_SAVED_REPORTS,
    COLLECTION_USERS,
    DatabaseManager,
    db_manager,
)

__all__ = [
    "ALL_COLLECTIONS",
    "COLLECTION_AUDIT_EVENTS",
    "COLLECTION_CROP_RECORDS",
    "COLLECTION_PREDICTIONS",
    "COLLECTION_SAVED_REPORTS",
    "COLLECTION_USERS",
    "DatabaseManager",
    "db_manager",
]
