"""Evaluation helpers for the ML pipelines.

Classification and regression are kept deliberately separate: the disease
model is a multi-class CNN, the crop recommender is a tabular classifier and
the yield model is a tabular regressor.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)


def classification_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Precision / recall / F1 / accuracy plus a confusion matrix.

    ``labels`` fixes the class ordering so the confusion matrix is stable even
    when a class is missing from a particular evaluation split.
    """
    y_true_array = np.asarray(y_true)
    y_pred_array = np.asarray(y_pred)

    if labels is None:
        labels = [str(label) for label in sorted(set(y_true_array.tolist()))]
    label_indices = list(range(len(labels)))

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true_array, y_pred_array)),
        "precision_macro": float(
            precision_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="macro",
                zero_division=0,
            )
        ),
        "recall_macro": float(
            recall_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="macro",
                zero_division=0,
            )
        ),
        "f1_macro": float(
            f1_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="macro",
                zero_division=0,
            )
        ),
        "precision_weighted": float(
            precision_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="weighted",
                zero_division=0,
            )
        ),
        "recall_weighted": float(
            recall_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="weighted",
                zero_division=0,
            )
        ),
        "f1_weighted": float(
            f1_score(
                y_true_array,
                y_pred_array,
                labels=label_indices,
                average="weighted",
                zero_division=0,
            )
        ),
        "support": int(len(y_true_array)),
        "confusion_matrix": confusion_matrix(
            y_true_array, y_pred_array, labels=label_indices
        ).tolist(),
        "labels": list(labels),
        "per_class": {},
    }

    report = classification_report(
        y_true_array,
        y_pred_array,
        labels=label_indices,
        target_names=list(labels),
        output_dict=True,
        zero_division=0,
    )
    for label in labels:
        entry = report.get(label)
        if not entry:
            continue
        metrics["per_class"][label] = {
            "precision": float(entry.get("precision", 0.0)),
            "recall": float(entry.get("recall", 0.0)),
            "f1": float(entry.get("f1-score", 0.0)),
            "support": int(entry.get("support", 0)),
        }

    return metrics


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> dict[str, Any]:
    """MAE / RMSE / R2 plus a residual summary for a regression model."""
    y_true_array = np.asarray(y_true, dtype=np.float64)
    y_pred_array = np.asarray(y_pred, dtype=np.float64)
    residuals = y_true_array - y_pred_array

    mse = float(mean_squared_error(y_true_array, y_pred_array))
    return {
        "mae": float(mean_absolute_error(y_true_array, y_pred_array)),
        "rmse": float(np.sqrt(mse)),
        "mse": mse,
        "r2": float(r2_score(y_true_array, y_pred_array)),
        "max_absolute_error": float(np.max(np.abs(residuals))) if residuals.size else 0.0,
        "mean_residual": float(np.mean(residuals)) if residuals.size else 0.0,
        "support": int(len(y_true_array)),
    }


def confidence_interval(
    residuals: Sequence[float], scale: float = 1.96
) -> tuple[float, float]:
    """Symmetric residual-based interval half-width around zero."""
    array = np.asarray(residuals, dtype=np.float64)
    if array.size == 0:
        return (0.0, 0.0)
    std = float(np.std(array))
    return (float(-scale * std), float(scale * std))


def format_classification_summary(metrics: dict[str, Any]) -> str:
    """Human readable summary printed at the end of a training run."""
    lines = [
        "Evaluation summary (test split)",
        f"  accuracy        : {metrics['accuracy']:.4f}",
        f"  precision macro : {metrics['precision_macro']:.4f}",
        f"  recall macro    : {metrics['recall_macro']:.4f}",
        f"  f1 macro        : {metrics['f1_macro']:.4f}",
        f"  f1 weighted     : {metrics['f1_weighted']:.4f}",
        f"  support         : {metrics['support']}",
    ]
    return "\n".join(lines)


def format_regression_summary(metrics: dict[str, Any]) -> str:
    """Human readable summary printed at the end of a training run."""
    lines = [
        "Evaluation summary (test split)",
        f"  MAE  : {metrics['mae']:.4f}",
        f"  RMSE : {metrics['rmse']:.4f}",
        f"  R2   : {metrics['r2']:.4f}",
        f"  support : {metrics['support']}",
    ]
    return "\n".join(lines)
