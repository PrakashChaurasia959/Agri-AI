"""Disease detection schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.prediction import PredictionType


class DiseaseInfo(BaseModel):
    """Educational information attached to a recognised disease class."""

    crop: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    prevention: list[str] = Field(default_factory=list)
    treatment: list[str] = Field(default_factory=list)
    severity: str | None = None
    disclaimer: str | None = None


class TopPrediction(BaseModel):
    """A single class from the model's probability distribution."""

    label: str
    probability: float = Field(ge=0.0, le=1.0)


class DiseasePredictionResponse(BaseModel):
    """Result of ``POST /api/v1/disease/predict``."""

    prediction_id: str | None = None
    predicted_class: str
    display_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_percent: float = Field(ge=0.0, le=100.0)
    is_healthy: bool
    is_certain: bool
    uncertainty_message: str | None = None
    model_name: str
    model_version: str
    inference_ms: float = Field(ge=0.0)
    top_predictions: list[TopPrediction] = Field(default_factory=list)
    disease_info: DiseaseInfo | None = None
    image: dict[str, str | int | float | None] = Field(default_factory=dict)
    saved: bool = False
    created_at: datetime | None = None


class PredictionListItem(BaseModel):
    """A single row in the prediction history list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    prediction_type: PredictionType
    predicted_class: str
    # ``None`` for a yield estimate: a regressor returns a number, not a class
    # probability, so there is no honest confidence to report.
    confidence: float | None = None
    model_name: str
    model_version: str
    created_at: datetime
    input_summary: dict = Field(default_factory=dict)


class PredictionDetail(PredictionListItem):
    """Full detail of one stored prediction."""

    details: dict = Field(default_factory=dict)
    image_metadata: dict = Field(default_factory=dict)


class ModelStatus(BaseModel):
    """Availability information for one ML model."""

    key: str
    display_name: str
    task: str
    available: bool
    model_name: str | None = None
    model_version: str | None = None
    accuracy: float | None = None
    metrics: dict = Field(default_factory=dict)
    classes_count: int | None = None
    trained_at: str | None = None
    dataset: str | None = None
    message: str | None = None
    artifact_path: str | None = None
