"""Train the crop yield regression model.

Usage
-----
::

    python -m ml.train_yield_model

The target column (``yield``) is expressed in tonnes per hectare in the
upstream dataset.  The model is fitted on the seven agronomic features and
evaluated on a held-out test split with MAE / RMSE / R2.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml.config import (  # noqa: E402
    CROP_YIELD_CSV,
    DatasetConfig,
    YIELD_METADATA_FILENAME,
    YIELD_MODEL_FILENAME,
    YIELD_MODEL_VERSION,
    YieldTrainingConfig,
    ensure_directories,
)
from ml.evaluation import format_regression_summary, regression_metrics  # noqa: E402
from ml.yield_predictor import FEATURE_NAMES, YIELD_UNIT  # noqa: E402

logger = logging.getLogger("agrivision.train_yield_model")

FEATURE_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET_COLUMN = "yield"


def load_dataset(csv_path: Path) -> pd.DataFrame:
    """Load and validate the yield dataset."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}. "
            "Run `python -m scripts.download_datasets --tabular` first."
        )
    frame = pd.read_csv(csv_path)
    required = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"The dataset is missing the expected columns {missing}. "
            f"Found: {list(frame.columns)}"
        )
    frame = frame.dropna(subset=required)
    return frame


def train(config: YieldTrainingConfig, args: argparse.Namespace) -> dict[str, Any]:
    """Fit the regressor, evaluate it and persist the artifacts."""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    import joblib

    print("=" * 72)
    print("AgriVision AI - crop yield model training")
    print("=" * 72)

    frame = load_dataset(Path(args.dataset))
    if args.limit:
        frame = frame.sample(n=min(args.limit, len(frame)), random_state=config.random_state)

    features = frame[FEATURE_COLUMNS]
    target = frame[TARGET_COLUMN].astype(float)

    print(f"Rows            : {len(frame)}")
    print(f"Crops           : {frame['label'].nunique()}")
    print(f"Target unit     : {YIELD_UNIT}")
    print(f"Target range    : {target.min():.2f} - {target.max():.2f}")

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=config.test_size,
        random_state=config.random_state,
    )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    min_samples_leaf=config.min_samples_leaf,
                    n_jobs=config.n_jobs,
                    random_state=config.random_state,
                ),
            ),
        ]
    )

    print("\nFitting the pipeline ...")
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    metrics = regression_metrics(y_test.tolist(), predictions.tolist())
    print(format_regression_summary(metrics))

    # ---- persist -------------------------------------------------------
    ensure_directories()
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / YIELD_MODEL_FILENAME
    joblib.dump(pipeline, model_path)
    print(f"\nSaved model    -> {model_path}")

    metadata: dict[str, Any] = {
        "model_name": "crop_yield_random_forest",
        "model_version": YIELD_MODEL_VERSION,
        "task": "tabular_regression",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DatasetConfig().yield_dataset,
        "dataset_source": DatasetConfig().yield_dataset_source,
        "features": list(FEATURE_NAMES),
        "target": TARGET_COLUMN,
        "yield_unit": YIELD_UNIT,
        "config": config.to_dict(),
        "metrics": metrics,
        "classes_count": int(frame["label"].nunique()),
        "crops": sorted(frame["label"].unique().tolist()),
        "rows": int(len(frame)),
        "library_versions": {
            "scikit-learn": _sklearn_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    metadata_path = model_dir / YIELD_METADATA_FILENAME
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved metadata -> {metadata_path}")

    return metrics


def _sklearn_version() -> str:
    import sklearn

    return str(sklearn.__version__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the AgriVision yield regressor")
    parser.add_argument("--dataset", type=str, default=str(CROP_YIELD_CSV))
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=YieldTrainingConfig.test_size)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    model_dir = (
        Path(args.model_dir)
        if args.model_dir
        else Path(__file__).resolve().parents[1] / "data" / "models"
    )

    config = YieldTrainingConfig(test_size=args.test_size)
    args.model_dir = str(model_dir)
    train(config, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
