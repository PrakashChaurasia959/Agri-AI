"""Saved report and audit event document models."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import Field

from app.models.base import MongoDocumentModel


class SavedReportDocument(MongoDocumentModel):
    """A row of the ``saved_reports`` collection.

    A "report" is a snapshot of an analysis result that a user explicitly
    saved from the dashboard or the history pages.
    """

    user_id: ObjectId
    report_type: str = Field(max_length=60)
    title: str = Field(default="Untitled report", max_length=200)
    report_data: dict[str, Any] = Field(default_factory=dict)


class AuditEventDocument(MongoDocumentModel):
    """A row of the ``audit_events`` collection.

    Records security relevant actions (logins, role changes, record
    deletions) so an administrator can review who did what.
    """

    actor_id: ObjectId | None = None
    actor_email: str | None = None
    action: str = Field(max_length=80)
    target_type: str | None = Field(default=None, max_length=60)
    target_id: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
