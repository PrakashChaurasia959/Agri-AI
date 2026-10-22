"""Classify documents in the ``crop_records`` collection.

The collection stores **two** kinds of record:

* a crop recommendation, whose ``prediction_summary`` carries ``top_crop``
  and ``top_score``;
* a yield estimate, whose ``prediction_summary`` carries ``estimated_yield``
  and ``per_hectare_yield``.

Both are written by :mod:`app.services.agriculture_service`, and both appear in
``GET /api/v1/crops/history``.  The dashboard and the admin panel have to count
and display them as two distinct prediction types, so the classification lives
here rather than being duplicated in each caller.
"""

from __future__ import annotations

from typing import Any

from app.models.prediction import PredictionType


def crop_record_kind(document: dict[str, Any]) -> str:
    """Return the prediction type of a ``crop_records`` document.

    A yield document is identified by the presence of ``estimated_yield`` in
    its summary; everything else is a crop recommendation.
    """
    summary = document.get("prediction_summary") or {}
    if "estimated_yield" in summary:
        return PredictionType.YIELD.value
    return PredictionType.CROP_RECOMMENDATION.value


def crop_record_confidence(document: dict[str, Any]) -> float | None:
    """The model's confidence for a crop record, when the model reports one.

    A crop recommender returns ``top_score``.  A yield regressor returns a
    point estimate and an interval, not a class probability, so there is no
    honest confidence to report - the function returns ``None`` rather than
    inventing one.
    """
    if crop_record_kind(document) == PredictionType.YIELD.value:
        return None
    value = (document.get("prediction_summary") or {}).get("top_score")
    return float(value) if isinstance(value, (int, float)) else None


def as_prediction_row(document: dict[str, Any]) -> dict[str, Any]:
    """Normalise a crop record into the shape the dashboard consumes."""
    summary = document.get("prediction_summary") or {}
    return {
        "_id": document.get("_id"),
        "prediction_type": crop_record_kind(document),
        "predicted_class": str(document.get("crop_type") or "unknown"),
        "confidence": crop_record_confidence(document),
        "created_at": document.get("created_at"),
        "details": summary,
        "document": document,
    }


__all__ = [
    "as_prediction_row",
    "crop_record_confidence",
    "crop_record_kind",
]
