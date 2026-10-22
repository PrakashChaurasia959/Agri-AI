"""Train the crop disease classifier.

The model is a MobileNetV2 backbone pre-trained on ImageNet with a custom
classification head, fine-tuned on the PlantVillage dataset (38 classes).

Usage
-----
::

    python -m ml.train_cnn                       # full training run
    python -m ml.train_cnn --epochs 3 --limit 4000
    python -m ml.train_cnn --evaluate-only        # re-evaluate an existing model

Design notes
------------
* The upstream PlantVillage split is respected: images from the ``train``
  shard are used for fitting, images from the ``test`` shard are only ever
  used to produce the final reported metrics.
* Augmentation is applied to the training split only.
* The training pipeline and the inference pipeline apply *exactly* the same
  normalisation (``x / 255`` followed by ImageNet standardisation).  The
  normalisation lives in the data pipeline rather than in a ``Rescaling``
  layer inside the model, because a layer would divide by 255 a second time
  and collapse the input range to ~1e-3, which silently destroys the
  pretrained features.
* Training accuracy is never reported as test accuracy; the summary printed
  at the end contains the held-out test metrics.
* The run is reproducible: the seed, the hyper-parameters and the library
  versions are written into ``plant_disease_metadata.json`` next to the model.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.config import (  # noqa: E402
    DISEASE_LABELS_FILENAME,
    DISEASE_METADATA_FILENAME,
    DISEASE_MODEL_FILENAME,
    DISEASE_MODEL_VERSION,
    PLANTVILLAGE_DIR,
    AugmentationConfig,
    DatasetConfig,
    DiseaseTrainingConfig,
    InferenceConfig,
    ensure_directories,
)
from ml.evaluation import classification_metrics, format_classification_summary  # noqa: E402

logger = logging.getLogger("agrivision.train_cnn")

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


def set_seed(seed: int) -> None:
    """Seed every random source that influences the run."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover
        pass
    try:
        import tensorflow as tf

        tf.random.set_seed(seed)
        tf.keras.utils.set_random_seed(seed)
    except ImportError:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def discover_classes(train_dir: Path) -> list[str]:
    """Return the sorted class folder names of a dataset root."""
    if not train_dir.is_dir():
        raise FileNotFoundError(
            f"Dataset directory not found: {train_dir}. "
            "Run `python -m scripts.download_datasets --disease` first."
        )
    classes = sorted(entry.name for entry in train_dir.iterdir() if entry.is_dir())
    if not classes:
        raise FileNotFoundError(f"No class folders found in {train_dir}")
    return classes


def build_datasets(
    config: DiseaseTrainingConfig,
    augmentation: AugmentationConfig,
    *,
    limit: int | None = None,
) -> tuple[Any, Any, Any, list[str]]:
    """Build the train / validation / test datasets.

    Returns ``(train_ds, val_ds, test_ds, class_names)``.
    """
    import tensorflow as tf

    train_dir = PLANTVILLAGE_DIR / "train"
    test_dir = PLANTVILLAGE_DIR / "test"

    class_names = discover_classes(train_dir)
    image_size = (config.image_size, config.image_size)

    mean = tf.constant(config.mean, dtype=tf.float32)
    std = tf.constant(config.std, dtype=tf.float32)
    augment = build_augmentation(augmentation)

    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=image_size,
        batch_size=config.batch_size,
        shuffle=True,
        seed=config.seed,
        validation_split=config.validation_split,
        subset="training",
    )

    val_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=image_size,
        batch_size=config.batch_size,
        shuffle=False,
        seed=config.seed,
        validation_split=config.validation_split,
        subset="validation",
    )

    if test_dir.is_dir():
        test_ds = tf.keras.utils.image_dataset_from_directory(
            test_dir,
            labels="inferred",
            label_mode="categorical",
            class_names=class_names,
            image_size=image_size,
            batch_size=config.batch_size,
            shuffle=False,
        )
    else:  # pragma: no cover - defensive
        logger.warning("No test directory found - the test split will be empty")
        test_ds = tf.data.Dataset.from_tensor_slices(([], []))

    def prepare(image, label):
        """Validation / test normalisation - must match the inference path."""
        image = tf.cast(image, tf.float32) * config.rescale_factor
        image = (image - mean) / std
        return image, label

    def prepare_train(image, label):
        """Training normalisation - augment first, then normalise."""
        image = tf.cast(image, tf.float32) * config.rescale_factor
        image = augment(image)
        image = (image - mean) / std
        return image, label

    train_ds = train_ds.map(prepare_train, num_parallel_calls=tf.data.AUTOTUNE)
    val_ds = val_ds.map(prepare, num_parallel_calls=tf.data.AUTOTUNE)
    test_ds = test_ds.map(prepare, num_parallel_calls=tf.data.AUTOTUNE)

    train_ds = train_ds.cache().prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.cache().prefetch(tf.data.AUTOTUNE)
    test_ds = test_ds.cache().prefetch(tf.data.AUTOTUNE)

    if limit:
        train_ds = train_ds.take(limit)
        val_ds = val_ds.take(max(1, limit // 10))

    return train_ds, val_ds, test_ds, class_names


def build_augmentation(augmentation: AugmentationConfig) -> Any:
    """Return the training-only augmentation callable.

    The returned function is applied inside the **training** dataset pipeline
    only, which keeps the persisted model a pure inference model - no random
    layer is baked into the artifact.

    The geometric part (rotation, translation, shear, zoom, flip) uses the
    Keras random layers, which are explicitly documented as safe inside a
    ``tf.data`` pipeline and are inert when ``training`` is ``False``.

    The brightness part is applied separately because ``keras.layers
    .RandomBrightness`` is an *additive* offset scaled to a
    ``value_range=(0, 255)`` by default - on a ``[0, 1]`` image that would
    saturate the whole frame to black.  A multiplicative factor in
    ``[low, high]`` reproduces the configured semantics exactly.

    Note on unit conversions - the configuration is expressed in human units
    while the Keras layers use fractions:

    * ``rotation_range`` is in degrees; Keras wants a fraction of a full turn.
    * ``shear_range`` is in degrees; Keras wants the tangent of that angle.
    * ``shift``/``zoom`` ranges are already fractions of the image size.
    """
    import keras
    import tensorflow as tf

    shear = math.tan(math.radians(augmentation.shear_range))

    layers: list[Any] = [
        keras.layers.RandomRotation(
            (-augmentation.rotation_range / 360.0, augmentation.rotation_range / 360.0),
            fill_mode=augmentation.fill_mode,
        ),
        keras.layers.RandomTranslation(
            augmentation.height_shift_range,
            augmentation.width_shift_range,
            fill_mode=augmentation.fill_mode,
        ),
        keras.layers.RandomShear(
            shear,
            shear,
            fill_mode=augmentation.fill_mode,
        ),
        keras.layers.RandomZoom(
            (-augmentation.zoom_range, augmentation.zoom_range),
            (-augmentation.zoom_range, augmentation.zoom_range),
            fill_mode=augmentation.fill_mode,
        ),
    ]
    if augmentation.horizontal_flip:
        layers.append(keras.layers.RandomFlip("horizontal"))

    geometric = keras.Sequential(layers, name="augmentation_geometric")
    low, high = augmentation.brightness_range

    def _augment(image: Any) -> Any:
        image = geometric(image, training=True)
        factor = tf.random.uniform([], low, high)
        return tf.clip_by_value(image * factor, 0.0, 1.0)

    return _augment


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def build_model(
    config: DiseaseTrainingConfig,
    num_classes: int,
    *,
    base_weights: str = "imagenet",
):
    """Build the MobileNetV2 transfer-learning classifier.

    The network expects **ImageNet-normalised** input, i.e. the tensor that
    ``keras.applications.mobilenet_v2.preprocess_input`` produces
    (``x / 255`` followed by standardisation with the ImageNet mean/std).
    The normalisation therefore lives in the *data pipeline*, not in a
    ``Rescaling`` layer: a layer inside the model would apply a second
    division by 255 on top of the pipeline and collapse the input range to
    roughly ``1e-3``, which destroys the pretrained features.

    Returns ``(model, base_model)`` so the caller can fine-tune the base
    network without guessing at layer names.
    """
    import keras

    base = keras.applications.MobileNetV2(
        weights=base_weights,
        input_shape=(config.image_size, config.image_size, 3),
        include_top=False,
    )
    base.trainable = False

    model = keras.Sequential(
        [
            keras.layers.Input(
                shape=(config.image_size, config.image_size, 3), name="input"
            ),
            base,
            keras.layers.GlobalAveragePooling2D(name="global_pool"),
            keras.layers.Dropout(config.dropout_rate, name="dropout"),
            keras.layers.Dense(
                config.dense_units, activation=config.activation, name="dense"
            ),
            keras.layers.Dropout(config.dropout_rate, name="dropout_2"),
            keras.layers.Dense(num_classes, activation="softmax", name="disease_class"),
        ],
        name="agrivision_disease_cnn",
    )
    return model, base


def unfreeze_base_model(base: Any, config: DiseaseTrainingConfig) -> int:
    """Unfreeze the top fraction of the base network for fine-tuning.

    Batch-normalisation layers stay frozen even when the rest is unfrozen -
    this is standard practice for small transfer-learning datasets because
    running statistics would otherwise be corrupted by the small batch sizes.
    """
    total = len(base.layers)
    unfreeze_from = int(total * (1 - config.fine_tune_unfreeze_ratio))
    for layer in base.layers[unfreeze_from:]:
        layer.trainable = True
    for layer in base.layers:
        if layer.__class__.__name__.startswith("BatchNormalization"):
            layer.trainable = False
    return total - unfreeze_from


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(config: DiseaseTrainingConfig, augmentation: AugmentationConfig, args: argparse.Namespace) -> dict[str, Any]:
    """Run the full training pipeline and persist the artifacts."""
    import keras
    import tensorflow as tf

    set_seed(config.seed)

    print("=" * 72)
    print("AgriVision AI - crop disease classifier training")
    print("=" * 72)

    train_ds, val_ds, test_ds, class_names = build_datasets(
        config, augmentation, limit=args.limit
    )
    print(f"Classes            : {len(class_names)}")
    print(f"Training batches   : {tf.data.experimental.cardinality(train_ds).numpy()}")
    print(f"Validation batches : {tf.data.experimental.cardinality(val_ds).numpy()}")
    print(f"Test batches       : {tf.data.experimental.cardinality(test_ds).numpy()}")

    num_classes = len(class_names)
    model, base_model = build_model(config, num_classes)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss=keras.losses.CategoricalCrossentropy(
            label_smoothing=config.label_smoothing
        ),
        metrics=["accuracy"],
    )
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=config.early_stopping_patience,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=config.reduce_lr_factor,
            patience=config.reduce_lr_patience,
            min_lr=config.min_lr,
            verbose=1,
        ),
    ]

    print("\n--- Stage 1: training the classification head ---")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=config.epochs,
        callbacks=callbacks,
    )

    print("\n--- Stage 2: fine-tuning the top of the base network ---")
    unfrozen = unfreeze_base_model(base_model, config)
    print(f"Unfroze {unfrozen} base layers")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.fine_tune_learning_rate),
        loss=keras.losses.CategoricalCrossentropy(
            label_smoothing=config.label_smoothing
        ),
        metrics=["accuracy"],
    )
    history_fine = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=max(1, config.epochs // 2),
        callbacks=callbacks,
    )

    # ---- evaluation on the held-out test split ------------------------
    print("\n--- Evaluating on the held-out test split ---")
    y_true: list[int] = []
    y_pred: list[int] = []
    for images, labels in test_ds:
        predictions = model.predict(images, verbose=0)
        y_true.extend(labels.numpy().argmax(axis=1).tolist())
        y_pred.extend(predictions.argmax(axis=1).tolist())

    if not y_true:
        raise RuntimeError("The test split is empty - nothing to evaluate.")

    metrics = classification_metrics(y_true, y_pred, labels=class_names)
    print(format_classification_summary(metrics))

    train_accuracy = float(history.history.get("accuracy", [0.0])[-1])
    validation_accuracy = float(history.history.get("val_accuracy", [0.0])[-1])
    fine_train_accuracy = float(history_fine.history.get("accuracy", [0.0])[-1])
    fine_validation_accuracy = float(history_fine.history.get("val_accuracy", [0.0])[-1])

    print("\nTraining metrics (for reference only - NOT test accuracy):")
    print(f"  stage 1 train accuracy      : {train_accuracy:.4f}")
    print(f"  stage 1 validation accuracy : {validation_accuracy:.4f}")
    print(f"  stage 2 train accuracy      : {fine_train_accuracy:.4f}")
    print(f"  stage 2 validation accuracy : {fine_validation_accuracy:.4f}")

    # ---- persist -------------------------------------------------------
    ensure_directories()
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / DISEASE_MODEL_FILENAME
    model.save(model_path)
    print(f"\nSaved model      -> {model_path}")

    labels_path = model_dir / DISEASE_LABELS_FILENAME
    labels_path.write_text(
        json.dumps(
            {
                "labels": class_names,
                "num_classes": len(class_names),
                "image_size": config.image_size,
                "label_separator_note": (
                    "Folder names use the upstream PlantVillage convention."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved labels     -> {labels_path}")

    metadata: dict[str, Any] = {
        "model_name": "plant_disease_mobilenetv2",
        "model_version": DISEASE_MODEL_VERSION,
        "task": "image_classification",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DatasetConfig().disease,
        "dataset_source": DatasetConfig().disease_source,
        "config": config.to_dict(),
        "augmentation": augmentation.to_dict(),
        "preprocessing": {
            "image_size": config.image_size,
            "rescale_factor": config.rescale_factor,
            "mean": list(config.mean),
            "std": list(config.std),
            "note": (
                "The model expects ImageNet-normalised input "
                "(x / rescale_factor, then standardised with mean/std). "
                "This is identical to ml.preprocessing.PreprocessConfig."
            ),
        },
        "num_classes": len(class_names),
        "classes": class_names,
        "metrics": {
            "accuracy": metrics["accuracy"],
            "precision_macro": metrics["precision_macro"],
            "recall_macro": metrics["recall_macro"],
            "f1_macro": metrics["f1_macro"],
            "f1_weighted": metrics["f1_weighted"],
            "per_class": metrics["per_class"],
            "confusion_matrix": metrics["confusion_matrix"],
        },
        "split": {
            "train_source": "PlantVillage train shard (further split into train/validation)",
            "validation_fraction": config.validation_split,
            "test_source": "PlantVillage test shard (never used for fitting)",
        },
        "training_history": {
            "stage1_accuracy": train_accuracy,
            "stage1_val_accuracy": validation_accuracy,
            "stage2_accuracy": fine_train_accuracy,
            "stage2_val_accuracy": fine_validation_accuracy,
        },
        "library_versions": _library_versions(),
    }
    metadata_path = model_dir / DISEASE_METADATA_FILENAME
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved metadata   -> {metadata_path}")

    return metrics


def _library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for module_name in ("tensorflow", "keras", "numpy", "sklearn", "PIL"):
        try:
            module = __import__(module_name)
            versions[module_name] = str(getattr(module, "__version__", "unknown"))
        except Exception:  # pragma: no cover - defensive
            versions[module_name] = "unknown"
    return versions


def evaluate_existing(model_dir: Path) -> dict[str, Any]:
    """Evaluate an already trained model on the test split."""
    import keras
    import tensorflow as tf

    model_path = model_dir / DISEASE_MODEL_FILENAME
    labels_path = model_dir / DISEASE_LABELS_FILENAME
    if not model_path.is_file() or not labels_path.is_file():
        raise FileNotFoundError(f"No trained model found in {model_dir}")

    model = keras.models.load_model(model_path, compile=False)
    class_names = json.loads(labels_path.read_text(encoding="utf-8"))["labels"]

    test_dir = PLANTVILLAGE_DIR / "test"
    if not test_dir.is_dir():
        raise FileNotFoundError(f"No test split found at {test_dir}")

    test_ds = tf.keras.utils.image_dataset_from_directory(
        test_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=(224, 224),
        batch_size=32,
        shuffle=False,
    )
    inference = InferenceConfig()
    mean = tf.constant(inference.mean, dtype=tf.float32)
    std = tf.constant(inference.std, dtype=tf.float32)

    def _normalise(image, label):
        image = tf.cast(image, tf.float32) * inference.rescale_factor
        image = (image - mean) / std
        return image, label

    test_ds = test_ds.map(_normalise)

    y_true: list[int] = []
    y_pred: list[int] = []
    for images, labels in test_ds:
        predictions = model.predict(images, verbose=0)
        y_true.extend(labels.numpy().argmax(axis=1).tolist())
        y_pred.extend(predictions.argmax(axis=1).tolist())

    metrics = classification_metrics(y_true, y_pred, labels=class_names)
    print(format_classification_summary(metrics))
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the AgriVision disease classifier")
    parser.add_argument("--epochs", type=int, default=DiseaseTrainingConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=DiseaseTrainingConfig.batch_size)
    parser.add_argument("--learning-rate", type=float, default=DiseaseTrainingConfig.learning_rate)
    parser.add_argument("--seed", type=int, default=DiseaseTrainingConfig.seed)
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of training batches")
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only evaluate the existing model on the test split",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s"
    )

    model_dir = Path(args.model_dir) if args.model_dir else Path(__file__).resolve().parents[1] / "data" / "models"

    if args.evaluate_only:
        evaluate_existing(model_dir)
        return 0

    config = DiseaseTrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    augmentation = AugmentationConfig()
    args.model_dir = str(model_dir)
    train(config, augmentation, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
