"""Crop recommendation and yield estimation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CropRecommendationRequest(BaseModel):
    """Soil and climate inputs for the crop recommendation model."""

    nitrogen: float = Field(..., ge=0, le=300, description="Soil nitrogen (N) in mg/kg")
    phosphorus: float = Field(..., ge=0, le=300, description="Soil phosphorus (P) in mg/kg")
    potassium: float = Field(..., ge=0, le=300, description="Soil potassium (K) in mg/kg")
    temperature: float = Field(..., ge=0, le=60, description="Mean temperature in degrees Celsius")
    humidity: float = Field(..., ge=0, le=100, description="Relative humidity in percent")
    rainfall: float = Field(..., ge=0, le=500, description="Seasonal rainfall in mm")
    ph: float = Field(..., ge=0, le=14, description="Soil pH value")
    soil_type: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)

    @property
    def feature_vector(self) -> list[float]:
        """Ordered feature vector expected by the trained pipeline."""
        return [
            self.nitrogen,
            self.phosphorus,
            self.potassium,
            self.temperature,
            self.humidity,
            self.rainfall,
            self.ph,
        ]


class CropRecommendationItem(BaseModel):
    """One recommended crop with its model score."""

    crop: str
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)


class CropRecommendationResponse(BaseModel):
    """Result of ``POST /api/v1/crops/recommend``."""

    record_id: str | None = None
    recommendations: list[CropRecommendationItem]
    top_crop: str | None = None
    top_score: float | None = None
    input_summary: dict = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)
    model_name: str
    model_version: str
    metrics: dict = Field(default_factory=dict)
    disclaimer: str
    created_at: datetime | None = None


class CropRecordListItem(BaseModel):
    """A row in the crop recommendation history."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    crop_type: str
    soil_parameters: dict = Field(default_factory=dict)
    environmental_parameters: dict = Field(default_factory=dict)
    prediction_summary: dict = Field(default_factory=dict)
    created_at: datetime


class YieldPredictionRequest(BaseModel):
    """Inputs for the yield regression model."""

    crop_type: str = Field(..., min_length=2, max_length=60)
    nitrogen: float = Field(..., ge=0, le=300)
    phosphorus: float = Field(..., ge=0, le=300)
    potassium: float = Field(..., ge=0, le=300)
    temperature: float = Field(..., ge=0, le=60)
    humidity: float = Field(..., ge=0, le=100)
    rainfall: float = Field(..., ge=0, le=500)
    ph: float = Field(..., ge=0, le=14)
    area_ha: float = Field(default=1.0, gt=0, le=100_000, description="Area in hectares")
    soil_type: str | None = Field(default=None, max_length=40)
    irrigation: str | None = Field(
        default=None, max_length=40, description="Irrigation regime label"
    )
    season: str | None = Field(default=None, max_length=40)

    @property
    def feature_vector(self) -> list[float]:
        """The seven agronomic features expected by the trained pipeline.

        ``area_ha`` is deliberately *not* part of the vector: the dataset
        records yield per hectare, so the area is applied to the model's
        output rather than fed in as an input.
        """
        return [
            self.nitrogen,
            self.phosphorus,
            self.potassium,
            self.temperature,
            self.humidity,
            self.rainfall,
            self.ph,
        ]


class YieldPredictionResponse(BaseModel):
    """Result of ``POST /api/v1/yield/predict``."""

    record_id: str | None = None
    crop_type: str
    estimated_yield: float | None = None
    yield_unit: str
    per_hectare_yield: float | None = None
    confidence_interval: tuple[float, float] | None = None
    model_name: str
    model_version: str
    metrics: dict = Field(default_factory=dict)
    input_summary: dict = Field(default_factory=dict)
    disclaimer: str
    available: bool = True
    created_at: datetime | None = None
