"""ML data quality analyzer engine.

Computes multi-dimensional quality index scores (Completeness, Uniqueness,
Outlier-free, Distribution, Independence) and flags data quality issues
with actionable preprocessing recommendations.
"""

from datetime import datetime
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityAnalyzer:
    """Computes multidimensional quality metrics and actionable recommendations."""

    @classmethod
    def analyze(cls, df: pd.DataFrame, column_types: dict[str, str]) -> dict:
        """Run complete data quality audit on a DataFrame.

        Args:
            df: The Pandas DataFrame to analyze.
            column_types: Dictionary mapping column names to their detected type.

        Returns:
            Dict containing detailed reports, quality score, and recommendations.
        """
        total_rows = len(df)
        total_columns = len(df.columns)
        total_cells = total_rows * total_columns

        # Ensure we can handle empty DataFrames safely
        if total_rows == 0:
            return cls._empty_analysis_result()

        numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
        categorical_cols = [c for c, t in column_types.items() if t in ("categorical", "boolean")]

        # ── 1. Completeness Analysis ────────────────────────────────
        null_counts = df.isna().sum()
        total_null_cells = int(null_counts.sum())
        completeness_score = 100.0 * (1 - (total_null_cells / total_cells))

        missing_value_report = {
            col: {
                "null_count": int(null_counts[col]),
                "null_percentage": float((null_counts[col] / total_rows) * 100),
            }
            for col in df.columns
        }

        # ── 2. Uniqueness Analysis ──────────────────────────────────
        duplicate_rows_count = int(df.duplicated().sum())
        duplicate_percentage = float((duplicate_rows_count / total_rows) * 100)
        uniqueness_score = 100.0 * (1 - (duplicate_rows_count / total_rows))

        duplicate_report = {
            "duplicate_count": duplicate_rows_count,
            "duplicate_percentage": duplicate_percentage,
        }

        # ── 3. Outlier Analysis ─────────────────────────────────────
        outlier_report = {}
        outlier_indices = set()
        for col in numeric_cols:
            clean_series = df[col].dropna()
            if len(clean_series) > 0:
                q1 = clean_series.quantile(0.25)
                q3 = clean_series.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outliers = clean_series[(clean_series < lower_bound) | (clean_series > upper_bound)]
                outlier_count = len(outliers)
                outlier_report[col] = {
                    "outlier_count": outlier_count,
                    "outlier_percentage": float((outlier_count / total_rows) * 100),
                    "lower_bound": cls._to_json_val(lower_bound),
                    "upper_bound": cls._to_json_val(upper_bound),
                }
                outlier_indices.update(outliers.index)
            else:
                outlier_report[col] = {
                    "outlier_count": 0,
                    "outlier_percentage": 0.0,
                    "lower_bound": None,
                    "upper_bound": None,
                }

        rows_with_outliers_count = len(outlier_indices)
        outlier_free_score = 100.0 * (1 - (rows_with_outliers_count / total_rows))

        # ── 4. Correlation & Multicollinearity ─────────────────────
        correlation_matrix_dict = {}
        high_correlation_pairs = []
        independence_score = 100.0
        redundant_cols = set()

        if len(numeric_cols) > 1:
            # Drop columns with zero variance
            corr_df = df[numeric_cols].select_dtypes(include=[np.number]).dropna(how="all")
            # Fill missing numerical values with median for correlation check
            corr_df = corr_df.fillna(corr_df.median())
            
            # Filter zero variance
            non_zero_var_cols = [c for c in corr_df.columns if corr_df[c].var() > 0]
            if len(non_zero_var_cols) > 1:
                corr_matrix = corr_df[non_zero_var_cols].corr()

                # Convert matrix to JSON serializable nested dict
                for col1 in corr_matrix.columns:
                    correlation_matrix_dict[col1] = {
                        col2: cls._to_json_val(corr_matrix.loc[col1, col2])
                        for col2 in corr_matrix.index
                    }

                # Find pairs with |r| > 0.85
                seen_pairs = set()
                for i in range(len(non_zero_var_cols)):
                    for j in range(i + 1, len(non_zero_var_cols)):
                        col1 = non_zero_var_cols[i]
                        col2 = non_zero_var_cols[j]
                        coef = corr_matrix.loc[col1, col2]
                        if not pd.isna(coef) and abs(coef) > 0.85:
                            high_correlation_pairs.append({
                                "col1": col1,
                                "col2": col2,
                                "coefficient": float(coef),
                            })
                            # Flag the one with more missing values or alphabetically second
                            redundant_cols.add(col2)
            
            if len(numeric_cols) > 0:
                independence_score = 100.0 * (1 - (len(redundant_cols) / len(numeric_cols)))
        else:
            # If 0 or 1 numeric column, Independence is perfect
            independence_score = 100.0

        correlation_report = {
            "matrix": correlation_matrix_dict,
            "high_correlation_pairs": high_correlation_pairs,
        }

        # ── 5. Skewness Analysis ────────────────────────────────────
        skewness_report = {}
        skewed_cols_count = 0
        distribution_score = 100.0

        for col in numeric_cols:
            clean_series = df[col].dropna()
            if len(clean_series) > 0:
                skew_val = clean_series.skew()
                skew_val_json = cls._to_json_val(skew_val)
                skewness_report[col] = {"skewness": skew_val_json}
                if skew_val_json is not None and abs(skew_val_json) > 1.5:
                    skewed_cols_count += 1
            else:
                skewness_report[col] = {"skewness": None}

        if len(numeric_cols) > 0:
            distribution_score = 100.0 * (1 - (skewed_cols_count / len(numeric_cols)))

        # ── 6. Class Imbalance Analysis ─────────────────────────────
        imbalance_report = {}
        for col in categorical_cols:
            clean_series = df[col].dropna()
            if len(clean_series) > 0:
                unique_counts = clean_series.value_counts()
                if not unique_counts.empty:
                    # Check ratio of max class to min class
                    max_class_count = int(unique_counts.max())
                    min_class_count = int(unique_counts.min())
                    
                    ratio = max_class_count / min_class_count if min_class_count > 0 else 0
                    imbalance_report[col] = {
                        "frequencies": {str(k): int(v) for k, v in unique_counts.items()},
                        "majority_to_minority_ratio": float(ratio),
                    }

        # ── 7. Composite DQI Score Calculation ─────────────────────
        # Completeness: 30%, Uniqueness: 20%, Outliers: 20%, Skewness: 15%, Independence: 15%
        quality_score = (
            (completeness_score * 0.30) +
            (uniqueness_score * 0.20) +
            (outlier_free_score * 0.20) +
            (distribution_score * 0.15) +
            (independence_score * 0.15)
        )
        quality_score = float(np.clip(quality_score, 0.0, 100.0))

        # ── 8. Actionable Preprocessing Recommendations ─────────────
        recommendations = []

        # Missing values recommendations
        for col, metrics in missing_value_report.items():
            pct = metrics["null_percentage"]
            count = metrics["null_count"]
            if pct > 0:
                if pct > 50.0:
                    recommendations.append({
                        "description": f"Column '{col}' has extreme missing data ({pct:.1f}%).",
                        "severity": "critical",
                        "column": col,
                        "recommended_action": "drop_column",
                        "value": pct,
                    })
                elif pct >= 5.0:
                    action = "impute_knn" if column_types[col] == "numeric" else "impute_mode"
                    recommendations.append({
                        "description": f"Column '{col}' is missing {pct:.1f}% of its values.",
                        "severity": "warning",
                        "column": col,
                        "recommended_action": action,
                        "value": pct,
                    })
                else:
                    action = "impute_median" if column_types[col] == "numeric" else "impute_mode"
                    recommendations.append({
                        "description": f"Column '{col}' has minor missing values ({pct:.1f}%).",
                        "severity": "info",
                        "column": col,
                        "recommended_action": action,
                        "value": pct,
                    })

        # Duplicates recommendations
        if duplicate_rows_count > 0:
            recommendations.append({
                "description": f"Dataset contains {duplicate_rows_count} exact duplicate rows ({duplicate_percentage:.1f}%).",
                "severity": "warning",
                "column": None,
                "recommended_action": "drop_duplicates",
                "value": duplicate_percentage,
            })

        # Outliers recommendations
        for col, o_stats in outlier_report.items():
            o_pct = o_stats["outlier_percentage"]
            if o_pct > 0:
                # Few outliers → drop those rows; many → cap them at the IQR fences
                action = "outliers_drop" if o_pct < 2.0 else "outliers_cap"
                recommendations.append({
                    "description": f"Column '{col}' has {o_stats['outlier_count']} outliers ({o_pct:.1f}%).",
                    "severity": "warning",
                    "column": col,
                    "recommended_action": action,
                    "value": o_pct,
                })

        # Multicollinearity recommendations
        for pair in high_correlation_pairs:
            col1, col2 = pair["col1"], pair["col2"]
            recommendations.append({
                "description": f"High multicollinearity between '{col1}' and '{col2}' (correlation {pair['coefficient']:.2f}).",
                "severity": "warning",
                "column": col2,
                "recommended_action": "drop_correlated_column",
                "value": pair["coefficient"],
            })

        # Skewness recommendations
        for col, s_stats in skewness_report.items():
            skew = s_stats["skewness"]
            if skew is not None and abs(skew) > 1.5:
                recommendations.append({
                    "description": f"Column '{col}' is highly skewed (skewness = {skew:.2f}).",
                    "severity": "info",
                    "column": col,
                    "recommended_action": "apply_log_transform",
                    "value": skew,
                })

        # Class imbalance recommendations
        for col, i_stats in imbalance_report.items():
            ratio = i_stats["majority_to_minority_ratio"]
            if ratio > 4.0:
                recommendations.append({
                    "description": (
                        f"Column '{col}' has severe class imbalance (ratio {ratio:.1f}:1). If it is your "
                        f"prediction target, consider over-sampling the minority class before training."
                    ),
                    "severity": "warning",
                    "column": col,
                    "recommended_action": "resample_oversample",
                    "value": ratio,
                })

        return {
            "quality_score": quality_score,
            "missing_value_report": missing_value_report,
            "duplicate_report": duplicate_report,
            "outlier_report": outlier_report,
            "correlation_report": correlation_report,
            "skewness_report": skewness_report,
            "imbalance_report": imbalance_report,
            "recommendations": recommendations,
        }

    @classmethod
    def _empty_analysis_result(cls) -> dict:
        """Provide a clean fallback result for empty datasets."""
        return {
            "quality_score": 0.0,
            "missing_value_report": {},
            "duplicate_report": {"duplicate_count": 0, "duplicate_percentage": 0.0},
            "outlier_report": {},
            "correlation_report": {"matrix": {}, "high_correlation_pairs": []},
            "skewness_report": {},
            "imbalance_report": {},
            "recommendations": [],
        }

    @classmethod
    def _to_json_val(cls, val):
        """Helper to convert numpy numeric types to serializable python numbers."""
        if pd.isna(val):
            return None
        if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(val)
        if isinstance(val, (np.floating, np.float64, np.float32)):
            if np.isnan(val) or np.isinf(val):
                return None
            return float(val)
        return val
