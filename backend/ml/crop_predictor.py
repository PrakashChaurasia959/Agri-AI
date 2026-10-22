"""Crop recommendation inference.

Wraps the trained scikit-learn pipeline and turns a prediction into a
user-facing explanation.  The explanation is derived from the model's own
feature importances and the *observed* input values - it never invents an
agronomic rationale that the model does not support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import CROP_MODEL_FILENAME
from ml.model_registry import ModelRegistry, ModelUnavailableError, registry as default_registry

logger = logging.getLogger(__name__)

# The feature order expected by the trained pipeline.
FEATURE_NAMES: tuple[str, ...] = (
    "nitrogen",
    "phosphorus",
    "potassium",
    "temperature",
    "humidity",
    "rainfall",
    "ph",
)

FEATURE_LABELS: dict[str, str] = {
    "nitrogen": "Soil nitrogen (N)",
    "phosphorus": "Soil phosphorus (P)",
    "potassium": "Soil potassium (K)",
    "temperature": "Temperature",
    "humidity": "Relative humidity",
    "rainfall": "Rainfall",
    "ph": "Soil pH",
}

# Reference ranges taken from the training dataset distribution.  They are
# used only to describe the *supplied* inputs, not to make agronomic claims.
_REFERENCE_RANGES: dict[str, tuple[float, float]] = {
    "nitrogen": (0.0, 140.0),
    "phosphorus": (5.0, 145.0),
    "potassium": (5.0, 205.0),
    "temperature": (8.0, 44.0),
    "humidity": (14.0, 100.0),
    "rainfall": (20.0, 300.0),
    "ph": (3.5, 10.0),
}

DISCLAIMER = (
    "This recommendation comes from a model trained on the Crop Recommendation "
    "Dataset, whose coverage is limited to 22 crop classes and the climatic "
    "range present in that dataset. It is a decision aid, not an agronomic "
    "decision. Confirm with a local soil test and your regional agricultural "
    "advisor before changing your cropping plan."
)


@dataclass
class CropRecommendation:
    """A single ranked crop recommendation."""

    crop: str
    score: float
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {"crop": self.crop, "score": round(self.score, 6), "rank": self.rank}


@dataclass
class CropPredictionResult:
    """The outcome of a crop recommendation request."""

    recommendations: list[CropRecommendation] = field(default_factory=list)
    model_name: str = ""
    model_version: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)
    input_summary: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER

    @property
    def top_crop(self) -> str | None:
        return self.recommendations[0].crop if self.recommendations else None

    @property
    def top_score(self) -> float | None:
        return self.recommendations[0].score if self.recommendations else None


def _describe_inputs(values: Sequence[float]) -> list[str]:
    """Describe the supplied parameters in plain language."""
    lines: list[str] = []
    for name, value in zip(FEATURE_NAMES, values):
        low, high = _REFERENCE_RANGES.get(name, (0.0, 0.0))
        label = FEATURE_LABELS.get(name, name)
        if low <= value <= high:
            position = "within"
        elif value < low:
            position = "below"
        else:
            position = "above"
        lines.append(
            f"{label}: {value:g} ({position} the range commonly seen in the "
            f"training data, {low:g}-{high:g})."
        )
    return lines


def _feature_importance_lines(pipeline: Any, top_n: int = 3) -> list[str]:
    """Describe the model's own most influential inputs."""
    estimator = getattr(pipeline, "steps", [("", pipeline)])[-1][1]
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return []
    ranked = sorted(
        zip(FEATURE_NAMES, list(importances)), key=lambda item: item[1], reverse=True
    )
    top = ranked[:top_n]
    return [
        f"{FEATURE_LABELS.get(name, name)} was the most influential input for this "
        f"model (relative importance {importance:.3f})."
        for name, importance in top
        if importance > 0
    ]


def recommend_crops(
    features: Sequence[float],
    *,
    model_registry: ModelRegistry | None = None,
    top_k: int = 5,
) -> CropPredictionResult:
    """Recommend crops for the supplied agronomic parameters.

    Raises:
        :class:`ml.model_registry.ModelUnavailableError` when the model has
            not been trained.
        ValueError when the feature vector has the wrong length.
    """
    if len(features) != len(FEATURE_NAMES):
        raise ValueError(
            f"Expected {len(FEATURE_NAMES)} features, received {len(features)}"
        )

    registry = model_registry or default_registry
    bundle = registry.load_crop_model()

    probabilities = bundle.pipeline.predict_proba([list(features)])[0]
    classes = list(bundle.pipeline.classes_)

    order = sorted(range(len(classes)), key=lambda index: probabilities[index], reverse=True)
    limit = max(1, min(top_k, len(classes)))

    recommendations = [
        CropRecommendation(
            crop=str(classes[index]),
            score=float(probabilities[index]),
            rank=rank,
        )
        for rank, index in enumerate(order[:limit], start=1)
    ]

    explanation = _describe_inputs(features)
    explanation.extend(_feature_importance_lines(bundle.pipeline))
    if recommendations:
        explanation.insert(
            0,
            f"The model ranked {recommendations[0].crop} first with a score of "
            f"{recommendations[0].score:.2f}.",
        )

    return CropPredictionResult(
        recommendations=recommendations,
        model_name=bundle.name,
        model_version=bundle.version,
        metrics=bundle.metrics,
        explanation=explanation,
        input_summary={name: value for name, value in zip(FEATURE_NAMES, features)},
        disclaimer=DISCLAIMER,
    )


__all__ = [
    "CROP_MODEL_FILENAME",
    "DISCLAIMER",
    "FEATURE_NAMES",
    "CropPredictionResult",
    "CropRecommendation",
    "recommend_crops",
]
