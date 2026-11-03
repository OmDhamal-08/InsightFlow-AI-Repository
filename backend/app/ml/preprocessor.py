"""ML dataset preprocessing engine.

Sequentially applies data transformations (imputations, outlier capping, scaling,
skewness reductions, binarizations, binning, encoders, feature extractions) on
a column-by-column basis, compiling fit parameters for model inference.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401  (activates IterativeImputer)
from sklearn.impute import IterativeImputer, KNNImputer
from sklearn.preprocessing import KBinsDiscretizer, LabelEncoder, MinMaxScaler, PowerTransformer, RobustScaler, StandardScaler

from app.ml.json_utils import to_json_value

logger = logging.getLogger(__name__)

# Rows used to fit KNN / MICE imputers (keeps imputation fast on large files).
IMPUTER_FIT_ROWS = 5000

DATASET_ACTIONS = {"drop_duplicates"}
RESAMPLE_ACTIONS = {"resample_oversample", "resample_undersample"}
NUMERIC_ACTIONS = {
    "impute_mean", "impute_median", "impute_end_of_dist", "impute_knn", "impute_iterative",
    "outliers_cap", "outliers_drop", "outliers_impute_median", "outliers_impute_mean", "outliers_set_nan",
    "discretize_equal_width", "discretize_equal_frequency", "discretize_kmeans", "binarize",
    "scale_standard", "scale_minmax", "scale_robust",
    "apply_log_transform", "apply_sqrt_transform", "apply_reciprocal_transform",
    "apply_boxcox_transform", "apply_yeojohnson_transform",
}
ANY_COLUMN_ACTIONS = {
    "impute_cca", "impute_mode", "impute_constant", "impute_random", "handle_datetime",
    "encode_onehot", "encode_label", "drop_column", "drop_correlated_column",
}
KNOWN_ACTIONS = DATASET_ACTIONS | RESAMPLE_ACTIONS | NUMERIC_ACTIONS | ANY_COLUMN_ACTIONS


class PreprocessingError(ValueError):
    """A preprocessing step is invalid or failed; the message is safe to show to users."""


class DatasetPreprocessor:
    """Applies structured transformations sequentially to clean and prepare data for ML."""

    @classmethod
    def preview(cls, df: pd.DataFrame, steps: list[dict]) -> dict:
        """Apply steps to a copy of the dataframe and return a before/after preview.

        Returns sample rows and descriptive statistics before and after.
        """
        df_before = df.copy()
        
        # Calculate summary statistics before
        before_summary = cls._compute_summary_stats(df_before)
        before_rows_raw = df_before.head(5).to_dict(orient="records")
        before_rows = [{k: to_json_value(v) for k, v in row.items()} for row in before_rows_raw]

        # Apply transformations
        df_after, _ = cls.apply(df.copy(), steps)

        # Calculate summary statistics after
        after_summary = cls._compute_summary_stats(df_after)
        after_rows_raw = df_after.head(5).to_dict(orient="records")
        after_rows = [{k: to_json_value(v) for k, v in row.items()} for row in after_rows_raw]

        return {
            "before": {
                "shape": [len(df_before), len(df_before.columns)],
                "columns": list(df_before.columns),
                "rows": before_rows,
                "summary": before_summary,
            },
            "after": {
                "shape": [len(df_after), len(df_after.columns)],
                "columns": list(df_after.columns),
                "rows": after_rows,
                "summary": after_summary,
            }
        }

    @classmethod
    def apply(cls, df: pd.DataFrame, steps: list[dict]) -> tuple[pd.DataFrame, dict]:
        """Apply sequential preprocessing transformations on the DataFrame.

        Args:
            df: The Pandas DataFrame to preprocess.
            steps: List of dicts specifying column actions.

        Returns:
            The processed DataFrame and a config dictionary containing fitted parameters.
        """
        df = df.copy()  # never modify the caller's DataFrame
        config = {}

        for idx, step in enumerate(steps):
            action = step.get("action")
            column = step.get("column")
            params = step.get("params") or {}
            label = f"Step {idx + 1} ({action}" + (f" on '{column}')" if column else ")")

            if action not in KNOWN_ACTIONS:
                raise PreprocessingError(f"{label}: unknown preprocessing action")

            # Dataset-level action
            if action == "drop_duplicates":
                before = len(df)
                df = df.drop_duplicates().reset_index(drop=True)
                config[f"step_{idx}_drop_duplicates"] = {"rows_removed": before - len(df), "rows_after": len(df)}
                continue

            if not column:
                raise PreprocessingError(f"{label}: a column is required")
            if column not in df.columns:
                raise PreprocessingError(
                    f"{label}: column not found (it may have been dropped or encoded by an earlier step)"
                )
            if action in NUMERIC_ACTIONS and (
                not pd.api.types.is_numeric_dtype(df[column]) or pd.api.types.is_bool_dtype(df[column])
            ):
                raise PreprocessingError(
                    f"{label}: needs a numeric column, but '{column}' contains text. Encode it or pick another action."
                )

            try:
                df, step_config = cls._apply_column_step(df, column, action, params)
            except PreprocessingError:
                raise
            except Exception as exc:
                logger.warning("Preprocessing %s failed: %s", label, exc)
                raise PreprocessingError(f"{label} failed: {exc}") from exc
            config[f"step_{idx}_{column}_{action}"] = step_config

        return df, config

    @classmethod
    def _apply_column_step(cls, df: pd.DataFrame, col: str, action: str, params: dict) -> tuple[pd.DataFrame, dict]:
        """Execute a single column-level transformation step."""
        step_config = {}
        series = df[col]

        # 1. Imputations
        if action == "impute_cca":
            df = df.dropna(subset=[col]).reset_index(drop=True)
            step_config["dropped_nulls"] = True

        elif action == "impute_mean":
            mean_val = float(series.mean()) if not series.dropna().empty else 0.0
            df[col] = series.fillna(mean_val)
            step_config["fill_value"] = mean_val

        elif action == "impute_median":
            median_val = float(series.median()) if not series.dropna().empty else 0.0
            df[col] = series.fillna(median_val)
            step_config["fill_value"] = median_val

        elif action == "impute_mode":
            mode_series = series.mode()
            mode_val = to_json_value(mode_series.iloc[0]) if not mode_series.empty else "missing"
            df[col] = series.fillna(mode_val)
            step_config["fill_value"] = mode_val

        elif action == "impute_constant":
            val = params.get("value")
            if val is None:
                val = 0 if pd.api.types.is_numeric_dtype(series) else "missing"
            df[col] = series.fillna(val)
            step_config["fill_value"] = val

        elif action == "impute_random":
            non_null = series.dropna()
            if not non_null.empty:
                null_mask = series.isna()
                rng = np.random.default_rng(42)
                filled = series.astype(object).copy()
                filled[null_mask] = rng.choice(non_null.to_numpy(dtype=object), size=int(null_mask.sum()))
                df[col] = pd.Series(filled, index=series.index).infer_objects()
                step_config["imputed_random_count"] = int(null_mask.sum())

        elif action == "impute_end_of_dist":
            # Impute at mean + 3*std
            clean = series.dropna()
            if not clean.empty:
                fill_val = float(clean.mean() + 3 * clean.std())
                df[col] = series.fillna(fill_val)
                step_config["fill_value"] = fill_val

        elif action in ("impute_knn", "impute_iterative"):
            # Use the other numeric columns as predictors, so the imputed value
            # reflects similar rows (KNN) or a regression chain (MICE).
            missing = series.isna()
            if missing.any() and not series.dropna().empty:
                numeric_cols = [
                    c for c in df.columns
                    if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
                ]
                frame = df[numeric_cols].astype(float)
                if action == "impute_knn":
                    n_neighbors = int(params.get("n_neighbors", 5))
                    imputer = KNNImputer(n_neighbors=n_neighbors, keep_empty_features=True)
                    step_config["n_neighbors"] = n_neighbors
                else:
                    imputer = IterativeImputer(random_state=42, max_iter=10, keep_empty_features=True)
                    step_config["method"] = "MICE (IterativeImputer)"
                fit_rows = frame.sample(min(len(frame), IMPUTER_FIT_ROWS), random_state=42)
                imputer.fit(fit_rows)
                col_pos = numeric_cols.index(col)
                filled = series.astype(float).copy()
                filled[missing] = imputer.transform(frame[missing])[:, col_pos]
                df[col] = filled
                step_config["imputed_count"] = int(missing.sum())
                step_config["predictor_columns"] = [c for c in numeric_cols if c != col]

        # 2. Outlier Handlings
        elif action == "outliers_cap":
            clean = series.dropna()
            if not clean.empty:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                df[col] = series.clip(lower, upper)
                step_config["bounds"] = [float(lower), float(upper)]

        elif action == "outliers_drop":
            clean = series.dropna()
            if not clean.empty:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                df = df[(df[col] >= lower) & (df[col] <= upper)].reset_index(drop=True)
                step_config["bounds"] = [float(lower), float(upper)]

        elif action == "outliers_impute_median":
            clean = series.dropna()
            if not clean.empty:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                median_val = float(clean.median())
                df[col] = series.apply(lambda x: median_val if (x < lower or x > upper) else x)
                step_config["fill_value"] = median_val

        elif action == "outliers_impute_mean":
            clean = series.dropna()
            if not clean.empty:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                mean_val = float(clean.mean())
                df[col] = series.apply(lambda x: mean_val if (x < lower or x > upper) else x)
                step_config["fill_value"] = mean_val

        elif action == "outliers_set_nan":
            clean = series.dropna()
            if not clean.empty:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                df[col] = series.apply(lambda x: np.nan if (x < lower or x > upper) else x)
                step_config["set_nan_count"] = int(((series < lower) | (series > upper)).sum())

        # 3. Discretizations
        elif action == "discretize_equal_width":
            n_bins = int(params.get("n_bins", 5))
            df[col] = pd.cut(df[col], bins=n_bins, labels=False)
            step_config["n_bins"] = n_bins

        elif action == "discretize_equal_frequency":
            n_bins = int(params.get("n_bins", 5))
            df[col] = pd.qcut(df[col], q=n_bins, labels=False, duplicates="drop")
            step_config["n_bins"] = n_bins

        elif action == "discretize_kmeans":
            n_bins = int(params.get("n_bins", 5))
            clean_idx = series.dropna().index
            if len(clean_idx) > n_bins:
                discretizer = KBinsDiscretizer(n_bins=n_bins, encode="ordinal", strategy="kmeans")
                binned = discretizer.fit_transform(df.loc[clean_idx, [col]].values)
                result = pd.Series(np.nan, index=df.index, dtype=float)
                result[clean_idx] = binned.ravel()
                df[col] = result
                step_config["n_bins"] = n_bins

        # 4. Binarization
        elif action == "binarize":
            threshold = float(params.get("threshold", 0.0))
            df[col] = (df[col] > threshold).astype(int)
            step_config["threshold"] = threshold

        # 5. Datetime handling
        elif action == "handle_datetime":
            try:
                dt_series = pd.to_datetime(df[col], errors="coerce")
                selected_feats = params.get("features", ["year", "month", "day"])
                
                # Extract requested features
                if "year" in selected_feats:
                    df[f"{col}_year"] = dt_series.dt.year.fillna(-1).astype(int)
                if "month" in selected_feats:
                    df[f"{col}_month"] = dt_series.dt.month.fillna(-1).astype(int)
                if "day" in selected_feats:
                    df[f"{col}_day"] = dt_series.dt.day.fillna(-1).astype(int)
                if "day_of_week" in selected_feats:
                    df[f"{col}_dayofweek"] = dt_series.dt.day_of_week.fillna(-1).astype(int)
                if "hour" in selected_feats:
                    df[f"{col}_hour"] = dt_series.dt.hour.fillna(-1).astype(int)

                # Always drop original column to prevent model errors
                df = df.drop(columns=[col])
                step_config["extracted"] = selected_feats
            except Exception as e:
                logger.error("Failed to parse datetime features for %s: %s", col, e)

        # 6. Numerical Scalings
        elif action == "scale_standard":
            scaler = StandardScaler()
            reshaped = df[[col]].fillna(0.0).values
            df[col] = scaler.fit_transform(reshaped).ravel()
            step_config["mean"] = float(scaler.mean_[0])
            step_config["scale"] = float(scaler.scale_[0])

        elif action == "scale_minmax":
            scaler = MinMaxScaler()
            reshaped = df[[col]].fillna(0.0).values
            df[col] = scaler.fit_transform(reshaped).ravel()
            step_config["min"] = float(scaler.min_[0])
            step_config["scale"] = float(scaler.scale_[0])

        elif action == "scale_robust":
            scaler = RobustScaler()
            reshaped = df[[col]].fillna(0.0).values
            df[col] = scaler.fit_transform(reshaped).ravel()
            step_config["center"] = float(scaler.center_[0])
            step_config["scale"] = float(scaler.scale_[0])

        # 7. Skewness Transformations
        elif action == "apply_log_transform":
            # y = log(x + 1)
            # Clip negative values to zero to prevent NaN issues
            df[col] = np.log1p(df[col].clip(lower=0))
            step_config["applied"] = "log1p"

        elif action == "apply_sqrt_transform":
            df[col] = np.sqrt(df[col].clip(lower=0))
            step_config["applied"] = "sqrt"

        elif action == "apply_reciprocal_transform":
            # y = 1 / (x + 1e-5)
            df[col] = 1.0 / (df[col] + 1e-5)
            step_config["applied"] = "reciprocal"

        elif action == "apply_boxcox_transform":
            try:
                # Add positive shift if values contain <= 0
                shift = 0.0
                min_val = series.min()
                if min_val <= 0:
                    shift = float(abs(min_val) + 1.0)
                pt = PowerTransformer(method="box-cox")
                shifted = (df[[col]] + shift).values
                df[col] = pt.fit_transform(shifted).ravel()
                step_config["lambdas"] = float(pt.lambdas_[0])
                step_config["shift"] = shift
            except Exception:
                # Fallback to Yeo-Johnson
                pt = PowerTransformer(method="yeo-johnson")
                df[col] = pt.fit_transform(df[[col]].values).ravel()
                step_config["lambdas"] = float(pt.lambdas_[0])
                step_config["fallback_yeo_johnson"] = True

        elif action == "apply_yeojohnson_transform":
            pt = PowerTransformer(method="yeo-johnson")
            df[col] = pt.fit_transform(df[[col]].values).ravel()
            step_config["lambdas"] = float(pt.lambdas_[0])

        # 8. Encodings
        elif action == "encode_onehot":
            # For 1D preview, we can apply pd.get_dummies
            # We prefix the column name
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=True, dtype=int)
            df = pd.concat([df.drop(columns=[col]), dummies], axis=1)
            step_config["columns_added"] = list(dummies.columns)

        elif action == "encode_label":
            le = LabelEncoder()
            non_null = series.dropna()
            codes = pd.Series(-1, index=df.index, dtype=int)  # missing values become -1
            codes[non_null.index] = le.fit_transform(non_null.astype(str))
            df[col] = codes
            step_config["classes"] = [str(c) for c in le.classes_]

        # 9. Feature Selection
        elif action in ("drop_column", "drop_correlated_column"):
            df = df.drop(columns=[col])
            step_config["dropped"] = True

        # 10. Class Imbalance Resampling
        elif action == "resample_oversample":
            # Random over-sampling: duplicate minority class rows to match majority count
            original_shape = list(df.shape)
            class_dist_before = df[col].value_counts().to_dict()
            class_dist_before = {str(k): int(v) for k, v in class_dist_before.items()}

            value_counts = df[col].value_counts()
            majority_count = int(value_counts.max())
            frames = [df]

            for cls_val, cls_count in value_counts.items():
                if cls_count < majority_count:
                    minority_rows = df[df[col] == cls_val]
                    oversampled = minority_rows.sample(
                        n=majority_count - cls_count, replace=True, random_state=42
                    )
                    frames.append(oversampled)

            df = pd.concat(frames, ignore_index=True)

            class_dist_after = df[col].value_counts().to_dict()
            class_dist_after = {str(k): int(v) for k, v in class_dist_after.items()}
            step_config["original_shape"] = original_shape
            step_config["new_shape"] = list(df.shape)
            step_config["class_distribution_before"] = class_dist_before
            step_config["class_distribution_after"] = class_dist_after

        elif action == "resample_undersample":
            # Random under-sampling: reduce majority class rows to match minority count
            original_shape = list(df.shape)
            class_dist_before = df[col].value_counts().to_dict()
            class_dist_before = {str(k): int(v) for k, v in class_dist_before.items()}

            value_counts = df[col].value_counts()
            minority_count = int(value_counts.min())
            frames = []

            for cls_val in value_counts.index:
                cls_rows = df[df[col] == cls_val]
                if len(cls_rows) > minority_count:
                    cls_rows = cls_rows.sample(
                        n=minority_count, replace=False, random_state=42
                    )
                frames.append(cls_rows)

            df = pd.concat(frames, ignore_index=True)

            class_dist_after = df[col].value_counts().to_dict()
            class_dist_after = {str(k): int(v) for k, v in class_dist_after.items()}
            step_config["original_shape"] = original_shape
            step_config["new_shape"] = list(df.shape)
            step_config["class_distribution_before"] = class_dist_before
            step_config["class_distribution_after"] = class_dist_after

        return df, step_config

    @classmethod
    def _compute_summary_stats(cls, df: pd.DataFrame) -> dict:
        """Compute summary statistics for columns, converted to serializable floats."""
        summary = {}
        for col in df.columns:
            series = df[col]
            nulls = int(series.isna().sum())
            if pd.api.types.is_numeric_dtype(series):
                mean_val = series.mean()
                std_val = series.std()
                summary[col] = {
                    "mean": float(mean_val) if pd.notna(mean_val) else None,
                    "std": float(std_val) if pd.notna(std_val) else None,
                    "null_count": nulls,
                }
            else:
                summary[col] = {
                    "mean": None,
                    "std": None,
                    "null_count": nulls,
                }
        return summary

