"""Crop yield estimation inference.

A separate regression task from crop recommendation: the target is a
continuous value (tonnes per hectare) instead of a crop class.

The dataset used here (``crop_yield.csv``) contains the columns
``N, P, K, temperature, humidity, ph, rainfall, label, yield, fertilizer``.
``yield`` is expressed in tonnes per hectare in the upstream dataset, and the
trained model reproduces that unit - the API labels the output explicitly so
the number is never ambiguous.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.model_registry import ModelRegistry, registry as default_registry

logger = logging.getLogger(__name__)

# The trained pipeline consumes the seven agronomic features.  ``area_ha``
# scales the final result and is handled explicitly rather than being fed to
# the model, because the dataset records yield per hectare.
FEATURE_NAMES: tuple[str, ...] = (
    "nitrogen",
    "phosphorus",
    "potassium",
    "temperature",
    "humidity",
    "rainfall",
    "ph",
)

YIELD_UNIT = "tonnes per hectare"

DISCLAIMER = (
    "This estimate comes from a model trained on the Crop Yield Prediction "
    "Dataset, which covers a limited set of crops, climates and management "
    "regimes. Treat the number as an order-of-magnitude planning aid and "
    "verify it against your own field records and local agronomic advice."
)


@dataclass
class YieldPrediction:
    """The outcome of a yield estimation request."""

    crop_type: str
    estimated_yield: float | None
    yield_unit: str = YIELD_UNIT
    per_hectare_yield: float | None = None
    total_yield: float | None = None
    confidence_interval: tuple[float, float] | None = None
    model_name: str = ""
    model_version: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    input_summary: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "crop_type": self.crop_type,
            "estimated_yield": (
                round(self.estimated_yield, 4) if self.estimated_yield is not None else None
            ),
            "yield_unit": self.yield_unit,
            "per_hectare_yield": (
                round(self.per_hectare_yield, 4)
                if self.per_hectare_yield is not None
                else None
            ),
            "total_yield": (
                round(self.total_yield, 4) if self.total_yield is not None else None
            ),
            "confidence_interval": (
                list(self.confidence_interval) if self.confidence_interval else None
            ),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "metrics": self.metrics,
            "input_summary": self.input_summary,
            "disclaimer": self.disclaimer,
            "available": self.available,
        }


def estimate_yield(
    features: Sequence[float],
    *,
    crop_type: str,
    area_ha: float = 1.0,
    model_registry: ModelRegistry | None = None,
) -> YieldPrediction:
    """Estimate the yield for the supplied agronomic parameters.

    Raises:
        :class:`ml.model_registry.ModelUnavailableError` when the model has
            not been trained.
    """
    if len(features) != len(FEATURE_NAMES):
        raise ValueError(
            f"Expected {len(FEATURE_NAMES)} features, received {len(features)}"
        )
    if area_ha <= 0:
        raise ValueError("area_ha must be greater than zero")

    registry = model_registry or default_registry
    bundle = registry.load_yield_model()

    predicted = bundle.pipeline.predict([list(features)])[0]
    per_hectare = float(predicted)

    metrics = bundle.metrics
    mae = metrics.get("mae")
    half_width: float | None = None
    if isinstance(mae, (int, float)):
        # A simple, honest interval: the mean absolute error of the model on
        # the held-out test split, used as a symmetric band.
        half_width = float(mae)

    lower = max(0.0, per_hectare - half_width) if half_width is not None else None
    upper = per_hectare + half_width if half_width is not None else None

    return YieldPrediction(
        crop_type=crop_type,
        estimated_yield=round(per_hectare * area_ha, 4),
        yield_unit=YIELD_UNIT,
        per_hectare_yield=round(per_hectare, 4),
        total_yield=round(per_hectare * area_ha, 4),
        confidence_interval=(lower, upper) if lower is not None and upper is not None else None,
        model_name=bundle.name,
        model_version=bundle.version,
        metrics=metrics,
        input_summary={
            **{name: value for name, value in zip(FEATURE_NAMES, features)},
            "area_ha": area_ha,
            "crop_type": crop_type,
        },
        disclaimer=DISCLAIMER,
    )


__all__ = [
    "DISCLAIMER",
    "FEATURE_NAMES",
    "YIELD_UNIT",
    "YieldPrediction",
    "estimate_yield",
]
