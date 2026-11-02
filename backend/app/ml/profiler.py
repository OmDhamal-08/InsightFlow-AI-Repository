"""Dataset profiling engine using Pandas and NumPy.

Analyzes raw DataFrames to extract column types, missing value statistics,
uniqueness statistics, descriptive stats, and value distributions.
Converts all data types to JSON-compatible standard Python types.
"""

from datetime import datetime

import numpy as np
import warnings

import pandas as pd


class DatasetProfiler:
    """Computes descriptive and type statistics for raw Pandas DataFrames.

    Converts all types (e.g., float64, int64, NaNs) to standard Python
    types for JSON serialization.
    """

    @classmethod
    def profile(cls, df: pd.DataFrame) -> dict:
        """Analyze the DataFrame and return a dict of profiling metrics.

        Metrics returned:
            - total_rows: int
            - total_columns: int
            - duplicate_row_count: int
            - column_types: dict[str, str]
            - null_counts: dict[str, int]
            - unique_counts: dict[str, int]
            - descriptive_stats: dict[str, dict]
        """
        total_rows = len(df)
        total_columns = len(df.columns)

        # Compute duplicate rows count
        duplicate_row_count = int(df.duplicated().sum())

        column_types = {}
        null_counts = {}
        unique_counts = {}
        descriptive_stats = {}

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_counts[col] = null_count

            # Drop missing values for calculations
            clean_series = series.dropna()
            unique_count = int(clean_series.nunique())
            unique_counts[col] = unique_count

            # 1. Type Detection
            col_type = cls._detect_column_type(clean_series, unique_count)
            column_types[col] = col_type

            # 2. Descriptive Stats Computation
            stats = {}
            if len(clean_series) > 0:
                if col_type == "numeric":
                    # Numeric statistics
                    stats["mean"] = cls._to_json_val(clean_series.mean())
                    stats["median"] = cls._to_json_val(clean_series.median())
                    stats["std"] = cls._to_json_val(clean_series.std())
                    stats["min"] = cls._to_json_val(clean_series.min())
                    stats["max"] = cls._to_json_val(clean_series.max())
                    stats["q1"] = cls._to_json_val(clean_series.quantile(0.25))
                    stats["q3"] = cls._to_json_val(clean_series.quantile(0.75))
                    stats["skewness"] = cls._to_json_val(clean_series.skew())
                else:
                    # Non-numeric statistics (categorical, text, boolean, datetime)
                    mode_val = clean_series.mode()
                    if not mode_val.empty:
                        stats["top_value"] = cls._to_json_val(mode_val.iloc[0])
                        stats["frequency"] = int(clean_series.eq(mode_val.iloc[0]).sum())
                    else:
                        stats["top_value"] = None
                        stats["frequency"] = 0

                    if col_type == "datetime":
                        try:
                            # Min/max dates
                            parsed_dt = pd.to_datetime(clean_series, errors="coerce")
                            parsed_dt_clean = parsed_dt.dropna()
                            if not parsed_dt_clean.empty:
                                stats["min_date"] = parsed_dt_clean.min().isoformat()
                                stats["max_date"] = parsed_dt_clean.max().isoformat()
                        except Exception:
                            pass

                # Value distribution / frequencies (limited to top 10 unique values)
                if unique_count <= 25 or col_type in ("categorical", "boolean"):
                    value_freqs = clean_series.value_counts().head(10)
                    stats["frequencies"] = {
                        str(k): int(v) for k, v in value_freqs.items()
                    }

            descriptive_stats[col] = stats

        return {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "duplicate_row_count": duplicate_row_count,
            "column_types": column_types,
            "null_counts": null_counts,
            "unique_counts": unique_counts,
            "descriptive_stats": descriptive_stats,
        }

    @classmethod
    def _detect_column_type(cls, series: pd.Series, unique_count: int) -> str:
        """Classify column as numeric, categorical, boolean, datetime, or text."""
        # 1. Check if Boolean
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if unique_count <= 2 and set(series.unique()).issubset({0, 1, "0", "1", "yes", "no", "true", "false", "True", "False"}):
            return "boolean"

        # 2. Check if Datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        # Attempt datetime parsing on string columns to see if it's a date column
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            # Try to convert a sample of the column to dates
            sample = series.head(100)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")  # mixed/unknown formats are expected here
                    parsed = pd.to_datetime(sample, errors="coerce")
                # If at least 80% of non-null values parse as valid datetimes and it's not all NaNs
                if parsed.notna().sum() > 0.8 * len(sample) and parsed.notna().sum() > 0:
                    return "datetime"
            except Exception:
                pass

        # 3. Check if Numeric
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"

        # 4. Object/String Categorization
        # High cardinality => text. Low cardinality => categorical.
        if unique_count > 0:
            cardinality_ratio = unique_count / len(series) if len(series) > 0 else 0
            if unique_count < 20 or cardinality_ratio < 0.05:
                return "categorical"

        return "text"

    @classmethod
    def _to_json_val(cls, val):
        """Convert NumPy data types and NaNs to standard JSON serializable values."""
        if pd.isna(val):
            return None
        if isinstance(val, (np.bool_, bool)):
            return bool(val)
        if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(val)
        if isinstance(val, (np.floating, np.float64, np.float32)):
            if np.isnan(val) or np.isinf(val):
                return None
            return float(val)
        if isinstance(val, (pd.Timestamp, datetime)):
            return val.isoformat()
        return val
