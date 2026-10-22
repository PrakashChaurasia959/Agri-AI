"""Model registry.

Central place that knows which model artifacts exist on disk, loads them
lazily (once per process) and reports their status.

The registry is deliberately the *only* place allowed to touch the model
files.  Everything else goes through the public accessors, which means a
missing or corrupt artifact produces one consistent, honest error instead of
an ``ImportError`` deep inside a request handler.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.config import (
    CROP_METADATA_FILENAME,
    CROP_MODEL_FILENAME,
    DISEASE_LABELS_FILENAME,
    DISEASE_METADATA_FILENAME,
    DISEASE_MODEL_FILENAME,
    MODEL_DIR,
    YIELD_METADATA_FILENAME,
    YIELD_MODEL_FILENAME,
)

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when a requested model has not been trained/installed."""

    def __init__(self, message: str, code: str = "model_unavailable") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class DiseaseModelBundle:
    """A loaded disease classifier plus its metadata."""

    model: Any
    labels: list[str]
    metadata: dict[str, Any]
    path: Path
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def version(self) -> str:
        return str(self.metadata.get("model_version", "unknown"))

    @property
    def name(self) -> str:
        return str(self.metadata.get("model_name", "plant_disease_cnn"))

    @property
    def accuracy(self) -> float | None:
        metrics = self.metadata.get("metrics") or {}
        value = metrics.get("accuracy")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def input_size(self) -> int:
        return int(self.metadata.get("config", {}).get("image_size", 224))


@dataclass
class SklearnModelBundle:
    """A loaded scikit-learn pipeline plus its metadata."""

    pipeline: Any
    metadata: dict[str, Any]
    path: Path
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def version(self) -> str:
        return str(self.metadata.get("model_version", "unknown"))

    @property
    def name(self) -> str:
        return str(self.metadata.get("model_name", "sklearn_pipeline"))

    @property
    def metrics(self) -> dict[str, Any]:
        return dict(self.metadata.get("metrics") or {})


class ModelRegistry:
    """Thread-safe lazy loader for the ML artifacts."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self._lock = threading.Lock()
        self._disease_bundle: DiseaseModelBundle | None = None
        self._crop_bundle: SklearnModelBundle | None = None
        self._yield_bundle: SklearnModelBundle | None = None
        self._load_errors: dict[str, str] = {}

    # -- paths -----------------------------------------------------------
    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def _path(self, filename: str) -> Path:
        return self._model_dir / filename

    # -- generic helpers -------------------------------------------------
    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {path.name}")
        return data

    def _reset(self) -> None:
        with self._lock:
            self._disease_bundle = None
            self._crop_bundle = None
            self._yield_bundle = None
            self._load_errors.clear()

    # -- disease model ---------------------------------------------------
    def is_disease_model_available(self) -> bool:
        return self._path(DISEASE_MODEL_FILENAME).is_file() and self._path(
            DISEASE_LABELS_FILENAME
        ).is_file()

    def load_disease_model(self, *, force_reload: bool = False) -> DiseaseModelBundle:
        """Load the disease classifier.

        Raises :class:`ModelUnavailableError` when the artifact has not been
        trained.  The API surfaces this as a clear, actionable message - it
        never fabricates a prediction.
        """
        with self._lock:
            if self._disease_bundle is not None and not force_reload:
                return self._disease_bundle

        model_path = self._path(DISEASE_MODEL_FILENAME)
        labels_path = self._path(DISEASE_LABELS_FILENAME)
        metadata_path = self._path(DISEASE_METADATA_FILENAME)

        if not model_path.is_file():
            raise ModelUnavailableError(
                "The crop disease model has not been trained yet. "
                "Run `python -m ml.train_cnn` (after preparing the PlantVillage "
                "dataset) to enable disease detection.",
                "model_not_trained",
            )
        if not labels_path.is_file():
            raise ModelUnavailableError(
                "The class-label mapping for the disease model is missing "
                f"({labels_path.name}). Re-run the training pipeline.",
                "model_incomplete",
            )

        try:
            import keras

            model = keras.models.load_model(model_path, compile=False)
        except Exception as exc:  # pragma: no cover - depends on artifact
            logger.error("Failed to load the disease model: %s", type(exc).__name__)
            raise ModelUnavailableError(
                "The crop disease model artifact could not be loaded. "
                "Re-run the training pipeline to regenerate it.",
                "model_load_failed",
            ) from exc

        labels = self._read_json(labels_path).get("labels", [])
        metadata = self._read_json(metadata_path) if metadata_path.is_file() else {}

        bundle = DiseaseModelBundle(
            model=model,
            labels=list(labels),
            metadata=metadata,
            path=model_path,
        )
        with self._lock:
            self._disease_bundle = bundle
        logger.info("Loaded disease model '%s' v%s", bundle.name, bundle.version)
        return bundle

    # -- crop recommendation model ---------------------------------------
    def is_crop_model_available(self) -> bool:
        return self._path(CROP_MODEL_FILENAME).is_file()

    def load_crop_model(self, *, force_reload: bool = False) -> SklearnModelBundle:
        """Load the crop recommendation pipeline."""
        with self._lock:
            if self._crop_bundle is not None and not force_reload:
                return self._crop_bundle

        model_path = self._path(CROP_MODEL_FILENAME)
        if not model_path.is_file():
            raise ModelUnavailableError(
                "The crop recommendation model has not been trained yet. "
                "Run `python -m ml.train_crop_model` to enable crop recommendations.",
                "model_not_trained",
            )

        try:
            import joblib

            pipeline = joblib.load(model_path)
        except Exception as exc:  # pragma: no cover - depends on artifact
            logger.error("Failed to load the crop model: %s", type(exc).__name__)
            raise ModelUnavailableError(
                "The crop recommendation model artifact could not be loaded. "
                "Re-run the training pipeline to regenerate it.",
                "model_load_failed",
            ) from exc

        metadata_path = self._path(CROP_METADATA_FILENAME)
        metadata = self._read_json(metadata_path) if metadata_path.is_file() else {}

        bundle = SklearnModelBundle(
            pipeline=pipeline, metadata=metadata, path=model_path
        )
        with self._lock:
            self._crop_bundle = bundle
        logger.info("Loaded crop model '%s' v%s", bundle.name, bundle.version)
        return bundle

    # -- yield model -----------------------------------------------------
    def is_yield_model_available(self) -> bool:
        return self._path(YIELD_MODEL_FILENAME).is_file()

    def load_yield_model(self, *, force_reload: bool = False) -> SklearnModelBundle:
        """Load the yield regression pipeline."""
        with self._lock:
            if self._yield_bundle is not None and not force_reload:
                return self._yield_bundle

        model_path = self._path(YIELD_MODEL_FILENAME)
        if not model_path.is_file():
            raise ModelUnavailableError(
                "The crop yield model has not been trained yet. "
                "Run `python -m ml.train_yield_model` to enable yield estimation.",
                "model_not_trained",
            )

        try:
            import joblib

            pipeline = joblib.load(model_path)
        except Exception as exc:  # pragma: no cover - depends on artifact
            logger.error("Failed to load the yield model: %s", type(exc).__name__)
            raise ModelUnavailableError(
                "The crop yield model artifact could not be loaded. "
                "Re-run the training pipeline to regenerate it.",
                "model_load_failed",
            ) from exc

        metadata_path = self._path(YIELD_METADATA_FILENAME)
        metadata = self._read_json(metadata_path) if metadata_path.is_file() else {}

        bundle = SklearnModelBundle(
            pipeline=pipeline, metadata=metadata, path=model_path
        )
        with self._lock:
            self._yield_bundle = bundle
        logger.info("Loaded yield model '%s' v%s", bundle.name, bundle.version)
        return bundle

    # -- status ----------------------------------------------------------
    def disease_status(self) -> dict[str, Any]:
        """Availability report for the disease classifier."""
        available = self.is_disease_model_available()
        payload: dict[str, Any] = {
            "key": "disease_detection",
            "display_name": "Crop Disease Detection (CNN)",
            "task": "image_classification",
            "available": available,
            "model_name": None,
            "model_version": None,
            "accuracy": None,
            "metrics": {},
            "classes_count": None,
            "trained_at": None,
            "dataset": None,
            "message": None,
            "artifact_path": str(self._path(DISEASE_MODEL_FILENAME)),
        }
        if not available:
            payload["message"] = (
                "Model not installed. Run `python -m ml.train_cnn` to train the "
                "MobileNetV2 classifier on the PlantVillage dataset."
            )
            return payload

        metadata_path = self._path(DISEASE_METADATA_FILENAME)
        metadata: dict[str, Any] = {}
        if metadata_path.is_file():
            try:
                metadata = self._read_json(metadata_path)
            except (OSError, ValueError, json.JSONDecodeError):
                metadata = {}

        payload["model_name"] = metadata.get("model_name")
        payload["model_version"] = metadata.get("model_version")
        payload["metrics"] = metadata.get("metrics", {})
        payload["trained_at"] = metadata.get("trained_at")
        payload["dataset"] = metadata.get("dataset")
        payload["message"] = "Model available."

        metrics = metadata.get("metrics") or {}
        if isinstance(metrics.get("accuracy"), (int, float)):
            payload["accuracy"] = float(metrics["accuracy"])

        labels_path = self._path(DISEASE_LABELS_FILENAME)
        if labels_path.is_file():
            try:
                labels = self._read_json(labels_path).get("labels", [])
                payload["classes_count"] = len(labels)
            except (OSError, ValueError, json.JSONDecodeError):
                payload["classes_count"] = None
        return payload

    def crop_status(self) -> dict[str, Any]:
        """Availability report for the crop recommender."""
        available = self.is_crop_model_available()
        payload: dict[str, Any] = {
            "key": "crop_recommendation",
            "display_name": "Crop Recommendation",
            "task": "tabular_classification",
            "available": available,
            "model_name": None,
            "model_version": None,
            "accuracy": None,
            "metrics": {},
            "classes_count": None,
            "trained_at": None,
            "dataset": None,
            "message": None,
            "artifact_path": str(self._path(CROP_MODEL_FILENAME)),
        }
        if not available:
            payload["message"] = (
                "Model not installed. Run `python -m ml.train_crop_model` to train "
                "the recommendation classifier."
            )
            return payload

        metadata_path = self._path(CROP_METADATA_FILENAME)
        metadata: dict[str, Any] = {}
        if metadata_path.is_file():
            try:
                metadata = self._read_json(metadata_path)
            except (OSError, ValueError, json.JSONDecodeError):
                metadata = {}

        payload["model_name"] = metadata.get("model_name")
        payload["model_version"] = metadata.get("model_version")
        payload["metrics"] = metadata.get("metrics", {})
        payload["trained_at"] = metadata.get("trained_at")
        payload["dataset"] = metadata.get("dataset")
        payload["message"] = "Model available."
        metrics = metadata.get("metrics") or {}
        if isinstance(metrics.get("accuracy"), (int, float)):
            payload["accuracy"] = float(metrics["accuracy"])
        classes = metadata.get("classes")
        if isinstance(classes, list):
            payload["classes_count"] = len(classes)
        return payload

    def yield_status(self) -> dict[str, Any]:
        """Availability report for the yield regressor."""
        available = self.is_yield_model_available()
        payload: dict[str, Any] = {
            "key": "yield_estimation",
            "display_name": "Crop Yield Estimation",
            "task": "tabular_regression",
            "available": available,
            "model_name": None,
            "model_version": None,
            "accuracy": None,
            "metrics": {},
            "classes_count": None,
            "trained_at": None,
            "dataset": None,
            "message": None,
            "artifact_path": str(self._path(YIELD_MODEL_FILENAME)),
        }
        if not available:
            payload["message"] = (
                "Model not installed. Run `python -m ml.train_yield_model` to train "
                "the yield regressor."
            )
            return payload

        metadata_path = self._path(YIELD_METADATA_FILENAME)
        metadata: dict[str, Any] = {}
        if metadata_path.is_file():
            try:
                metadata = self._read_json(metadata_path)
            except (OSError, ValueError, json.JSONDecodeError):
                metadata = {}

        payload["model_name"] = metadata.get("model_name")
        payload["model_version"] = metadata.get("model_version")
        payload["metrics"] = metadata.get("metrics", {})
        payload["trained_at"] = metadata.get("trained_at")
        payload["dataset"] = metadata.get("dataset")
        payload["message"] = "Model available."
        payload["classes_count"] = metadata.get("classes_count")
        return payload

    def all_status(self) -> dict[str, Any]:
        """Status of every model plus the overall availability."""
        disease = self.disease_status()
        crop = self.crop_status()
        yield_ = self.yield_status()
        models = [disease, crop, yield_]
        return {
            "models": models,
            "available_count": sum(1 for model in models if model["available"]),
            "total_count": len(models),
        }


registry = ModelRegistry()
