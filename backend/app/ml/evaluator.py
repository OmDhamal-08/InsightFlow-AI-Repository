"""Model evaluation (Phase 11).

Given a fitted pipeline and the held-out test split, produce:

* ``metrics``    — flat dict of scalar scores used in the leaderboard.
    - Classification: accuracy, precision/recall/F1 (weighted and macro),
      ROC-AUC, log loss.
    - Regression: MAE, MSE, RMSE, R², adjusted R², MAPE.
* ``evaluation`` — chart-ready data for the evaluation page.
    - Classification: confusion matrix, per-class report, ROC and
      precision-recall curves.
    - Regression: predicted-vs-actual points and residuals.
    - Both: permutation feature importance on the original input columns
      (model-agnostic, so it works the same for every algorithm).

Everything returned is JSON-serialisable (NaN/inf become ``None``).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

REGRESSION = "regression"
MAX_CURVE_POINTS = 100
MAX_SCATTER_POINTS = 500
MAX_CURVE_CLASSES = 10
MAX_IMPORTANCE_ROWS = 2000
TOP_FEATURES = 20
RANDOM_STATE = 42


def _clean(value: Any) -> Any:
    """Round floats and turn NaN/inf into None so the result is valid JSON."""
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _thin(xs: np.ndarray, ys: np.ndarray, max_points: int = MAX_CURVE_POINTS) -> tuple[list, list]:
    """Down-sample a curve to at most ``max_points`` points, keeping both ends."""
    if len(xs) > max_points:
        idx = np.unique(np.linspace(0, len(xs) - 1, max_points).astype(int))
        xs, ys = xs[idx], ys[idx]
    return [_clean(x) for x in xs], [_clean(y) for y in ys]


def _predict_proba(model, X: pd.DataFrame) -> np.ndarray | None:
    if not hasattr(model, "predict_proba"):
        return None
    try:
        return model.predict_proba(X)
    except Exception:
        return None


# ── Classification ────────────────────────────────────────────────────

def classification_metrics(y_true, y_pred, proba, n_classes: int) -> dict:
    labels = list(range(n_classes))
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_weighted": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall_weighted": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "roc_auc": None,
        "log_loss": None,
    }
    if proba is not None:
        try:
            if n_classes == 2:
                metrics["roc_auc"] = roc_auc_score(y_true, proba[:, 1])
            else:
                metrics["roc_auc"] = roc_auc_score(
                    y_true, proba, multi_class="ovr", average="weighted", labels=labels
                )
        except ValueError:  # a class missing from the test split
            pass
        try:
            metrics["log_loss"] = log_loss(y_true, proba, labels=labels)
        except ValueError:
            pass
    return {k: _clean(v) for k, v in metrics.items()}


def classification_charts(y_true, y_pred, proba, class_labels: list[str]) -> dict:
    n_classes = len(class_labels)
    labels = list(range(n_classes))
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    per_class = []
    for i, label in enumerate(class_labels):
        tp = cm[i, i]
        support = cm[i, :].sum()
        predicted = cm[:, i].sum()
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class.append({
            "label": label,
            "precision": _clean(precision),
            "recall": _clean(recall),
            "f1": _clean(f1),
            "support": int(support),
        })

    roc_curves, pr_curves = [], []
    if proba is not None:
        # Binary: one curve for the positive class. Multiclass: one-vs-rest per class.
        classes_to_plot = [1] if n_classes == 2 else labels[:MAX_CURVE_CLASSES]
        for cls in classes_to_plot:
            y_bin = (np.asarray(y_true) == cls).astype(int)
            if y_bin.min() == y_bin.max():  # class absent (or only class) in test split
                continue
            scores = proba[:, cls]
            fpr, tpr, _ = roc_curve(y_bin, scores)
            fx, ty = _thin(fpr, tpr)
            roc_curves.append({"label": class_labels[cls], "fpr": fx, "tpr": ty, "auc": _clean(auc(fpr, tpr))})

            precision, recall, _ = precision_recall_curve(y_bin, scores)
            rx, py = _thin(recall[::-1], precision[::-1])
            pr_curves.append({
                "label": class_labels[cls],
                "recall": rx,
                "precision": py,
                "average_precision": _clean(average_precision_score(y_bin, scores)),
                "baseline": _clean(y_bin.mean()),
            })

    return {
        "confusion_matrix": {"labels": class_labels, "matrix": cm.astype(int).tolist()},
        "per_class": per_class,
        "roc_curves": roc_curves,
        "pr_curves": pr_curves,
    }


# ── Regression ────────────────────────────────────────────────────────

def regression_metrics(y_true, y_pred, n_features: int) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_true)
    mse = mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    adjusted = 1 - (1 - r2) * (n - 1) / (n - n_features - 1) if n - n_features - 1 > 0 else None

    nonzero = y_true != 0
    mape = (
        float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero]))) * 100
        if nonzero.any() else None
    )
    metrics = {
        "mae": mean_absolute_error(y_true, y_pred),
        "mse": mse,
        "rmse": math.sqrt(mse),
        "r2": r2,
        "adjusted_r2": adjusted,
        "mape": mape,
    }
    return {k: _clean(v) for k, v in metrics.items()}


def regression_charts(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    idx = np.arange(len(y_true))
    if len(idx) > MAX_SCATTER_POINTS:
        idx = np.random.default_rng(RANDOM_STATE).choice(idx, MAX_SCATTER_POINTS, replace=False)
    actual, predicted = y_true[idx], y_pred[idx]
    return {
        "predicted_vs_actual": {
            "actual": [_clean(v) for v in actual],
            "predicted": [_clean(v) for v in predicted],
        },
        "residuals": [_clean(v) for v in (actual - predicted)],
    }


# ── Feature importance ────────────────────────────────────────────────

def feature_importance(model, X: pd.DataFrame, y, feature_names: list[str]) -> list[dict]:
    """Permutation importance: how much the score drops when a column is shuffled."""
    if len(X) > MAX_IMPORTANCE_ROWS:
        X = X.sample(MAX_IMPORTANCE_ROWS, random_state=RANDOM_STATE)
        y = np.asarray(y)[X.index.to_numpy()] if hasattr(X, "index") else y
    try:
        result = permutation_importance(model, X, y, n_repeats=5, random_state=RANDOM_STATE, n_jobs=1)
    except Exception:
        return []
    items = [
        {"feature": name, "importance": _clean(mean), "std": _clean(std)}
        for name, mean, std in zip(feature_names, result.importances_mean, result.importances_std)
    ]
    items.sort(key=lambda d: d["importance"] or 0, reverse=True)
    return items[:TOP_FEATURES]


# ── Entry point ───────────────────────────────────────────────────────

def evaluate_model(
    model,
    X_test: pd.DataFrame,
    y_test,
    task_type: str,
    class_labels: list[str] | None,
    feature_names: list[str],
) -> tuple[dict, dict]:
    """Return ``(metrics, evaluation)`` for a fitted model on the test split."""
    X_test = X_test.reset_index(drop=True)
    y_test = np.asarray(y_test)
    y_pred = model.predict(X_test)

    if task_type == REGRESSION:
        metrics = regression_metrics(y_test, y_pred, n_features=len(feature_names))
        evaluation = regression_charts(y_test, y_pred)
    else:
        proba = _predict_proba(model, X_test)
        metrics = classification_metrics(y_test, y_pred, proba, len(class_labels or []))
        evaluation = classification_charts(y_test, y_pred, proba, class_labels or [])

    evaluation["feature_importance"] = feature_importance(model, X_test, y_test, feature_names)
    evaluation["test_rows"] = int(len(y_test))
    return metrics, evaluation
