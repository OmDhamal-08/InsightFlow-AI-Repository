"""AutoML engine (Phase 10).

Pure-Python training engine with no web or database code, so it is easy to
unit-test and to explain:

1. ``detect_task_type``     — look at the target column, decide regression /
                               binary / multiclass classification.
2. ``recommend_algorithms`` — pick sensible candidates for the task and data size.
3. ``prepare_data``         — drop unusable columns (IDs, constants, free text),
                               split X / y, label-encode the target.
4. ``build_pipeline``       — one scikit-learn ``Pipeline``:
                               impute → scale / one-hot → model.
5. ``run_automl``           — for every algorithm: cross-validate (optionally
                               tune with ``RandomizedSearchCV``), refit on the
                               training split, evaluate on the held-out test
                               split, save a ``.joblib`` bundle.

Model selection uses the cross-validation score; the test split is only used
for the final, unbiased report (Phase 11, see ``app.ml.evaluator``).

Only scikit-learn is required. XGBoost and LightGBM are used automatically
when they are installed, but they are optional.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from scipy.stats import loguniform, randint, uniform
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.model_selection import (
    KFold,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.ml.evaluator import evaluate_model

logger = logging.getLogger(__name__)

TASK_REGRESSION = "regression"
TASK_BINARY = "binary_classification"
TASK_MULTICLASS = "multiclass_classification"
CLASSIFICATION_TASKS = (TASK_BINARY, TASK_MULTICLASS)

RANDOM_STATE = 42

# Columns with more distinct text values than this are treated as free text / IDs.
MAX_CATEGORIES = 50
# Algorithms flagged ``small_data_only`` are only recommended below this many rows.
SMALL_DATA_ROWS = 5000


class AutoMLError(ValueError):
    """Raised for invalid AutoML input (bad target, unsupported algorithm, ...)."""


# ══════════════════════════════════════════════════════════════════════
# Metrics used for model selection
# ══════════════════════════════════════════════════════════════════════

# metric key -> (sklearn scoring string, human label, higher_is_better)
CLASSIFICATION_METRICS: dict[str, tuple[str, str]] = {
    "f1_weighted": ("f1_weighted", "F1 (weighted)"),
    "accuracy": ("accuracy", "Accuracy"),
    "roc_auc": ("roc_auc_ovr_weighted", "ROC-AUC"),
    "precision_weighted": ("precision_weighted", "Precision (weighted)"),
    "recall_weighted": ("recall_weighted", "Recall (weighted)"),
}
REGRESSION_METRICS: dict[str, tuple[str, str]] = {
    "r2": ("r2", "R²"),
    "rmse": ("neg_root_mean_squared_error", "RMSE"),
    "mae": ("neg_mean_absolute_error", "MAE"),
}
# Error metrics are reported by sklearn as negatives; we flip the sign for display.
LOWER_IS_BETTER = {"rmse", "mae"}


def metrics_for_task(task_type: str) -> dict[str, tuple[str, str]]:
    """Return the selectable optimisation metrics for a task."""
    return REGRESSION_METRICS if task_type == TASK_REGRESSION else CLASSIFICATION_METRICS


def default_metric(task_type: str) -> str:
    """Default optimisation metric: R² for regression, weighted F1 for classification."""
    return "r2" if task_type == TASK_REGRESSION else "f1_weighted"


def _scoring_for(metric: str, task_type: str) -> str:
    scoring = metrics_for_task(task_type)[metric][0]
    if metric == "roc_auc" and task_type == TASK_BINARY:
        return "roc_auc"
    return scoring


# ══════════════════════════════════════════════════════════════════════
# Algorithm registry
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AlgorithmSpec:
    """A trainable algorithm and its tuning search space."""

    key: str
    name: str
    tasks: tuple[str, ...]
    description: str
    factory: Callable[[str], Any]
    param_space: dict[str, Any] = field(default_factory=dict)
    small_data_only: bool = False
    is_baseline: bool = False
    # Search-space prefix when the classifier is wrapped (e.g. calibrated SVM).
    classifier_param_prefix: str = ""
    regressor_param_prefix: str = ""


def _clf_or_reg(classifier: Callable[[], Any], regressor: Callable[[], Any]) -> Callable[[str], Any]:
    return lambda task: regressor() if task == TASK_REGRESSION else classifier()


def _build_registry() -> dict[str, AlgorithmSpec]:
    both = (TASK_REGRESSION, TASK_BINARY, TASK_MULTICLASS)
    clf = CLASSIFICATION_TASKS
    reg = (TASK_REGRESSION,)

    specs = [
        AlgorithmSpec(
            "logistic_regression", "Logistic Regression", clf,
            "Fast linear baseline; coefficients are easy to interpret.",
            lambda _t: LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
            {"C": loguniform(1e-3, 1e2)},
            is_baseline=True,
        ),
        AlgorithmSpec(
            "linear_regression", "Linear Regression", reg,
            "Ordinary least squares baseline.",
            lambda _t: LinearRegression(),
            is_baseline=True,
        ),
        AlgorithmSpec(
            "ridge", "Ridge Regression", reg,
            "Linear model with L2 regularisation; robust to correlated features.",
            lambda _t: Ridge(random_state=RANDOM_STATE),
            {"alpha": loguniform(1e-3, 1e2)},
        ),
        AlgorithmSpec(
            "lasso", "Lasso Regression", reg,
            "Linear model with L1 regularisation; can zero out useless features.",
            lambda _t: Lasso(max_iter=5000, random_state=RANDOM_STATE),
            {"alpha": loguniform(1e-4, 1e1)},
        ),
        AlgorithmSpec(
            "elastic_net", "ElasticNet", reg,
            "Mix of L1 and L2 regularisation.",
            lambda _t: ElasticNet(max_iter=5000, random_state=RANDOM_STATE),
            {"alpha": loguniform(1e-4, 1e1), "l1_ratio": uniform(0.05, 0.9)},
        ),
        AlgorithmSpec(
            "decision_tree", "Decision Tree", both,
            "Single interpretable tree; prone to overfitting.",
            _clf_or_reg(
                lambda: DecisionTreeClassifier(random_state=RANDOM_STATE),
                lambda: DecisionTreeRegressor(random_state=RANDOM_STATE),
            ),
            {"max_depth": randint(2, 20), "min_samples_leaf": randint(1, 20)},
        ),
        AlgorithmSpec(
            "random_forest", "Random Forest", both,
            "Ensemble of trees; strong default with little tuning.",
            _clf_or_reg(
                lambda: RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE),
                lambda: RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE),
            ),
            {"max_depth": [None, 5, 10, 20], "min_samples_leaf": randint(1, 10), "max_features": ["sqrt", 0.5, 1.0]},
        ),
        AlgorithmSpec(
            "extra_trees", "Extra Trees", both,
            "Randomised tree ensemble; fast and low-variance.",
            _clf_or_reg(
                lambda: ExtraTreesClassifier(n_estimators=200, random_state=RANDOM_STATE),
                lambda: ExtraTreesRegressor(n_estimators=200, random_state=RANDOM_STATE),
            ),
            {"max_depth": [None, 5, 10, 20], "min_samples_leaf": randint(1, 10)},
        ),
        AlgorithmSpec(
            "hist_gradient_boosting", "Gradient Boosting (Histogram)", both,
            "scikit-learn's fast gradient boosting; scales to large data.",
            _clf_or_reg(
                lambda: HistGradientBoostingClassifier(random_state=RANDOM_STATE),
                lambda: HistGradientBoostingRegressor(random_state=RANDOM_STATE),
            ),
            {"learning_rate": loguniform(0.01, 0.3), "max_depth": [None, 3, 6, 10], "max_leaf_nodes": randint(15, 63)},
        ),
        AlgorithmSpec(
            "knn", "K-Nearest Neighbours", both,
            "Distance-based; good on small, low-dimensional data.",
            _clf_or_reg(KNeighborsClassifier, KNeighborsRegressor),
            {"n_neighbors": randint(3, 30), "weights": ["uniform", "distance"]},
            small_data_only=True,
        ),
        AlgorithmSpec(
            "svm", "Support Vector Machine", both,
            "Kernel method; accurate on small/medium data, slow on large data.",
            _clf_or_reg(
                # Calibration gives SVC proper probabilities (needed for ROC-AUC / ROC curves).
                lambda: CalibratedClassifierCV(SVC(random_state=RANDOM_STATE), ensemble=False, cv=3),
                # SVR is scale-sensitive on the target too, so standardise y as well.
                lambda: TransformedTargetRegressor(regressor=SVR(), transformer=StandardScaler()),
            ),
            {"C": loguniform(1e-2, 1e2), "gamma": ["scale", "auto"]},
            small_data_only=True,
            classifier_param_prefix="estimator__",
            regressor_param_prefix="regressor__",
        ),
    ]

    # Optional third-party boosting libraries — only if installed.
    try:
        from xgboost import XGBClassifier, XGBRegressor

        specs.append(AlgorithmSpec(
            "xgboost", "XGBoost", both, "Optional: XGBoost gradient boosting (installed).",
            _clf_or_reg(
                lambda: XGBClassifier(n_estimators=300, random_state=RANDOM_STATE, verbosity=0),
                lambda: XGBRegressor(n_estimators=300, random_state=RANDOM_STATE, verbosity=0),
            ),
            {"learning_rate": loguniform(0.01, 0.3), "max_depth": randint(3, 10), "subsample": uniform(0.6, 0.4)},
        ))
    except ImportError:
        pass

    try:
        from lightgbm import LGBMClassifier, LGBMRegressor

        specs.append(AlgorithmSpec(
            "lightgbm", "LightGBM", both, "Optional: LightGBM gradient boosting (installed).",
            _clf_or_reg(
                lambda: LGBMClassifier(n_estimators=300, random_state=RANDOM_STATE, verbose=-1),
                lambda: LGBMRegressor(n_estimators=300, random_state=RANDOM_STATE, verbose=-1),
            ),
            {"learning_rate": loguniform(0.01, 0.3), "num_leaves": randint(15, 127)},
        ))
    except ImportError:
        pass

    return {spec.key: spec for spec in specs}


ALGORITHMS: dict[str, AlgorithmSpec] = _build_registry()


# ══════════════════════════════════════════════════════════════════════
# Task detection & recommendations
# ══════════════════════════════════════════════════════════════════════

def detect_task_type(y: pd.Series) -> str:
    """Infer the ML task from the target column.

    Rules (simple and explainable):
      * non-numeric or boolean target            → classification
      * exactly 2 distinct values                → binary classification
      * integer-valued with ≤ 20 distinct values
        (and < 50% unique)                       → multiclass classification
      * otherwise numeric                        → regression
    """
    y = y.dropna()
    if y.empty:
        raise AutoMLError("Target column has no non-missing values")

    n_unique = y.nunique()
    if n_unique < 2:
        raise AutoMLError("Target column has only one distinct value — nothing to predict")

    if n_unique == 2:
        return TASK_BINARY

    if pd.api.types.is_bool_dtype(y) or not pd.api.types.is_numeric_dtype(y):
        return TASK_MULTICLASS

    is_integer_like = bool(np.all(np.isclose(y.astype(float) % 1, 0)))
    if is_integer_like and n_unique <= 20 and n_unique / len(y) < 0.5:
        return TASK_MULTICLASS

    return TASK_REGRESSION


def available_algorithms(task_type: str) -> list[AlgorithmSpec]:
    """All registered algorithms that support the task."""
    return [spec for spec in ALGORITHMS.values() if task_type in spec.tasks]


def recommend_algorithms(task_type: str, n_rows: int) -> list[dict]:
    """Return every algorithm for the task, flagging the recommended subset.

    Recommended = a linear baseline + tree ensembles + boosting, plus
    distance/kernel methods only when the data is small enough for them.
    """
    preferred = {"random_forest", "hist_gradient_boosting", "extra_trees", "xgboost", "lightgbm"}
    result = []
    for spec in available_algorithms(task_type):
        if spec.small_data_only and n_rows > SMALL_DATA_ROWS:
            recommended, reason = False, f"Slow above {SMALL_DATA_ROWS:,} rows"
        elif spec.is_baseline:
            recommended, reason = True, "Simple baseline to compare against"
        elif spec.key in preferred:
            recommended, reason = True, "Strong general-purpose performer"
        elif spec.small_data_only:
            recommended, reason = True, "Dataset is small enough for this method"
        else:
            recommended, reason = False, "Optional extra candidate"
        result.append({
            "key": spec.key,
            "name": spec.name,
            "description": spec.description,
            "recommended": recommended,
            "reason": reason,
            "tunable": bool(spec.param_space),
        })
    return result


def validate_choices(task_type: str, algorithms: list[str] | None, metric: str | None) -> None:
    """Raise ``AutoMLError`` if the chosen algorithms/metric don't fit the task."""
    task_label = task_type.replace("_", " ")
    if metric is not None and metric not in metrics_for_task(task_type):
        raise AutoMLError(f"Metric '{metric}' is not valid for {task_label}")
    if algorithms:
        unknown = [a for a in algorithms if a not in ALGORITHMS]
        if unknown:
            raise AutoMLError(f"Unknown algorithm(s): {', '.join(unknown)}")
        unsupported = [a for a in algorithms if task_type not in ALGORITHMS[a].tasks]
        if unsupported:
            raise AutoMLError(f"Algorithm(s) not suitable for {task_label}: {', '.join(unsupported)}")


# ══════════════════════════════════════════════════════════════════════
# Data preparation
# ══════════════════════════════════════════════════════════════════════

_ID_NAME = re.compile(r"(^|[_\s-])id$|^id([_\s-]|$)|_id$|^(index|row|row_?num(ber)?)$")


def looks_like_id(name: str, non_null: pd.Series) -> bool:
    """Integer column that is ~all unique and either consecutive or named like an ID.

    Duplicated rows make a real ID column slightly non-unique, so we allow 5% slack.
    """
    if not pd.api.types.is_integer_dtype(non_null) or len(non_null) <= 20:
        return False
    n_unique = non_null.nunique()
    if n_unique / len(non_null) < 0.95:
        return False
    consecutive = (non_null.max() - non_null.min() + 1) <= n_unique * 1.05
    return consecutive or bool(_ID_NAME.search(name.strip().lower()))


def _looks_like_dates(non_null: pd.Series) -> bool:
    """True if most text values parse as dates (e.g. '2024-01-31')."""
    sample = non_null.astype(str).head(200)
    if pd.to_numeric(sample, errors="coerce").notna().mean() > 0.5:
        return False  # numbers stored as text are not dates
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return parsed.notna().mean() >= 0.9


def _as_category_strings(series: pd.Series) -> pd.Series:
    """Cast to plain Python strings (object dtype) while keeping missing values as NaN.

    One-hot encoding needs a single value type per column; mixed ints/strings break it.
    """
    as_str = series.map(lambda v: v if pd.isna(v) else str(v))
    return as_str.astype(object)


@dataclass
class PreparedData:
    """Model-ready inputs plus a record of what was dropped and why."""

    X: pd.DataFrame
    y: np.ndarray
    task_type: str
    numeric_features: list[str]
    categorical_features: list[str]
    dropped_columns: list[dict]
    class_labels: list[str] | None
    rows_dropped_missing_target: int
    rows_sampled_from: int | None


def prepare_data(
    df: pd.DataFrame,
    target_column: str,
    task_type: str | None = None,
    max_rows: int | None = None,
) -> PreparedData:
    """Split a raw DataFrame into features/target and choose usable columns."""
    if target_column not in df.columns:
        raise AutoMLError(f"Target column '{target_column}' not found in dataset")

    df = df.copy()
    n_before = len(df)
    df = df[df[target_column].notna()]
    rows_dropped = n_before - len(df)
    if len(df) < 20:
        raise AutoMLError("Need at least 20 rows with a non-missing target to train models")

    task_type = task_type or detect_task_type(df[target_column])

    # Down-sample very large datasets so training stays interactive.
    sampled_from = None
    if max_rows and len(df) > max_rows:
        sampled_from = len(df)
        stratify = df[target_column] if task_type in CLASSIFICATION_TASKS else None
        try:
            df, _ = train_test_split(df, train_size=max_rows, stratify=stratify, random_state=RANDOM_STATE)
        except ValueError:
            df = df.sample(n=max_rows, random_state=RANDOM_STATE)

    X = df.drop(columns=[target_column])
    dropped: list[dict] = []
    numeric, categorical = [], []

    for col in X.columns:
        series = X[col]
        non_null = series.dropna()
        if non_null.empty:
            dropped.append({"column": col, "reason": "All values are missing"})
            continue
        if non_null.nunique() <= 1:
            dropped.append({"column": col, "reason": "Constant column (single value)"})
            continue
        if pd.api.types.is_bool_dtype(series):
            X[col] = series.astype(float)
            numeric.append(col)
        elif pd.api.types.is_numeric_dtype(series):
            if looks_like_id(col, non_null):
                dropped.append({"column": col, "reason": "Looks like a row ID (almost every value is a unique integer)"})
                continue
            numeric.append(col)
        elif pd.api.types.is_datetime64_any_dtype(series) or _looks_like_dates(non_null):
            dropped.append({
                "column": col,
                "reason": "Date column — use Feature Engineering → Datetime Split to turn it into year/month/day features",
            })
            continue
        else:
            n_unique = non_null.nunique()
            if n_unique > MAX_CATEGORIES:
                dropped.append({
                    "column": col,
                    "reason": f"High-cardinality text ({n_unique} distinct values) — likely an ID or free text",
                })
                continue
            X[col] = _as_category_strings(series)
            categorical.append(col)

    if not numeric and not categorical:
        raise AutoMLError("No usable feature columns remain after dropping IDs, constants and free text")

    X = X[numeric + categorical]

    class_labels = None
    if task_type in CLASSIFICATION_TASKS:
        encoder = LabelEncoder()
        y = encoder.fit_transform(df[target_column].astype(str))
        class_labels = [str(c) for c in encoder.classes_]
        counts = np.bincount(y)
        if counts.min() < 2:
            raise AutoMLError("Every target class needs at least 2 rows for a stratified split")
    else:
        y = pd.to_numeric(df[target_column], errors="coerce").to_numpy(dtype=float)
        if np.isnan(y).any():
            raise AutoMLError("Regression target must be numeric")

    return PreparedData(
        X=X.reset_index(drop=True),
        y=np.asarray(y),
        task_type=task_type,
        numeric_features=numeric,
        categorical_features=categorical,
        dropped_columns=dropped,
        class_labels=class_labels,
        rows_dropped_missing_target=rows_dropped,
        rows_sampled_from=sampled_from,
    )


def build_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    """Impute + scale numeric columns; impute + one-hot encode categorical columns."""
    transformers = []
    if numeric:
        transformers.append((
            "num",
            Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]),
            numeric,
        ))
    if categorical:
        transformers.append((
            "cat",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=20)),
            ]),
            categorical,
        ))
    return ColumnTransformer(transformers, remainder="drop")


def build_pipeline(algorithm: str, task_type: str, numeric: list[str], categorical: list[str]) -> Pipeline:
    """Bundle preprocessing and the estimator so the saved model accepts raw rows."""
    spec = ALGORITHMS[algorithm]
    return Pipeline([
        ("preprocess", build_preprocessor(numeric, categorical)),
        ("model", spec.factory(task_type)),
    ])


# ══════════════════════════════════════════════════════════════════════
# Training
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AutoMLConfig:
    """User-facing knobs for an AutoML run."""

    target_column: str
    algorithms: list[str] | None = None   # None → recommended set
    task_type: str | None = None          # None → auto-detect
    optimize_metric: str | None = None    # None → task default
    test_size: float = 0.2
    cv_folds: int = 5
    tune_hyperparameters: bool = False
    tuning_iterations: int = 10
    max_rows: int | None = 50000
    n_jobs: int = 1


def _json_safe_params(params: dict) -> dict:
    """Convert numpy scalars etc. so hyperparameters can be stored as JSON."""
    safe = {}
    for key, value in params.items():
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float):
            value = round(value, 6)
        if not isinstance(value, (str, int, float, bool, type(None))):
            value = str(value)
        safe[key.replace("model__", "").replace("estimator__", "").replace("regressor__", "")] = value
    return safe


def _cv_splitter(task_type: str, folds: int, y: np.ndarray):
    if task_type in CLASSIFICATION_TASKS:
        smallest_class = int(np.bincount(y).min())
        folds = max(2, min(folds, smallest_class))
        return StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    return KFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)


def run_automl(df: pd.DataFrame, config: AutoMLConfig, artifact_dir: str | Path) -> dict:
    """Train, compare and persist every requested algorithm.

    Returns a plain dict (JSON-friendly) describing the run and each model. A
    failure in one algorithm is recorded on that model and does not stop the
    others.
    """
    started = time.perf_counter()
    data = prepare_data(df, config.target_column, config.task_type, config.max_rows)
    task = data.task_type

    validate_choices(task, config.algorithms, config.optimize_metric)
    metric = config.optimize_metric or default_metric(task)
    if metric == "roc_auc" and task == TASK_MULTICLASS:
        metric_label = "ROC-AUC (one-vs-rest, weighted)"
    else:
        metric_label = metrics_for_task(task)[metric][1]
    scoring = _scoring_for(metric, task)

    algorithms = config.algorithms or [a["key"] for a in recommend_algorithms(task, len(data.X)) if a["recommended"]]

    stratify = data.y if task in CLASSIFICATION_TASKS else None
    X_train, X_test, y_train, y_test = train_test_split(
        data.X, data.y, test_size=config.test_size, stratify=stratify, random_state=RANDOM_STATE
    )
    cv = _cv_splitter(task, config.cv_folds, y_train)

    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    models: list[dict] = []
    for key in algorithms:
        spec = ALGORITHMS[key]
        model_id = uuid.uuid4()
        t0 = time.perf_counter()
        entry: dict[str, Any] = {"id": model_id, "algorithm": key, "display_name": spec.name}
        try:
            pipeline = build_pipeline(key, task, data.numeric_features, data.categorical_features)

            if config.tune_hyperparameters and spec.param_space:
                prefix = "model__" + (
                    spec.classifier_param_prefix if task in CLASSIFICATION_TASKS else spec.regressor_param_prefix
                )
                search = RandomizedSearchCV(
                    pipeline,
                    {f"{prefix}{k}": v for k, v in spec.param_space.items()},
                    n_iter=config.tuning_iterations,
                    scoring=scoring,
                    cv=cv,
                    random_state=RANDOM_STATE,
                    n_jobs=config.n_jobs,
                    error_score="raise",
                )
                search.fit(X_train, y_train)
                fitted = search.best_estimator_
                best_idx = search.best_index_
                cv_mean = float(search.cv_results_["mean_test_score"][best_idx])
                cv_std = float(search.cv_results_["std_test_score"][best_idx])
                params = _json_safe_params(search.best_params_)
            else:
                scores = cross_val_score(pipeline, X_train, y_train, scoring=scoring, cv=cv, n_jobs=config.n_jobs)
                cv_mean, cv_std = float(np.mean(scores)), float(np.std(scores))
                fitted = pipeline.fit(X_train, y_train)
                params = {}

            if metric in LOWER_IS_BETTER:  # sklearn returns negative errors
                cv_mean = -cv_mean

            metrics, evaluation = evaluate_model(
                fitted, X_test, y_test, task, data.class_labels,
                feature_names=list(data.X.columns),
            )

            artifact_path = artifact_dir / f"{model_id}.joblib"
            joblib.dump({
                "pipeline": fitted,
                "task_type": task,
                "target_column": config.target_column,
                "feature_columns": list(data.X.columns),
                "numeric_features": data.numeric_features,
                "categorical_features": data.categorical_features,
                "class_labels": data.class_labels,
                "algorithm": key,
            }, artifact_path)

            entry.update({
                "status": "completed",
                "hyperparameters": params,
                "cv_score": round(cv_mean, 6),
                "cv_std": round(cv_std, 6),
                "test_score": metrics.get(metric),
                "metrics": metrics,
                "evaluation": evaluation,
                "artifact_path": str(artifact_path),
                "error_message": None,
            })
        except Exception as exc:  # one bad algorithm must not sink the run
            logger.warning("AutoML: %s failed: %s", key, exc)
            entry.update({
                "status": "failed",
                "hyperparameters": {},
                "cv_score": None,
                "cv_std": None,
                "test_score": None,
                "metrics": {},
                "evaluation": {},
                "artifact_path": None,
                "error_message": str(exc)[:500],
            })
        entry["training_time_seconds"] = round(time.perf_counter() - t0, 3)
        models.append(entry)

    # Leaderboard: rank successful models by CV score (higher is better unless error metric).
    succeeded = [m for m in models if m["status"] == "completed"]
    reverse = metric not in LOWER_IS_BETTER
    succeeded.sort(key=lambda m: m["cv_score"], reverse=reverse)
    for rank, model in enumerate(succeeded, start=1):
        model["rank"] = rank
        model["is_best"] = rank == 1
    for model in models:
        model.setdefault("rank", None)
        model.setdefault("is_best", False)

    class_distribution = None
    if data.class_labels:
        counts = np.bincount(data.y, minlength=len(data.class_labels))
        class_distribution = {label: int(c) for label, c in zip(data.class_labels, counts)}

    return {
        "task_type": task,
        "optimize_metric": metric,
        "metric_label": metric_label,
        "lower_is_better": metric in LOWER_IS_BETTER,
        "algorithms": algorithms,
        "models": models,
        "best_model_id": succeeded[0]["id"] if succeeded else None,
        "summary": {
            "rows_used": int(len(data.X)),
            "rows_sampled_from": data.rows_sampled_from,
            "rows_dropped_missing_target": data.rows_dropped_missing_target,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "cv_folds": cv.get_n_splits(),
            "feature_columns": list(data.X.columns),
            "numeric_features": data.numeric_features,
            "categorical_features": data.categorical_features,
            "dropped_columns": data.dropped_columns,
            "class_labels": data.class_labels,
            "class_distribution": class_distribution,
        },
        "training_time_seconds": round(time.perf_counter() - started, 3),
    }


# ══════════════════════════════════════════════════════════════════════
# Inference
# ══════════════════════════════════════════════════════════════════════

def load_model_bundle(path: str | Path) -> dict:
    """Load a saved ``.joblib`` bundle (pipeline + metadata)."""
    return joblib.load(path)


def predict_with_bundle(bundle: dict, rows: list[dict]) -> list[dict]:
    """Predict for raw input rows using a saved bundle.

    Missing feature columns are filled with NaN (the pipeline imputes them);
    extra keys are ignored.
    """
    columns = bundle["feature_columns"]
    frame = pd.DataFrame([{col: row.get(col) for col in columns} for row in rows], columns=columns)
    # Apply the same typing as training: numbers for numeric columns, strings for categoricals.
    for col in bundle.get("numeric_features", []):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    for col in bundle.get("categorical_features", []):
        frame[col] = _as_category_strings(frame[col].replace("", np.nan))

    pipeline = bundle["pipeline"]
    raw = pipeline.predict(frame)
    labels = bundle.get("class_labels")

    results = []
    proba = None
    if labels and hasattr(pipeline, "predict_proba"):
        try:
            proba = pipeline.predict_proba(frame)
        except Exception:  # some estimators expose predict_proba but cannot use it
            proba = None

    for i, value in enumerate(raw):
        if labels:
            item: dict[str, Any] = {"prediction": labels[int(value)]}
            if proba is not None:
                item["probabilities"] = {labels[j]: round(float(p), 4) for j, p in enumerate(proba[i])}
        else:
            item = {"prediction": round(float(value), 6)}
        results.append(item)
    return results
