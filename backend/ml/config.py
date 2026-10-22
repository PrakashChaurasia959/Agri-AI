"""Machine learning configuration.

Every tunable that affects training reproducibility lives here so that a run
can be reproduced exactly from the metadata written next to the model.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ``backend/`` directory.
ML_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = ML_ROOT.parent
PROJECT_ROOT = BACKEND_ROOT.parent

DATA_DIR = BACKEND_ROOT / "data"
DATASET_DIR = DATA_DIR / "dataset"
MODEL_DIR = DATA_DIR / "models"
UPLOAD_DIR = DATA_DIR / "uploads"

# PlantVillage materialised as ``<dataset>/PlantVillage/<Class Name>/*.jpg``
PLANTVILLAGE_DIR = DATASET_DIR / "PlantVillage"
CROP_RECOMMENDATION_CSV = DATASET_DIR / "crop_recommendation.csv"
CROP_YIELD_CSV = DATASET_DIR / "crop_yield.csv"

# Deterministic runs.
RANDOM_SEED = 42

# The disease model is versioned independently of the application.
DISEASE_MODEL_VERSION = "1.0.0"
CROP_MODEL_VERSION = "1.0.0"
YIELD_MODEL_VERSION = "1.0.0"

DISEASE_MODEL_FILENAME = "plant_disease_mobilenetv2.keras"
CROP_MODEL_FILENAME = "crop_recommender.joblib"
YIELD_MODEL_FILENAME = "crop_yield_regressor.joblib"

DISEASE_LABELS_FILENAME = "plant_disease_labels.json"
DISEASE_METADATA_FILENAME = "plant_disease_metadata.json"
CROP_METADATA_FILENAME = "crop_recommender_metadata.json"
YIELD_METADATA_FILENAME = "crop_yield_metadata.json"


@dataclass(frozen=True)
class DiseaseTrainingConfig:
    """Hyper-parameters for the CNN disease classifier."""

    image_size: int = 224
    input_channels: int = 3
    batch_size: int = 32
    epochs: int = 12
    learning_rate: float = 1e-3
    fine_tune_learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    label_smoothing: float = 0.05
    validation_split: float = 0.15
    seed: int = RANDOM_SEED
    base_model: str = "MobileNetV2"
    # Fraction of the base model kept trainable in the fine-tuning phase.
    fine_tune_unfreeze_ratio: float = 0.35
    early_stopping_patience: int = 3
    reduce_lr_patience: int = 2
    reduce_lr_factor: float = 0.5
    min_lr: float = 1e-6
    dropout_rate: float = 0.3
    dense_units: int = 128
    activation: str = "relu"
    # -- normalisation --------------------------------------------------
    # These must stay identical to ``ml.preprocessing.PreprocessConfig`` and
    # ``ml.config.InferenceConfig``.  The training pipeline divides by
    # ``rescale_factor`` and then standardises with ``mean``/``std``; the
    # inference pipeline does exactly the same.  A regression test asserts
    # the three definitions agree, because a mismatch silently destroys the
    # pretrained features (the model then only sees a constant image).
    rescale_factor: float = 1.0 / 255.0
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CropTrainingConfig:
    """Hyper-parameters for the crop recommendation classifier."""

    test_size: float = 0.2
    random_state: int = RANDOM_SEED
    n_estimators: int = 300
    max_depth: int | None = 12
    min_samples_leaf: int = 2
    class_weight: str = "balanced"
    n_jobs: int = -1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class YieldTrainingConfig:
    """Hyper-parameters for the yield regression model."""

    test_size: float = 0.2
    random_state: int = RANDOM_SEED
    n_estimators: int = 300
    max_depth: int | None = 14
    min_samples_leaf: int = 3
    n_jobs: int = -1
    # Rows-per-hectare uncertainty band used for the reported interval.
    residual_scale: float = 1.96

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AugmentationConfig:
    """Training-only image augmentation.

    Augmentation is deliberately *not* applied at inference time.
    """

    rotation_range: float = 25.0
    width_shift_range: float = 0.10
    height_shift_range: float = 0.10
    shear_range: float = 8.0
    zoom_range: float = 0.15
    horizontal_flip: bool = True
    brightness_range: tuple[float, float] = (0.85, 1.15)
    fill_mode: str = "reflect"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetConfig:
    """Where the datasets live and how they are licensed."""

    disease: str = "PlantVillage (leaf images, 38 classes)"
    disease_source: str = (
        "https://huggingface.co/datasets/GVJahnavi/PlantVillage_dataset "
        "(mirror of the PlantVillage dataset by Hughes & Salathé, 2015)"
    )
    crop_recommendation: str = "Crop Recommendation Dataset (N, P, K, temperature, humidity, pH, rainfall)"
    crop_recommendation_source: str = (
        "https://huggingface.co/datasets/randalakab/Crop-recommendation"
    )
    yield_dataset: str = "Crop Yield Prediction Dataset (N, P, K, climate, yield)"
    yield_dataset_source: str = (
        "https://huggingface.co/datasets/Jakehills/Crop_Yield_Fertilizer"
    )
    notes: str = (
        "Datasets are mirrored on the Hugging Face Hub. Each dataset card "
        "carries the upstream licence; review it before commercial use."
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InferenceConfig:
    """Preprocessing settings that must match the training configuration."""

    image_size: int = 224
    interpolation: str = "bilinear"
    rescale_factor: float = 1.0 / 255.0
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
    confidence_threshold: float = 0.35
    top_k: int = 5

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class Paths:
    """Resolved filesystem locations."""

    model_dir: Path = field(default_factory=lambda: MODEL_DIR)
    dataset_dir: Path = field(default_factory=lambda: DATASET_DIR)

    @property
    def disease_model(self) -> Path:
        return self.model_dir / DISEASE_MODEL_FILENAME

    @property
    def disease_labels(self) -> Path:
        return self.model_dir / DISEASE_LABELS_FILENAME

    @property
    def disease_metadata(self) -> Path:
        return self.model_dir / DISEASE_METADATA_FILENAME

    @property
    def crop_model(self) -> Path:
        return self.model_dir / CROP_MODEL_FILENAME

    @property
    def crop_metadata(self) -> Path:
        return self.model_dir / CROP_METADATA_FILENAME

    @property
    def yield_model(self) -> Path:
        return self.model_dir / YIELD_MODEL_FILENAME

    @property
    def yield_metadata(self) -> Path:
        return self.model_dir / YIELD_METADATA_FILENAME


def ensure_directories() -> None:
    """Create the directories the application expects to exist."""
    for directory in (MODEL_DIR, DATASET_DIR, UPLOAD_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def device_name() -> str:
    """Resolve the compute device for training/inference."""
    explicit = os.getenv("AGRIVISION_DEVICE", "").strip().lower()
    if explicit in {"cpu", "gpu"}:
        return explicit
    try:  # pragma: no cover - depends on the host
        import tensorflow as tf

        if tf.config.list_physical_devices("GPU"):
            return "gpu"
    except Exception:
        pass
    return "cpu"
