"""Train the crop recommendation classifier.

Usage
-----
::

    python -m ml.train_crop_model
    python -m ml.train_crop_model --limit 5000

The pipeline is a ``StandardScaler`` + ``RandomForestClassifier``.  The model
is evaluated on a held-out test split that is never used for fitting; the
metrics are written next to the artifact so the API can report them.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml.config import (  # noqa: E402
    CROP_METADATA_FILENAME,
    CROP_MODEL_FILENAME,
    CROP_MODEL_VERSION,
    CROP_RECOMMENDATION_CSV,
    CropTrainingConfig,
    DatasetConfig,
    ensure_directories,
)
from ml.crop_predictor import FEATURE_NAMES  # noqa: E402
from ml.evaluation import classification_metrics, format_classification_summary  # noqa: E402

logger = logging.getLogger("agrivision.train_crop_model")

REQUIRED_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "label"]


def load_dataset(csv_path: Path) -> pd.DataFrame:
    """Load and validate the crop recommendation dataset."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}. "
            "Run `python -m scripts.download_datasets --tabular` first."
        )
    frame = pd.read_csv(csv_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            f"The dataset is missing the expected columns {missing}. "
            f"Found: {list(frame.columns)}"
        )
    frame = frame.dropna(subset=REQUIRED_COLUMNS)
    return frame


def train(config: CropTrainingConfig, args: argparse.Namespace) -> dict[str, Any]:
    """Fit the pipeline, evaluate it and persist the artifacts."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    import joblib

    print("=" * 72)
    print("AgriVision AI - crop recommendation model training")
    print("=" * 72)

    frame = load_dataset(Path(args.dataset))
    if args.limit:
        frame = frame.sample(n=min(args.limit, len(frame)), random_state=config.random_state)

    features = frame[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]]
    labels = frame["label"]

    print(f"Rows      : {len(frame)}")
    print(f"Crops     : {labels.nunique()}")
    print(f"Features  : {list(features.columns)}")

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=labels,
    )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    min_samples_leaf=config.min_samples_leaf,
                    class_weight=config.class_weight,
                    n_jobs=config.n_jobs,
                    random_state=config.random_state,
                ),
            ),
        ]
    )

    print("\nFitting the pipeline ...")
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    probabilities = pipeline.predict_proba(x_test)
    confidence = probabilities.max(axis=1)

    class_names = sorted(labels.unique().tolist())
    metrics = classification_metrics(
        [class_names.index(label) for label in y_test.tolist()],
        [class_names.index(label) for label in predictions.tolist()],
        labels=class_names,
    )
    metrics["mean_confidence"] = float(confidence.mean())

    print(format_classification_summary(metrics))

    # ---- persist -------------------------------------------------------
    ensure_directories()
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / CROP_MODEL_FILENAME
    joblib.dump(pipeline, model_path)
    print(f"\nSaved model    -> {model_path}")

    metadata: dict[str, Any] = {
        "model_name": "crop_recommender_random_forest",
        "model_version": CROP_MODEL_VERSION,
        "task": "tabular_classification",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DatasetConfig().crop_recommendation,
        "dataset_source": DatasetConfig().crop_recommendation_source,
        "classes": class_names,
        "classes_count": len(class_names),
        "features": list(FEATURE_NAMES),
        "config": config.to_dict(),
        "metrics": {
            "accuracy": metrics["accuracy"],
            "precision_macro": metrics["precision_macro"],
            "recall_macro": metrics["recall_macro"],
            "f1_macro": metrics["f1_macro"],
            "f1_weighted": metrics["f1_weighted"],
            "mean_confidence": metrics["mean_confidence"],
            "per_class": metrics["per_class"],
            "confusion_matrix": metrics["confusion_matrix"],
        },
        "rows": int(len(frame)),
        "library_versions": {
            "scikit-learn": _sklearn_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    metadata_path = model_dir / CROP_METADATA_FILENAME
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved metadata -> {metadata_path}")

    return metrics


def _sklearn_version() -> str:
    import sklearn

    return str(sklearn.__version__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the AgriVision crop recommender")
    parser.add_argument("--dataset", type=str, default=str(CROP_RECOMMENDATION_CSV))
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=CropTrainingConfig.test_size)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    model_dir = (
        Path(args.model_dir)
        if args.model_dir
        else Path(__file__).resolve().parents[1] / "data" / "models"
    )

    config = CropTrainingConfig(test_size=args.test_size)
    args.model_dir = str(model_dir)
    train(config, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
