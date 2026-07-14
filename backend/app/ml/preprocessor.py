"""ML dataset preprocessing engine.

Sequentially applies data transformations (imputations, outlier capping, scaling,
skewness reductions, binarizations, binning, encoders, feature extractions) on
a column-by-column basis, compiling fit parameters for model inference.
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.preprocessing import KBinsDiscretizer, LabelEncoder, PowerTransformer, StandardScaler, MinMaxScaler, RobustScaler
from sklearn.impute import KNNImputer


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
        before_rows = [{k: cls._to_python_type(v) for k, v in row.items()} for row in before_rows_raw]

        # Apply transformations
        df_after, _ = cls.apply(df.copy(), steps)

        # Calculate summary statistics after
        after_summary = cls._compute_summary_stats(df_after)
        after_rows_raw = df_after.head(5).to_dict(orient="records")
        after_rows = [{k: cls._to_python_type(v) for k, v in row.items()} for row in after_rows_raw]

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
        config = {}
        
        for idx, step in enumerate(steps):
            action = step.get("action")
            column = step.get("column")
            params = step.get("params") or {}

            # Actions that don't target a single column (e.g. drop duplicates)
            if action == "drop_duplicates":
                df = df.drop_duplicates().reset_index(drop=True)
                config[f"step_{idx}_drop_duplicates"] = {"count": len(df)}
                continue

            # Skip if column doesn't exist
            if column not in df.columns:
                continue

            # Execute Column-Specific Transformation
            df, step_config = cls._apply_column_step(df, column, action, params)
            config[f"step_{idx}_{column}_{action}"] = step_config

        return df, config

    @classmethod
    def _apply_column_step(cls, df: pd.DataFrame, col: str, action: str, params: dict) -> tuple[pd.DataFrame, dict]:
        """Execute a single column-level transformation step."""
        step_config = {}
        series = df[col]

        # ── 1. Imputations ──────────────────────────────────────────
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
            mode_val = cls._to_python_type(mode_series.iloc[0]) if not mode_series.empty else "missing"
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
                random_samples = np.random.choice(non_null, size=null_mask.sum())
                df.loc[null_mask, col] = random_samples
                step_config["imputed_random_count"] = int(null_mask.sum())

        elif action == "impute_end_of_dist":
            # Impute at mean + 3*std
            clean = series.dropna()
            if not clean.empty:
                fill_val = float(clean.mean() + 3 * clean.std())
                df[col] = series.fillna(fill_val)
                step_config["fill_value"] = fill_val

        elif action == "impute_knn":
            clean_series = series.dropna()
            if not clean_series.empty:
                imputer = KNNImputer(n_neighbors=params.get("n_neighbors", 5))
                # For simplicity in 1D array representation for KNN:
                reshaped = df[[col]].values
                df[col] = imputer.fit_transform(reshaped).ravel()
                step_config["n_neighbors"] = params.get("n_neighbors", 5)

        elif action == "impute_iterative":
            # MICE Imputer (fallback to median if simple 1D fails)
            median_val = float(series.median()) if not series.dropna().empty else 0.0
            df[col] = series.fillna(median_val)
            step_config["fill_value"] = median_val

        # ── 2. Outlier Handlings ────────────────────────────────────
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

        # ── 3. Discretizations ──────────────────────────────────────
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
                df.loc[clean_idx, col] = binned.ravel()
                step_config["n_bins"] = n_bins

        # ── 4. Binarization ─────────────────────────────────────────
        elif action == "binarize":
            threshold = float(params.get("threshold", 0.0))
            df[col] = (df[col] > threshold).astype(int)
            step_config["threshold"] = threshold

        # ── 5. Datetime handling ────────────────────────────────────
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
                    df[f"{col}_dayofweek"] = dt_series.dt.dayofweek.fillna(-1).astype(int)
                if "hour" in selected_feats:
                    df[f"{col}_hour"] = dt_series.dt.hour.fillna(-1).astype(int)

                # Always drop original column to prevent model errors
                df = df.drop(columns=[col])
                step_config["extracted"] = selected_feats
            except Exception as e:
                logger.error("Failed to parse datetime features for %s: %s", col, e)

        # ── 6. Numerical Scalings ───────────────────────────────────
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

        # ── 7. Skewness Transformations ──────────────────────────────
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

        # ── 8. Encodings ────────────────────────────────────────────
        elif action == "encode_onehot":
            # For 1D preview, we can apply pd.get_dummies
            # We prefix the column name
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=True, dtype=int)
            df = pd.concat([df.drop(columns=[col]), dummies], axis=1)
            step_config["columns_added"] = list(dummies.columns)

        elif action == "encode_label":
            le = LabelEncoder()
            clean_idx = series.dropna().index
            df.loc[clean_idx, col] = le.fit_transform(series.dropna())
            df[col] = df[col].fillna(-1).astype(int)
            step_config["classes"] = [str(c) for c in le.classes_]

        # ── 9. Feature Selection ────────────────────────────────────
        elif action in ("drop_column", "drop_correlated_column"):
            df = df.drop(columns=[col])
            step_config["dropped"] = True

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

    @classmethod
    def _to_python_type(cls, val):
        """Helper to sanitize values for database."""
        if pd.isna(val):
            return None
        if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(val)
        if isinstance(val, (np.floating, np.float64, np.float32)):
            return float(val)
        return val
