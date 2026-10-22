"""Document models package."""

from app.models.base import MongoBaseModel, MongoDocumentModel, new_object_id, utc_now
from app.models.crop_record import CropRecordDocument
from app.models.prediction import PredictionDocument, PredictionType
from app.models.reports import AuditEventDocument, SavedReportDocument
from app.models.user import UserDocument, UserRole

__all__ = [
    "AuditEventDocument",
    "CropRecordDocument",
    "MongoBaseModel",
    "MongoDocumentModel",
    "PredictionDocument",
    "PredictionType",
    "SavedReportDocument",
    "UserDocument",
    "UserRole",
    "new_object_id",
    "utc_now",
]
