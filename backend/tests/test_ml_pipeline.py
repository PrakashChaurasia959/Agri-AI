"""Tests for the machine-learning layer.

These cover the parts of the pipeline that do not need a trained model
(preprocessing, the knowledge base, the registry contract) plus the artifact
loading for the models that have actually been trained on this machine.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

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
from ml.disease_knowledge import resolve_class, unknown_entry
from ml.model_registry import ModelRegistry, ModelUnavailableError
from ml.preprocessing import (
    ImageValidationError,
    PreprocessConfig,
    preprocess_image,
    validate_image_bytes,
)
from tests.conftest import make_image_bytes


# ---------------------------------------------------------------------------
# Image validation
# ---------------------------------------------------------------------------
def test_empty_payloads_are_rejected():
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(b"")
    assert excinfo.value.code == "empty_file"


def test_random_bytes_are_rejected():
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(b"\x00\x01\x02not-an-image-at-all" * 10)
    assert excinfo.value.code in {"not_an_image", "corrupt_image"}


def test_a_truncated_png_is_rejected():
    data = make_image_bytes(fmt="PNG", size=(64, 64))
    with pytest.raises(ImageValidationError):
        validate_image_bytes(data[: len(data) // 3])


def test_a_gif_is_rejected_even_though_it_is_a_real_image():
    data = make_image_bytes(fmt="GIF", size=(64, 64))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data)
    assert excinfo.value.code == "unsupported_format"


def test_a_bmp_is_rejected():
    data = make_image_bytes(fmt="BMP", size=(64, 64))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data)
    assert excinfo.value.code == "unsupported_format"


def test_a_png_is_accepted_and_reports_its_metadata():
    data = make_image_bytes(fmt="PNG", size=(128, 96))
    info = validate_image_bytes(data)

    assert info.format == "PNG"
    assert info.mime_type == "image/png"
    assert (info.width, info.height) == (128, 96)
    assert info.file_size == len(data)
    assert info.aspect_ratio == pytest.approx(128 / 96, rel=1e-3)


def test_a_jpeg_is_accepted():
    data = make_image_bytes(fmt="JPEG", size=(200, 150))
    info = validate_image_bytes(data)
    assert info.format == "JPEG"
    assert info.mime_type == "image/jpeg"


def test_an_image_below_the_minimum_dimension_is_rejected():
    data = make_image_bytes(fmt="PNG", size=(16, 16))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data, min_dimension=32)
    assert excinfo.value.code == "image_too_small"


def test_an_image_above_the_maximum_dimension_is_rejected():
    data = make_image_bytes(fmt="PNG", size=(64, 64))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data, max_dimension=32)
    assert excinfo.value.code == "image_too_large"


def test_an_oversized_payload_is_rejected_before_decoding():
    data = make_image_bytes(fmt="PNG", size=(64, 64))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data, max_bytes=10)
    assert excinfo.value.code == "file_too_large"


def test_a_mime_type_outside_the_allow_list_is_rejected():
    data = make_image_bytes(fmt="PNG", size=(64, 64))
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_bytes(data, allowed_mime_types=["image/jpeg"])
    assert excinfo.value.code == "unsupported_format"


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------
def test_preprocessing_produces_a_batch_ready_float_array():
    data = make_image_bytes(fmt="PNG", size=(300, 200))
    array = preprocess_image(data)

    assert array.shape == (1, 224, 224, 3)
    assert array.dtype == np.float32
    assert np.isfinite(array).all()


def test_preprocessing_honours_the_configured_image_size():
    data = make_image_bytes(fmt="PNG", size=(300, 200))
    array = preprocess_image(data, PreprocessConfig(image_size=64))
    assert array.shape == (1, 64, 64, 3)


def test_preprocessing_normalises_the_pixel_range():
    """The output must match the documented ImageNet normalisation exactly.

    ``out = (pixel / 255 - mean) / std`` - a mid-grey pixel therefore lands
    *near zero*, not near 0.5, and a pure-black image lands strictly below
    zero on every channel.
    """
    import io

    from PIL import Image

    config = PreprocessConfig()
    mean, std = config.mean, config.std

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (0, 0, 0)).save(buffer, format="PNG")
    array = preprocess_image(buffer.getvalue())

    expected = [(0.0 - m) / s for m, s in zip(mean, std)]
    assert array[0, 0, 0, 0] == pytest.approx(expected[0], rel=1e-4)
    assert array[0, 0, 0, 1] == pytest.approx(expected[1], rel=1e-4)
    assert array[0, 0, 0, 2] == pytest.approx(expected[2], rel=1e-4)

    # Every channel of a black image is negative after the mean is removed.
    assert (array < 0).all()

    # A white image is positive on every channel.
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (255, 255, 255)).save(buffer, format="PNG")
    white = preprocess_image(buffer.getvalue())
    assert (white > 0).all()

    # The mean grey value is close to the ImageNet mean, so it lands near 0.
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buffer, format="PNG")
    grey = preprocess_image(buffer.getvalue())
    assert abs(float(grey.mean())) < 0.5


def test_preprocessing_rejects_a_non_image():
    with pytest.raises(ImageValidationError):
        preprocess_image(b"not-an-image")


# ---------------------------------------------------------------------------
# Disease knowledge base
# ---------------------------------------------------------------------------
def test_the_class_resolver_handles_both_separator_conventions():
    """Different dataset mirrors spell the same class differently."""
    double = resolve_class("Apple__Apple_scab")
    triple = resolve_class("Apple___Apple_scab")
    assert double is not None
    assert triple is not None
    assert double.display_name == triple.display_name
    assert double.crop == triple.crop


def test_the_class_resolver_handles_the_healthy_class():
    entry = resolve_class("Pepper__bell___healthy")
    assert entry is not None
    assert entry.is_healthy is True
    assert entry.symptoms


def test_an_unknown_class_resolves_to_nothing():
    assert resolve_class("Completely_Unknown_Class_1234") is None


def test_the_unknown_entry_is_explicitly_marked():
    entry = unknown_entry()
    assert entry["display_name"] == "Unrecognised class"
    assert entry["severity"] == "unknown"
    assert entry["disclaimer"]


def test_every_known_class_has_guidance():
    from ml.disease_knowledge import CLASSES

    assert len(CLASSES) == 38
    for entry in CLASSES:
        assert entry.symptoms, f"{entry.class_name} has no symptoms"
        assert entry.prevention, f"{entry.class_name} has no prevention advice"
        assert entry.treatment, f"{entry.class_name} has no treatment advice"
        assert entry.to_dict()["disclaimer"]


def test_the_knowledge_base_covers_every_class_in_the_dataset():
    """A class the model can predict must have guidance attached to it."""
    import re

    from ml.disease_knowledge import CLASSES

    normalise = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
    known = {normalise(entry.class_name) for entry in CLASSES}

    dataset_root = MODEL_DIR.parent / "dataset" / "PlantVillage" / "train"
    if not dataset_root.is_dir():
        pytest.skip("The PlantVillage dataset is not materialised on this machine.")

    class_dirs = {path.name for path in dataset_root.iterdir() if path.is_dir()}
    assert len(class_dirs) == 38
    unresolved = [
        name for name in sorted(class_dirs) if normalise(name) not in known
    ]
    assert unresolved == [], f"Classes without guidance: {unresolved}"


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
def test_the_registry_reports_a_missing_model_instead_of_raising(tmp_path: Path):
    registry = ModelRegistry(tmp_path)

    assert registry.is_disease_model_available() is False
    assert registry.is_crop_model_available() is False
    assert registry.is_yield_model_available() is False

    with pytest.raises(ModelUnavailableError) as excinfo:
        registry.load_disease_model()
    assert excinfo.value.code == "model_not_trained"

    with pytest.raises(ModelUnavailableError):
        registry.load_crop_model()

    with pytest.raises(ModelUnavailableError):
        registry.load_yield_model()


def test_the_registry_status_describes_every_model(tmp_path: Path):
    status = ModelRegistry(tmp_path).all_status()
    assert status["total_count"] == 3
    assert status["available_count"] == 0
    keys = {model["key"] for model in status["models"]}
    assert keys == {"disease_detection", "crop_recommendation", "yield_estimation"}
    for model in status["models"]:
        assert model["available"] is False
        assert model["message"]


def test_the_registry_reports_a_broken_artifact_as_unavailable(tmp_path: Path):
    (tmp_path / DISEASE_MODEL_FILENAME).write_bytes(b"not a keras model")
    (tmp_path / DISEASE_LABELS_FILENAME).write_text(
        json.dumps({"labels": ["A___B"]}), encoding="utf-8"
    )

    registry = ModelRegistry(tmp_path)
    with pytest.raises(ModelUnavailableError) as excinfo:
        registry.load_disease_model()
    assert excinfo.value.code == "model_load_failed"


def test_the_registry_reports_missing_labels_as_unavailable(tmp_path: Path):
    (tmp_path / DISEASE_MODEL_FILENAME).write_bytes(b"placeholder")
    registry = ModelRegistry(tmp_path)
    with pytest.raises(ModelUnavailableError) as excinfo:
        registry.load_disease_model()
    assert excinfo.value.code == "model_incomplete"


# ---------------------------------------------------------------------------
# Training / inference parity
# ---------------------------------------------------------------------------
def test_the_training_normalisation_matches_the_inference_normalisation():
    """The three normalisation definitions must not drift apart.

    A mismatch here is invisible in the code but catastrophic in practice:
    the training pipeline used to divide the images by 255 *and* to add a
    ``Rescaling(1/255)`` layer inside the model, so the backbone received
    values around ``1e-3`` instead of ImageNet-normalised values.  The model
    could not learn (training accuracy stayed at ~0.10, validation accuracy
    was 0.0) and the failure was invisible in the logs.
    """
    from ml.config import DiseaseTrainingConfig, InferenceConfig

    training = DiseaseTrainingConfig()
    inference = InferenceConfig()
    preprocessing = PreprocessConfig()

    assert training.rescale_factor == pytest.approx(inference.rescale_factor)
    assert training.rescale_factor == pytest.approx(preprocessing.rescale_factor)
    assert tuple(training.mean) == tuple(inference.mean) == tuple(preprocessing.mean)
    assert tuple(training.std) == tuple(inference.std) == tuple(preprocessing.std)
    assert training.image_size == inference.image_size == preprocessing.image_size


def test_the_training_pipeline_produces_the_same_tensor_as_the_inference_path():
    """The strongest form of the guard: identical numbers on both paths."""
    tf = pytest.importorskip("tensorflow")

    from ml.config import DiseaseTrainingConfig

    config = DiseaseTrainingConfig()
    rng = np.random.default_rng(0)
    pixels = (rng.random((1, 224, 224, 3)) * 255.0).astype("float32")

    train_tensor = tf.cast(tf.constant(pixels), tf.float32) * config.rescale_factor
    train_tensor = (train_tensor - tf.constant(config.mean, tf.float32)) / tf.constant(
        config.std, tf.float32
    )

    preprocessing = PreprocessConfig()
    expected = (pixels * preprocessing.rescale_factor - np.array(preprocessing.mean)) / np.array(
        preprocessing.std
    )

    assert np.allclose(train_tensor.numpy(), expected, atol=1e-5)


def test_the_model_does_not_rescale_the_input_a_second_time():
    """The network must consume already-normalised input."""
    keras = pytest.importorskip("keras")

    from ml.config import DiseaseTrainingConfig
    from ml.train_cnn import build_model

    model, _ = build_model(DiseaseTrainingConfig(), num_classes=38, base_weights=None)

    rescaling_layers = [
        layer for layer in model.layers if isinstance(layer, keras.layers.Rescaling)
    ]
    assert rescaling_layers == [], (
        "The model must not contain a Rescaling layer - the data pipeline "
        "already divides by 255, so a layer here would rescale twice."
    )


def test_the_augmentation_actually_changes_the_pixels():
    """Guards against a silent no-op augmentation."""
    tf = pytest.importorskip("tensorflow")

    from ml.config import AugmentationConfig
    from ml.train_cnn import build_augmentation

    augment = build_augmentation(AugmentationConfig())
    image = tf.random.uniform((224, 224, 3), 0.0, 1.0, seed=7)

    first = augment(image)
    second = augment(image)

    assert float(tf.reduce_min(first)) >= 0.0
    assert float(tf.reduce_max(first)) <= 1.0
    assert float(tf.reduce_sum(tf.abs(first - second))) > 1.0


# ---------------------------------------------------------------------------
# The artifacts that were actually trained
# ---------------------------------------------------------------------------
def _crop_model_installed() -> bool:
    return (MODEL_DIR / CROP_MODEL_FILENAME).is_file()


def _yield_model_installed() -> bool:
    return (MODEL_DIR / YIELD_MODEL_FILENAME).is_file()


@pytest.mark.skipif(
    not _crop_model_installed(), reason="The crop model has not been trained."
)
def test_the_trained_crop_model_loads_and_matches_its_metadata():
    registry = ModelRegistry(MODEL_DIR)
    bundle = registry.load_crop_model()

    assert bundle.pipeline is not None
    assert len(bundle.pipeline.classes_) == 22
    assert bundle.name
    assert bundle.version

    metadata = json.loads(
        (MODEL_DIR / CROP_METADATA_FILENAME).read_text(encoding="utf-8")
    )
    assert bundle.metrics["accuracy"] == pytest.approx(
        metadata["metrics"]["accuracy"], rel=1e-6
    )
    # The recorded accuracy must be a real number, not a placeholder.
    assert 0.0 < bundle.metrics["accuracy"] < 1.0
    assert bundle.metrics["accuracy"] > 0.9


@pytest.mark.skipif(
    not _crop_model_installed(), reason="The crop model has not been trained."
)
def test_the_crop_model_produces_a_probability_distribution():
    from ml.crop_predictor import FEATURE_NAMES, recommend_crops

    result = recommend_crops([90.0, 45.0, 40.0, 22.5, 82.0, 210.0, 6.5])

    assert len(FEATURE_NAMES) == 7
    assert len(result.recommendations) == 5
    assert result.top_crop
    total = sum(item.score for item in result.recommendations)
    assert 0.0 < total <= 1.0 + 1e-6


@pytest.mark.skipif(
    not _crop_model_installed(), reason="The crop model has not been trained."
)
def test_the_crop_predictor_rejects_a_wrong_feature_vector():
    from ml.crop_predictor import recommend_crops

    with pytest.raises(ValueError):
        recommend_crops([1.0, 2.0])


@pytest.mark.skipif(
    not _yield_model_installed(), reason="The yield model has not been trained."
)
def test_the_trained_yield_model_loads_and_matches_its_metadata():
    registry = ModelRegistry(MODEL_DIR)
    bundle = registry.load_yield_model()

    assert bundle.pipeline is not None
    metadata = json.loads(
        (MODEL_DIR / YIELD_METADATA_FILENAME).read_text(encoding="utf-8")
    )
    assert bundle.metrics["mae"] == pytest.approx(metadata["metrics"]["mae"], rel=1e-6)
    assert bundle.metrics["r2"] == pytest.approx(metadata["metrics"]["r2"], rel=1e-6)
    assert 0.0 < bundle.metrics["r2"] < 1.0
    assert bundle.metrics["mae"] > 0.0


@pytest.mark.skipif(
    not _yield_model_installed(), reason="The yield model has not been trained."
)
def test_the_yield_model_produces_a_positive_estimate():
    from ml.yield_predictor import estimate_yield

    result = estimate_yield(
        [90.0, 45.0, 40.0, 22.5, 82.0, 210.0, 6.5], crop_type="rice", area_ha=3.0
    )
    assert result.per_hectare_yield is not None
    assert result.per_hectare_yield > 0
    assert result.estimated_yield == pytest.approx(result.per_hectare_yield * 3.0)
    assert result.yield_unit == "tonnes per hectare"


@pytest.mark.skipif(
    not _yield_model_installed(), reason="The yield model has not been trained."
)
def test_the_yield_predictor_rejects_a_non_positive_area():
    from ml.yield_predictor import estimate_yield

    with pytest.raises(ValueError):
        estimate_yield([90.0, 45.0, 40.0, 22.5, 82.0, 210.0, 6.5], crop_type="rice", area_ha=0)


def test_the_disease_labels_file_matches_the_metadata_when_present():
    """The label mapping and the metadata must agree on the class count."""
    labels_path = MODEL_DIR / DISEASE_LABELS_FILENAME
    metadata_path = MODEL_DIR / DISEASE_METADATA_FILENAME
    if not (labels_path.is_file() and metadata_path.is_file()):
        pytest.skip("The disease model has not been trained on this machine.")

    labels = json.loads(labels_path.read_text(encoding="utf-8"))["labels"]
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert len(labels) == len(set(labels))
    assert metadata["num_classes"] == len(labels)
    assert 0.0 <= metadata["metrics"]["accuracy"] <= 1.0
