"""Unit tests for the AutoML engine and evaluator.

These call ``app.ml`` directly — no HTTP or database — so they are fast and
document how the engine behaves.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml import automl
from app.ml.automl import AutoMLConfig, AutoMLError, detect_task_type, prepare_data, run_automl


def _frame(n: int = 160, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "row_id": np.arange(1, n + 1),
        "age": rng.integers(18, 70, n).astype(float),
        "income": rng.normal(50000, 15000, n),
        "city": rng.choice(["Pune", "Mumbai", "Delhi"], n),
        "comment": [f"unique note {i}" for i in range(n)],
        "constant": 7,
    })
    df.loc[rng.choice(n, 10, replace=False), "income"] = np.nan
    signal = 0.05 * df["age"] + df["income"].fillna(50000) / 20000 + (df["city"] == "Pune") * 1.5
    df["churn"] = np.where(signal + rng.normal(0, 0.4, n) > signal.median(), "yes", "no")
    df["segment"] = pd.cut(signal, 3, labels=["low", "mid", "high"]).astype(str)
    df["spend"] = signal * 100 + rng.normal(0, 5, n)
    return df


# Task detection

@pytest.mark.parametrize(
    "values, expected",
    [
        (["yes", "no", "yes", "no"], automl.TASK_BINARY),
        ([0, 1, 1, 0, 1], automl.TASK_BINARY),
        (["a", "b", "c", "a", "b", "c"], automl.TASK_MULTICLASS),
        ([1, 2, 3] * 20, automl.TASK_MULTICLASS),
        (list(np.linspace(0, 100, 60)), automl.TASK_REGRESSION),
    ],
)
def test_detect_task_type(values, expected):
    assert detect_task_type(pd.Series(values)) == expected


def test_detect_task_type_rejects_single_value():
    with pytest.raises(AutoMLError):
        detect_task_type(pd.Series([1, 1, 1, 1]))


# Data preparation

def test_prepare_data_drops_unusable_columns_with_reasons():
    data = prepare_data(_frame(), "churn")
    dropped = {d["column"] for d in data.dropped_columns}
    assert {"row_id", "comment", "constant"} <= dropped
    assert "age" in data.numeric_features and "city" in data.categorical_features
    assert data.class_labels == ["no", "yes"]


def test_prepare_data_requires_enough_rows():
    with pytest.raises(AutoMLError):
        prepare_data(_frame(n=10), "churn")


def test_recommendations_skip_slow_models_on_large_data():
    small = {a["key"]: a["recommended"] for a in automl.recommend_algorithms(automl.TASK_BINARY, 500)}
    large = {a["key"]: a["recommended"] for a in automl.recommend_algorithms(automl.TASK_BINARY, 100_000)}
    assert small["svm"] is True and large["svm"] is False
    assert large["random_forest"] is True and large["logistic_regression"] is True


# End-to-end runs

def test_binary_classification_run(tmp_path):
    df = _frame().drop(columns=["segment", "spend"])
    result = run_automl(
        df,
        AutoMLConfig(target_column="churn", algorithms=["logistic_regression", "random_forest"], cv_folds=3),
        tmp_path,
    )
    assert result["task_type"] == automl.TASK_BINARY
    assert result["optimize_metric"] == "f1_weighted"
    models = result["models"]
    assert all(m["status"] == "completed" for m in models)
    assert sorted(m["rank"] for m in models) == [1, 2]
    assert sum(m["is_best"] for m in models) == 1

    best = next(m for m in models if m["is_best"])
    assert 0 <= best["metrics"]["accuracy"] <= 1
    assert best["metrics"]["roc_auc"] is not None
    ev = best["evaluation"]
    assert ev["confusion_matrix"]["labels"] == ["no", "yes"]
    assert sum(map(sum, ev["confusion_matrix"]["matrix"])) == result["summary"]["test_rows"]
    assert ev["roc_curves"] and ev["pr_curves"]
    assert {f["feature"] for f in ev["feature_importance"]} <= set(result["summary"]["feature_columns"])

    bundle = automl.load_model_bundle(best["artifact_path"])
    preds = automl.predict_with_bundle(bundle, [{"age": "40", "income": 90000, "city": "Pune"}, {}])
    assert preds[0]["prediction"] in {"no", "yes"}
    assert set(preds[0]["probabilities"]) == {"no", "yes"}


def test_multiclass_with_tuning(tmp_path):
    df = _frame().drop(columns=["churn", "spend"])
    result = run_automl(
        df,
        AutoMLConfig(
            target_column="segment",
            algorithms=["decision_tree", "svm"],
            tune_hyperparameters=True,
            tuning_iterations=3,
            cv_folds=3,
            optimize_metric="accuracy",
        ),
        tmp_path,
    )
    assert result["task_type"] == automl.TASK_MULTICLASS
    assert all(m["status"] == "completed" for m in result["models"])
    tuned = next(m for m in result["models"] if m["algorithm"] == "svm")
    assert "C" in tuned["hyperparameters"]
    assert len(tuned["evaluation"]["confusion_matrix"]["labels"]) == 3


def test_regression_ranks_error_metric_ascending(tmp_path):
    df = _frame().drop(columns=["churn", "segment"])
    result = run_automl(
        df,
        AutoMLConfig(target_column="spend", algorithms=["ridge", "decision_tree"], optimize_metric="rmse", cv_folds=3),
        tmp_path,
    )
    assert result["task_type"] == automl.TASK_REGRESSION
    assert result["lower_is_better"] is True
    ranked = sorted(result["models"], key=lambda m: m["rank"])
    assert ranked[0]["cv_score"] <= ranked[1]["cv_score"]  # smaller RMSE ranks first
    metrics = ranked[0]["metrics"]
    assert {"mae", "mse", "rmse", "r2", "adjusted_r2"} <= set(metrics)
    ev = ranked[0]["evaluation"]
    assert len(ev["predicted_vs_actual"]["actual"]) == len(ev["residuals"])


def test_rejects_algorithm_for_wrong_task(tmp_path):
    with pytest.raises(AutoMLError):
        run_automl(_frame(), AutoMLConfig(target_column="spend", algorithms=["logistic_regression"]), tmp_path)


def test_one_failing_algorithm_does_not_stop_the_run(tmp_path, monkeypatch):
    broken = automl.AlgorithmSpec(
        "broken", "Broken", automl.CLASSIFICATION_TASKS, "always fails",
        lambda _t: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setitem(automl.ALGORITHMS, "broken", broken)
    df = _frame().drop(columns=["segment", "spend"])
    result = run_automl(
        df, AutoMLConfig(target_column="churn", algorithms=["broken", "logistic_regression"], cv_folds=3), tmp_path
    )
    status = {m["algorithm"]: m["status"] for m in result["models"]}
    assert status == {"broken": "failed", "logistic_regression": "completed"}
    assert result["best_model_id"] is not None
