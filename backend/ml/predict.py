"""Disease inference entry point.

This module is the only place where a leaf image is turned into a prediction.
It performs the full pipeline:

1. validate the raw bytes (real image, sane dimensions, supported format)
2. preprocess the image exactly the way the training pipeline did
3. run the MobileNetV2 classifier
4. map the winning class onto the educational knowledge base
5. decide whether the result is *certain* enough to present as a finding

If no trained model is installed the function raises
:class:`ml.model_registry.ModelUnavailableError` - it never invents a
prediction.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ml.config import InferenceConfig
from ml.disease_knowledge import (
    GENERAL_DISCLAIMER,
    UNCERTAINTY_MESSAGE,
    DiseaseEntry,
    resolve_class,
    unknown_entry,
)
from ml.model_registry import ModelRegistry, ModelUnavailableError, registry as default_registry
from ml.preprocessing import PreprocessConfig, preprocess_image, validate_image_bytes

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """The outcome of a single inference run."""

    predicted_class: str
    display_name: str
    confidence: float
    is_healthy: bool
    is_certain: bool
    uncertainty_message: str | None
    model_name: str
    model_version: str
    inference_ms: float
    top_predictions: list[dict[str, Any]] = field(default_factory=list)
    disease_info: dict[str, Any] = field(default_factory=dict)
    image_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicted_class": self.predicted_class,
            "display_name": self.display_name,
            "confidence": round(self.confidence, 6),
            "confidence_percent": round(self.confidence * 100, 2),
            "is_healthy": self.is_healthy,
            "is_certain": self.is_certain,
            "uncertainty_message": self.uncertainty_message,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "inference_ms": round(self.inference_ms, 2),
            "top_predictions": self.top_predictions,
            "disease_info": self.disease_info,
            "image": self.image_info,
        }


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Numerically stable softmax over the last axis."""
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials, axis=-1, keepdims=True)


def _to_probabilities(raw_output: np.ndarray) -> np.ndarray:
    """Turn a model output row into a probability vector.

    The classifier ends in a ``softmax`` layer, so its output is *already* a
    probability distribution.  Applying softmax a second time over those
    probabilities destroys the result - a 0.96 becomes a 0.06 - so the
    conversion is conditional: a valid distribution is passed through, and only
    raw logits are converted.  This keeps the function correct for a model
    whose head ends in a linear layer, which is what a future re-export may do.
    """
    raw = np.asarray(raw_output, dtype=np.float64)
    if raw.ndim == 1:
        raw = raw[np.newaxis, :]
    if raw.ndim != 2 or raw.shape[0] != 1 or raw.shape[1] == 0:
        raise ModelUnavailableError(
            "The disease model returned an output of an unexpected shape. "
            "Re-run the training pipeline.",
            "model_incomplete",
        )

    row = raw[0]
    is_distribution = (
        bool(np.all(row >= 0.0))
        and bool(np.all(row <= 1.0))
        and abs(float(row.sum()) - 1.0) <= 1e-3
    )
    return row if is_distribution else _softmax(raw)[0]


def predict_disease(
    image_bytes: bytes,
    *,
    model_registry: ModelRegistry | None = None,
    confidence_threshold: float | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    min_dimension: int = 32,
    max_dimension: int = 8000,
    allowed_mime_types: list[str] | None = None,
) -> InferenceResult:
    """Run disease inference on raw image bytes.

    The image is validated *before* the model is loaded.  That ordering
    matters for the user experience: an unsupported file format is a
    problem with the upload, not with the server, so the API must report it
    as a ``400`` even on a deployment where the classifier is not installed.

    Raises:
        :class:`ml.preprocessing.ImageValidationError` when the payload is not
            a usable image.
        :class:`ml.model_registry.ModelUnavailableError` when no trained model
            is installed.
    """

    registry = model_registry or default_registry

    image_info = validate_image_bytes(
        image_bytes,
        max_bytes=max_bytes,
        min_dimension=min_dimension,
        max_dimension=max_dimension,
        allowed_mime_types=allowed_mime_types,
    )

    bundle = registry.load_disease_model()

    inference_config = InferenceConfig(
        image_size=bundle.input_size,
        confidence_threshold=(
            confidence_threshold
            if confidence_threshold is not None
            else InferenceConfig.confidence_threshold
        ),
    )

    preprocessed = preprocess_image(
        image_bytes,
        PreprocessConfig(
            image_size=inference_config.image_size,
            rescale_factor=inference_config.rescale_factor,
            mean=inference_config.mean,
            std=inference_config.std,
            interpolation=inference_config.interpolation,
        ),
    )

    started = time.perf_counter()
    raw_output = bundle.model.predict(preprocessed, verbose=0)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    probabilities = _to_probabilities(raw_output)
    labels = bundle.labels
    if not labels:
        raise ModelUnavailableError(
            "The disease model has no class labels recorded. Re-run the training pipeline.",
            "model_incomplete",
        )
    if len(labels) != len(probabilities):
        raise ModelUnavailableError(
            "The disease model output does not match the recorded class mapping. "
            "Re-run the training pipeline.",
            "model_incomplete",
        )

    order = np.argsort(probabilities)[::-1]
    top_predictions = [
        {
            "label": labels[int(index)],
            "probability": float(probabilities[int(index)]),
        }
        for index in order[: inference_config.top_k]
    ]

    best_index = int(order[0])
    best_label = labels[best_index]
    best_confidence = float(probabilities[best_index])

    entry: DiseaseEntry | None = resolve_class(best_label)
    is_certain = best_confidence >= inference_config.confidence_threshold

    if entry is None:
        # The model produced a class we have no information for - be explicit.
        display_name = best_label.replace("_", " ")
        disease_info = unknown_entry()
        is_healthy = False
        uncertainty = (
            "The model returned a class that is not part of the documented "
            "disease reference set, so no guidance can be given. Please "
            "consult a qualified agricultural extension officer."
        )
    else:
        display_name = entry.display_name
        disease_info = entry.to_dict()
        is_healthy = entry.is_healthy
        uncertainty = None if is_certain else UNCERTAINTY_MESSAGE

    return InferenceResult(
        predicted_class=best_label,
        display_name=display_name,
        confidence=best_confidence,
        is_healthy=is_healthy,
        is_certain=is_certain,
        uncertainty_message=uncertainty,
        model_name=bundle.name,
        model_version=bundle.version,
        inference_ms=elapsed_ms,
        top_predictions=top_predictions,
        disease_info=disease_info,
        image_info=image_info.to_dict(),
    )


__all__ = [
    "GENERAL_DISCLAIMER",
    "InferenceResult",
    "ModelUnavailableError",
    "predict_disease",
]
