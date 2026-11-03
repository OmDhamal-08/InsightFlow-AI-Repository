"""ML EDA generator engine.

Computes pre-calculated statistical coordinates for summary visualizations (heatmaps,
missing values, distributions) and custom interactive plots (normality tests, boxplots,
QQ-plots, and scatter plots with linear regression lines).
"""

import numpy as np
import pandas as pd
import scipy.stats as stats

from app.ml.json_utils import to_json_value


class EdaGenerator:
    """Calculates statistics coordinates and AI insights for dataset visualization."""

    @classmethod
    def generate_summary(cls, df: pd.DataFrame, column_types: dict[str, str]) -> list[dict]:
        """Auto-generate overview panel charts and insights.

        Produces:
            1. Correlation Heatmap (numeric columns)
            2. Missing Values Bar Chart (if nulls exist)
            3. Column Distribution (top numeric/categorical column)
        """
        results = []
        total_rows = len(df)

        numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
        categorical_cols = [c for c, t in column_types.items() if t in ("categorical", "boolean")]

        # 1. Correlation Heatmap
        if len(numeric_cols) > 1:
            clean_df = df[numeric_cols].select_dtypes(include=[np.number]).dropna(how="all")
            if not clean_df.empty and len(clean_df.columns) > 1:
                # Median impute for correlation matrix calculation
                corr_df = clean_df.fillna(clean_df.median())
                # Filter zero variance
                non_zero_var = [c for c in corr_df.columns if corr_df[c].var() > 0]
                
                if len(non_zero_var) > 1:
                    corr_matrix = corr_df[non_zero_var].corr()
                    
                    # Convert to JSON coordinates
                    x_labels = list(corr_matrix.columns)
                    y_labels = list(corr_matrix.index)
                    matrix_values = [
                        [to_json_value(corr_matrix.loc[y, x]) for x in x_labels]
                        for y in y_labels
                    ]

                    # AI Insight
                    flat_corr = []
                    for i in range(len(x_labels)):
                        for j in range(i+1, len(x_labels)):
                            flat_corr.append((x_labels[i], x_labels[j], corr_matrix.iloc[i, j]))
                    
                    insight = "Correlation Heatmap: Displays relationships between numeric variables."
                    if flat_corr:
                        flat_corr.sort(key=lambda item: abs(item[2]), reverse=True)
                        top_pair = flat_corr[0]
                        direction = "positive" if top_pair[2] > 0 else "negative"
                        insight += f" Strongest relationship is between '{top_pair[0]}' and '{top_pair[1]}' (correlation coefficient = {top_pair[2]:.2f}, indicating a {direction} linear trend)."

                    results.append({
                        "chart_type": "correlation_matrix",
                        "chart_config": {
                            "title": "Feature Correlation Heatmap",
                            "x_label": "Features",
                            "y_label": "Features",
                            "x_categories": x_labels,
                            "y_categories": y_labels,
                        },
                        "chart_data": {"matrix": matrix_values},
                        "insight": insight,
                    })

        # 2. Missing Values Bar Chart
        null_counts = df.isna().sum()
        cols_with_nulls = [col for col in df.columns if null_counts[col] > 0]
        
        if cols_with_nulls:
            null_pcts = [float((null_counts[c] / total_rows) * 100) for c in cols_with_nulls]
            insight = "Missing Values: Bar chart displays percentage of null values per column."
            max_null_col = cols_with_nulls[np.argmax(null_pcts)]
            max_null_pct = max(null_pcts)
            insight += f" Column '{max_null_col}' has the highest missing value density ({max_null_pct:.1f}%). Imputation is recommended before feeding to ML models."

            results.append({
                "chart_type": "missing_values",
                "chart_config": {
                    "title": "Missing Value Percentages per Column",
                    "x_label": "Columns",
                    "y_label": "Null %",
                    "x_categories": cols_with_nulls,
                },
                "chart_data": {"percentages": null_pcts, "counts": [int(null_counts[c]) for c in cols_with_nulls]},
                "insight": insight,
            })

        # 3. Categorical Counts (Target candidate)
        if categorical_cols:
            top_cat = categorical_cols[0]
            clean_series = df[top_cat].dropna()
            if not clean_series.empty:
                counts = clean_series.value_counts().head(10)
                labels = [str(k) for k in counts.index]
                values = [int(v) for v in counts.values]

                insight = f"Value Counts: Distribution of unique categories in column '{top_cat}'."
                majority = labels[0]
                maj_pct = (values[0] / len(clean_series)) * 100
                insight += f" The category '{majority}' is the majority class representing {maj_pct:.1f}% of values."

                results.append({
                    "chart_type": "categorical_counts",
                    "chart_config": {
                        "title": f"Category Distribution: {top_cat}",
                        "x_label": "Categories",
                        "y_label": "Frequency",
                        "x_categories": labels,
                    },
                    "chart_data": {"values": values},
                    "insight": insight,
                })

        # 4. Feature Skewness Overview
        if numeric_cols:
            skews = []
            for col in numeric_cols:
                series = df[col].dropna()
                if len(series) > 2:
                    skews.append((col, float(series.skew())))
            
            if skews:
                labels = [item[0] for item in skews]
                values = [item[1] for item in skews]
                
                # Highlight highly skewed column
                highly_skewed = [c for c, s in skews if abs(s) > 1.0]
                insight = "Feature Skewness: Displays the skewness coefficient of numeric columns."
                if highly_skewed:
                    insight += f" Highly skewed features (>1.0 or <-1.0) found: {', '.join(highly_skewed[:3])}. Consider a log or Yeo-Johnson transform on the Preprocessing page."
                else:
                    insight += " All numeric columns show low or moderate skewness (skew within [-1.0, 1.0])."

                results.append({
                    "chart_type": "numerical_skewness",
                    "chart_config": {
                        "title": "Numeric Features Skewness",
                        "x_label": "Features",
                        "y_label": "Skewness Coefficient",
                        "x_categories": labels,
                    },
                    "chart_data": {"values": values},
                    "insight": insight,
                })

        # 5. Outlier Densities Overview
        if numeric_cols:
            outlier_pcts = []
            for col in numeric_cols:
                series = df[col].dropna()
                if len(series) > 4:
                    q1 = series.quantile(0.25)
                    q3 = series.quantile(0.75)
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outliers = series[(series < lower) | (series > upper)]
                    pct = float((len(outliers) / len(series)) * 100)
                    outlier_pcts.append((col, pct))
            
            if outlier_pcts:
                labels = [item[0] for item in outlier_pcts]
                values = [item[1] for item in outlier_pcts]

                # Find highest outlier percentage
                max_out = max(outlier_pcts, key=lambda x: x[1])
                insight = "Outliers Density: Displays the percentage of rows classified as outliers via the 1.5 * IQR rule."
                if max_out[1] > 0:
                    insight += f" Feature '{max_out[0]}' has the highest outlier density ({max_out[1]:.1f}%). Preprocess with Winsorization or Capping."
                else:
                    insight += " No outliers detected in any numeric columns."

                results.append({
                    "chart_type": "outlier_densities",
                    "chart_config": {
                        "title": "Outlier Densities per Column (%)",
                        "x_label": "Features",
                        "y_label": "Outlier Percentage (%)",
                        "x_categories": labels,
                    },
                    "chart_data": {"values": values},
                    "insight": insight,
                })

        # 6. Categorical Cardinality Overview
        if categorical_cols:
            cardinalities = []
            for col in categorical_cols:
                cardinalities.append((col, int(df[col].nunique())))
            
            if cardinalities:
                labels = [item[0] for item in cardinalities]
                values = [item[1] for item in cardinalities]

                max_card = max(cardinalities, key=lambda x: x[1])
                insight = "Categorical Cardinality: Shows the number of unique classes in categorical columns."
                if max_card[1] > 20:
                    insight += f" Feature '{max_card[0]}' has high cardinality ({max_card[1]} classes) and will require target encoding or binning."
                else:
                    insight += " All categorical columns show low cardinality (<20 classes)."

                results.append({
                    "chart_type": "categorical_cardinality",
                    "chart_config": {
                        "title": "Categorical Columns Cardinality",
                        "x_label": "Features",
                        "y_label": "Unique Class Count",
                        "x_categories": labels,
                    },
                    "chart_data": {"values": values},
                    "insight": insight,
                })

        return results

    @classmethod
    def generate_custom_plot(
        cls, df: pd.DataFrame, chart_type: str, columns: list[str], column_types: dict[str, str]
    ) -> dict:
        """Calculate dynamic, user-selected column-level exploratory plots on the fly."""
        col = columns[0] if columns else None
        total_rows = len(df)

        if not col or col not in df.columns:
            return {"error": "Invalid column selection"}

        series = df[col].dropna()
        if series.empty:
            return {"error": f"Column '{col}' is entirely empty"}

        col_type = column_types.get(col, "numeric")
        is_numeric = col_type == "numeric"

        if chart_type in ("distribution", "boxplot", "qq_plot", "scatter") and not is_numeric:
            return {"error": f"Column '{col}' is categorical. Please select a Category Distribution or Category Share chart."}

        # A. Normality & Distribution
        if chart_type == "distribution":
            # 1. Compute histogram bins (Freedman-Diaconis rule or auto)
            counts, bin_edges = np.histogram(series, bins="auto")
            bin_centers = [(float(bin_edges[i]) + float(bin_edges[i+1])) / 2.0 for i in range(len(counts))]
            bin_labels = [f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}" for i in range(len(counts))]

            # 2. Fit normal distribution curve
            mean = float(series.mean())
            std = float(series.std()) if len(series) > 1 else 0.0
            
            normal_curve = []
            if std > 0:
                # Generate 100 points across the range
                linspace_x = np.linspace(float(series.min()), float(series.max()), 100)
                pdf_y = stats.norm.pdf(linspace_x, mean, std)
                # Multiply by total count * average bin width to scale curve to histogram counts
                bin_width = float(bin_edges[1] - bin_edges[0]) if len(bin_edges) > 1 else 1.0
                scale = len(series) * bin_width
                normal_curve = [{"x": float(x), "y": float(y * scale)} for x, y in zip(linspace_x, pdf_y)]

            # 3. Normality test (Shapiro-Wilk for N <= 5000, else Kolmogorov-Smirnov)
            is_normal = False
            p_value = 0.0
            try:
                if len(series) <= 5000:
                    stat, p_val = stats.shapiro(series)
                else:
                    # KS test against fitted normal
                    stat, p_val = stats.kstest(series, "norm", args=(mean, std))
                p_value = float(p_val)
                is_normal = p_value > 0.05
            except Exception:
                pass

            skewness = float(series.skew()) if len(series) > 2 else 0.0

            # AI Insight formulation
            insight = f"Distribution of '{col}': Skewness is {skewness:.2f}. "
            if is_normal:
                insight += f"The column passes the normality test (p-value = {p_value:.4f} > 0.05), indicating it is normally distributed. Algorithms requiring Gaussian inputs (e.g. Linear Regression, LDA) will perform well without transforms."
            else:
                insight += f"The column fails the normality test (p-value = {p_value:.4f} <= 0.05), indicating a non-normal/skewed distribution. A log or Yeo-Johnson transform (Preprocessing page) is recommended before model training."

            return {
                "chart_type": "distribution",
                "chart_config": {
                    "title": f"Normality Analysis: {col}",
                    "x_label": col,
                    "y_label": "Frequency",
                    "x_categories": bin_labels,
                },
                "chart_data": {
                    "centers": bin_centers,
                    "counts": [int(c) for c in counts],
                    "normal_curve": normal_curve,
                    "is_normal": is_normal,
                    "p_value": p_value,
                    "skewness": skewness,
                },
                "insight": insight,
            }

        # B. Boxplot & Outliers
        elif chart_type == "boxplot":
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            median = float(series.median())
            iqr = q3 - q1
            lower = float(q1 - 1.5 * iqr)
            upper = float(q3 + 1.5 * iqr)
            
            # Clamp min/max values to actual data range
            min_val = float(series.min())
            max_val = float(series.max())
            whisker_lower = max(lower, min_val)
            whisker_upper = min(upper, max_val)

            # Find outliers points
            outliers = series[(series < lower) | (series > upper)]
            outliers_list = [float(v) for v in outliers.head(50).values]  # Cap list to prevent huge JSONs

            insight = f"Box & Whiskers Plot: Median is {median:.2f}. "
            if len(outliers) > 0:
                out_pct = (len(outliers) / total_rows) * 100
                insight += f"Detected {len(outliers)} outliers ({out_pct:.1f}% of rows) beyond the IQR fences [{lower:.2f}, {upper:.2f}]. Preprocessing via Winsorization/Capping or dropping outlier rows is suggested."
            else:
                insight += "No outliers detected. Values are safely bounded within IQR bounds."

            return {
                "chart_type": "boxplot",
                "chart_config": {
                    "title": f"Outliers Summary: {col}",
                    "x_label": col,
                    "y_label": "Value",
                },
                "chart_data": {
                    "min": min_val,
                    "lower_whisker": whisker_lower,
                    "q1": q1,
                    "median": median,
                    "q3": q3,
                    "upper_whisker": whisker_upper,
                    "max": max_val,
                    "outliers": outliers_list,
                    "outlier_count": len(outliers),
                },
                "insight": insight,
            }

        # C. Q-Q Plot (Quantile-Quantile)
        elif chart_type == "qq_plot":
            # Compute theoretical quantiles vs sample quantiles
            clean_series = series.values
            if len(clean_series) > 1000:
                # Sample 1000 points to keep chart lightweight
                clean_series = np.random.choice(clean_series, size=1000, replace=False)
            
            (osm, osr), (slope, intercept, r) = stats.probplot(clean_series, dist="norm")
            
            points = [{"x": float(theo), "y": float(sample)} for theo, sample in zip(osm, osr)]
            
            # Calculate line of best fit coordinates
            min_x = float(osm.min())
            max_x = float(osm.max())
            line_coords = [
                {"x": min_x, "y": float(slope * min_x + intercept)},
                {"x": max_x, "y": float(slope * max_x + intercept)}
            ]

            insight = f"Normal Quantile-Quantile (Q-Q) Plot: R² of the diagonal fit is {r**2:.4f}. "
            if r**2 > 0.95:
                insight += "Data points follow the diagonal line very closely, indicating a strong normal/Gaussian behavior."
            else:
                insight += "Significant deviations from the diagonal line (especially at the tails) indicate high kurtosis or skewness, confirming non-normality."

            return {
                "chart_type": "qq_plot",
                "chart_config": {
                    "title": f"Normal Q-Q Plot: {col}",
                    "x_label": "Theoretical Quantiles",
                    "y_label": "Ordered Values",
                },
                "chart_data": {
                    "points": points,
                    "line": line_coords,
                    "r_squared": float(r**2),
                },
                "insight": insight,
            }

        # D. Bivariate Scatter Plot with Linear Trend
        elif chart_type == "scatter":
            col2 = columns[1] if len(columns) > 1 else None
            if not col2 or col2 not in df.columns:
                return {"error": "Bivariate scatter requires selecting 2 columns"}

            series2 = df[col2].dropna()
            if series2.empty:
                return {"error": f"Selected second column '{col2}' is empty"}

            # Align indices
            aligned_df = df[[col, col2]].dropna()
            if len(aligned_df) < 3:
                return {"error": "Not enough overlapping rows to plot scatter"}

            x = aligned_df[col].values
            y = aligned_df[col2].values

            # Sample if too big
            if len(x) > 1000:
                sample_idx = np.random.choice(len(x), size=1000, replace=False)
                x = x[sample_idx]
                y = y[sample_idx]

            # Fit linear trend line: y = mx + c
            slope = 0.0
            intercept = 0.0
            r_squared = 0.0
            line_coords = []
            try:
                m, c = np.polyfit(x, y, 1)
                slope = float(m)
                intercept = float(c)

                # Compute R^2
                y_pred = m * x + c
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r_squared = float(1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0)

                min_x = float(x.min())
                max_x = float(x.max())
                line_coords = [
                    {"x": min_x, "y": float(slope * min_x + intercept)},
                    {"x": max_x, "y": float(slope * max_x + intercept)}
                ]
            except Exception:
                pass

            points = [{"x": float(x_val), "y": float(y_val)} for x_val, y_val in zip(x, y)]

            direction = "positive" if slope > 0 else "negative"
            strength = "strong" if r_squared > 0.6 else ("moderate" if r_squared > 0.2 else "weak")
            insight = f"Bivariate Scatter Plot: Explores trend between '{col}' (X) and '{col2}' (Y). "
            if r_squared > 0.05:
                insight += f"Fitted regression line: $Y = {slope:.3f}X + {intercept:.2f}$ with an $R^2$ of {r_squared:.3f}, indicating a {strength} {direction} trend."
            else:
                insight += "Data points show no notable linear trend or correlation."

            return {
                "chart_type": "scatter",
                "chart_config": {
                    "title": f"Bivariate Trend: {col} vs {col2}",
                    "x_label": col,
                    "y_label": col2,
                },
                "chart_data": {
                    "points": points,
                    "line": line_coords,
                    "slope": slope,
                    "intercept": intercept,
                    "r_squared": r_squared,
                },
                "insight": insight,
            }

        elif chart_type == "categorical_counts":
            counts = series.value_counts().head(20)
            labels = [str(k) for k in counts.index]
            values = [int(v) for v in counts.values]

            insight = f"Category Distribution: Value counts of unique classes in column '{col}'."
            majority = labels[0] if labels else "None"
            maj_pct = (values[0] / len(series)) * 100 if values else 0.0
            insight += f" The category '{majority}' is the majority class representing {maj_pct:.1f}% of values."

            return {
                "chart_type": "categorical_counts",
                "chart_config": {
                    "title": f"Category Distribution: {col}",
                    "x_label": "Categories",
                    "y_label": "Frequency",
                    "x_categories": labels,
                },
                "chart_data": {"values": values},
                "insight": insight,
            }

        elif chart_type == "categorical_pie":
            counts = series.value_counts().head(10)
            labels = [str(k) for k in counts.index]
            values = [int(v) for v in counts.values]

            insight = f"Category Share: Percentage breakdown of column '{col}'."
            majority = labels[0] if labels else "None"
            maj_pct = (values[0] / len(series)) * 100 if values else 0.0
            insight += f" The category '{majority}' represents the largest slice ({maj_pct:.1f}%)."

            return {
                "chart_type": "categorical_pie",
                "chart_config": {
                    "title": f"Category Share: {col}",
                    "x_label": "Categories",
                    "y_label": "Percentage",
                    "x_categories": labels,
                },
                "chart_data": {"values": values},
                "insight": insight,
            }

        return {"error": "Unsupported chart type"}

    @classmethod
    def generate_bivariate_analysis(cls, df: pd.DataFrame, target_column: str, column_types: dict[str, str]) -> dict:
        """Generate target-aware bivariate statistical analysis and chart data.

        Computes association tests between every feature column and the
        designated target column, selecting the appropriate statistical test
        based on the column types (numeric vs categorical).

        Args:
            df: The Pandas DataFrame to analyze.
            target_column: Name of the target column.
            column_types: Dictionary mapping column names to their detected type
                          ('numeric', 'categorical', or 'boolean').

        Returns:
            Dict with keys ``target_column``, ``target_type``, ``associations``
            (per-feature test results), and ``bivariate_charts`` (Plotly-ready
            chart data dicts).
        """
        # Edge case: empty or missing target
        if df.empty or target_column not in df.columns:
            return {
                "target_column": target_column,
                "target_type": "unknown",
                "associations": [],
                "bivariate_charts": [],
            }

        target_type_raw = column_types.get(target_column, "numeric")
        target_type = "numeric" if target_type_raw == "numeric" else "categorical"

        feature_cols = [c for c in df.columns if c != target_column and c in column_types]
        numeric_features = [c for c in feature_cols if column_types[c] == "numeric"]
        categorical_features = [c for c in feature_cols if column_types[c] in ("categorical", "boolean")]

        associations: list[dict] = []
        bivariate_charts: list[dict] = []

        # Helper: classify effect-size strength
        def _strength(effect: float | None) -> str:
            if effect is None:
                return "none"
            abs_e = abs(effect)
            if abs_e >= 0.5:
                return "strong"
            if abs_e >= 0.3:
                return "moderate"
            if abs_e >= 0.1:
                return "weak"
            return "none"

        # CASE 1: Numeric target + Numeric feature
        if target_type == "numeric":
            # Pre-compute absolute Pearson correlations to rank features
            corr_scores: list[tuple[str, float]] = []
            for col in numeric_features:
                aligned = df[[target_column, col]].dropna()
                if len(aligned) < 3 or aligned[col].std() == 0 or aligned[target_column].std() == 0:
                    continue
                try:
                    r, _ = stats.pearsonr(aligned[target_column], aligned[col])
                    corr_scores.append((col, abs(r)))
                except Exception:
                    continue
            corr_scores.sort(key=lambda x: x[1], reverse=True)
            top_numeric = [c for c, _ in corr_scores[:6]]

            for col in numeric_features:
                aligned = df[[target_column, col]].dropna()
                if len(aligned) < 3 or aligned[col].std() == 0 or aligned[target_column].std() == 0:
                    associations.append({
                        "column": col,
                        "column_type": "numeric",
                        "test_name": "Pearson Correlation",
                        "statistic": None,
                        "p_value": None,
                        "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' has insufficient non-null data or zero variance for correlation analysis.",
                    })
                    continue

                try:
                    pearson_r, pearson_p = stats.pearsonr(aligned[target_column], aligned[col])
                    spearman_r, spearman_p = stats.spearmanr(aligned[target_column], aligned[col])
                except Exception:
                    pearson_r = spearman_r = None
                    pearson_p = spearman_p = None

                # Use the test with the stronger absolute effect as primary
                if pearson_r is not None and spearman_r is not None:
                    if abs(spearman_r) > abs(pearson_r):
                        primary_name = "Spearman Correlation"
                        primary_stat = to_json_value(spearman_r)
                        primary_p = to_json_value(spearman_p)
                        effect = to_json_value(spearman_r)
                    else:
                        primary_name = "Pearson Correlation"
                        primary_stat = to_json_value(pearson_r)
                        primary_p = to_json_value(pearson_p)
                        effect = to_json_value(pearson_r)
                else:
                    primary_name = "Pearson Correlation"
                    primary_stat = to_json_value(pearson_r)
                    primary_p = to_json_value(pearson_p)
                    effect = to_json_value(pearson_r)

                s = _strength(effect)
                direction = "positive" if (effect or 0) > 0 else "negative"
                r_str = f"{effect:.3f}" if effect is not None else "N/A"
                p_str = f"{primary_p:.4f}" if primary_p is not None else "N/A"
                insight = (
                    f"'{col}' shows a {s} {direction} {primary_name.lower()} "
                    f"with '{target_column}' (r = {r_str}, p = {p_str})."
                    if effect is not None and primary_p is not None
                    else f"Could not compute correlation between '{col}' and '{target_column}'."
                )

                associations.append({
                    "column": col,
                    "column_type": "numeric",
                    "test_name": primary_name,
                    "statistic": primary_stat,
                    "p_value": primary_p,
                    "effect_size": effect,
                    "strength": s,
                    "insight": insight,
                })

                # Chart: scatter + regression for top 6
                if col in top_numeric:
                    x = aligned[col].values
                    y = aligned[target_column].values
                    # Sample for large datasets
                    if len(x) > 1000:
                        idx = np.random.choice(len(x), size=1000, replace=False)
                        x, y = x[idx], y[idx]
                    try:
                        lr = stats.linregress(x, y)
                        slope, intercept, r_sq = float(lr.slope), float(lr.intercept), float(lr.rvalue ** 2)
                    except Exception:
                        slope, intercept, r_sq = 0.0, 0.0, 0.0

                    bivariate_charts.append({
                        "chart_type": "scatter_regression",
                        "chart_config": {
                            "title": f"{col} vs {target_column}",
                            "x_label": col,
                            "y_label": target_column,
                        },
                        "chart_data": {
                            "points": [{"x": to_json_value(xv), "y": to_json_value(yv)} for xv, yv in zip(x, y)],
                            "regression": {"slope": slope, "intercept": intercept, "r_squared": r_sq},
                        },
                        "feature_column": col,
                        "insight": f"Linear trend: Y = {slope:.3f}X + {intercept:.2f} (R² = {r_sq:.3f}).",
                    })

        # CASE 2: Numeric target + Categorical feature
        if target_type == "numeric":
            for col in categorical_features:
                n_unique = df[col].nunique()
                if n_unique > 15 or n_unique < 2:
                    associations.append({
                        "column": col,
                        "column_type": column_types[col],
                        "test_name": "ANOVA F-test",
                        "statistic": None,
                        "p_value": None,
                        "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' skipped: {'too many' if n_unique > 15 else 'fewer than 2'} unique categories ({n_unique}).",
                    })
                    continue

                aligned = df[[target_column, col]].dropna()
                if aligned.empty:
                    associations.append({
                        "column": col,
                        "column_type": column_types[col],
                        "test_name": "ANOVA F-test",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' has no overlapping non-null rows with the target.",
                    })
                    continue

                groups = [grp[target_column].values for _, grp in aligned.groupby(col) if len(grp) >= 1]
                if len(groups) < 2:
                    associations.append({
                        "column": col, "column_type": column_types[col],
                        "test_name": "ANOVA F-test",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' has fewer than 2 populated groups for ANOVA.",
                    })
                    continue

                try:
                    f_stat, p_val = stats.f_oneway(*groups)
                except Exception:
                    f_stat, p_val = None, None

                # Eta-squared = SS_between / SS_total
                eta_sq = None
                if f_stat is not None:
                    grand_mean = aligned[target_column].mean()
                    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
                    ss_total = ((aligned[target_column] - grand_mean) ** 2).sum()
                    eta_sq = float(ss_between / ss_total) if ss_total > 0 else 0.0

                s = _strength(eta_sq)
                f_str = f"{f_stat:.2f}" if f_stat is not None else "N/A"
                p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
                eta_str = f"{eta_sq:.3f}" if eta_sq is not None else "N/A"
                insight = (
                    f"ANOVA F-test between '{col}' and '{target_column}': F = {f_str}, "
                    f"p = {p_str}, η² = {eta_str} ({s} effect)."
                    if f_stat is not None and p_val is not None and eta_sq is not None
                    else f"Could not compute ANOVA for '{col}' vs '{target_column}'."
                )

                associations.append({
                    "column": col,
                    "column_type": column_types[col],
                    "test_name": "ANOVA F-test",
                    "statistic": to_json_value(f_stat),
                    "p_value": to_json_value(p_val),
                    "effect_size": to_json_value(eta_sq),
                    "strength": s,
                    "insight": insight,
                })

                # Chart: grouped box plot (categories on x-axis, target distribution on y)
                box_data: dict[str, dict] = {}
                for cat_val, grp in aligned.groupby(col):
                    vals = grp[target_column].dropna()
                    if vals.empty:
                        continue
                    box_data[str(cat_val)] = {
                        "min": to_json_value(vals.min()),
                        "q1": to_json_value(vals.quantile(0.25)),
                        "median": to_json_value(vals.median()),
                        "q3": to_json_value(vals.quantile(0.75)),
                        "max": to_json_value(vals.max()),
                    }

                bivariate_charts.append({
                    "chart_type": "grouped_box",
                    "chart_config": {
                        "title": f"{target_column} by {col}",
                        "x_label": col,
                        "y_label": target_column,
                    },
                    "chart_data": {"groups": box_data},
                    "feature_column": col,
                    "insight": f"Box plots of '{target_column}' grouped by '{col}' categories.",
                })

        # CASE 3: Categorical target + Numeric feature
        if target_type == "categorical":
            # Rank by Kruskal-Wallis H statistic to pick top 6
            kw_scores: list[tuple[str, float]] = []
            for col in numeric_features:
                aligned = df[[target_column, col]].dropna()
                if aligned.empty or aligned[col].std() == 0:
                    continue
                groups = [grp[col].values for _, grp in aligned.groupby(target_column) if len(grp) >= 1]
                if len(groups) < 2:
                    continue
                try:
                    h_stat, _ = stats.kruskal(*groups)
                    kw_scores.append((col, float(h_stat)))
                except Exception:
                    continue
            kw_scores.sort(key=lambda x: x[1], reverse=True)
            top_kw = {c for c, _ in kw_scores[:6]}

            for col in numeric_features:
                aligned = df[[target_column, col]].dropna()
                if aligned.empty or aligned[col].std() == 0:
                    associations.append({
                        "column": col, "column_type": "numeric",
                        "test_name": "Kruskal-Wallis H-test",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' has insufficient data or zero variance.",
                    })
                    continue

                groups = [grp[col].values for _, grp in aligned.groupby(target_column) if len(grp) >= 1]
                if len(groups) < 2:
                    associations.append({
                        "column": col, "column_type": "numeric",
                        "test_name": "Kruskal-Wallis H-test",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' has fewer than 2 target groups.",
                    })
                    continue

                try:
                    h_stat, p_val = stats.kruskal(*groups)
                except Exception:
                    h_stat, p_val = None, None

                # Epsilon-squared as effect size: H / (n - 1)
                n = len(aligned)
                eps_sq = float(h_stat / (n - 1)) if h_stat is not None and n > 1 else None

                s = _strength(eps_sq)
                h_str = f"{h_stat:.2f}" if h_stat is not None else "N/A"
                p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
                eps_str = f"{eps_sq:.3f}" if eps_sq is not None else "N/A"
                insight = (
                    f"Kruskal-Wallis test for '{col}' across '{target_column}' classes: "
                    f"H = {h_str}, p = {p_str}, "
                    f"ε² = {eps_str} ({s} effect)."
                    if h_stat is not None and p_val is not None and eps_sq is not None
                    else f"Could not compute Kruskal-Wallis for '{col}'."
                )

                associations.append({
                    "column": col,
                    "column_type": "numeric",
                    "test_name": "Kruskal-Wallis H-test",
                    "statistic": to_json_value(h_stat),
                    "p_value": to_json_value(p_val),
                    "effect_size": to_json_value(eps_sq),
                    "strength": s,
                    "insight": insight,
                })

                # Chart: grouped box plot for top 6 features
                if col in top_kw:
                    box_data = {}
                    for cls_val, grp in aligned.groupby(target_column):
                        vals = grp[col].dropna()
                        if vals.empty:
                            continue
                        box_data[str(cls_val)] = {
                            "min": to_json_value(vals.min()),
                            "q1": to_json_value(vals.quantile(0.25)),
                            "median": to_json_value(vals.median()),
                            "q3": to_json_value(vals.quantile(0.75)),
                            "max": to_json_value(vals.max()),
                        }

                    bivariate_charts.append({
                        "chart_type": "grouped_box",
                        "chart_config": {
                            "title": f"{col} by {target_column}",
                            "x_label": target_column,
                            "y_label": col,
                        },
                        "chart_data": {"groups": box_data},
                        "feature_column": col,
                        "insight": f"Distribution of '{col}' across '{target_column}' classes.",
                    })

        # CASE 4: Categorical target + Categorical feature
        if target_type == "categorical":
            for col in categorical_features:
                n_unique = df[col].nunique()
                if n_unique > 15 or n_unique < 2:
                    associations.append({
                        "column": col, "column_type": column_types[col],
                        "test_name": "Chi-Square / Cramér's V",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Column '{col}' skipped: {'too many' if n_unique > 15 else 'fewer than 2'} unique values ({n_unique}).",
                    })
                    continue

                aligned = df[[target_column, col]].dropna()
                if aligned.empty:
                    associations.append({
                        "column": col, "column_type": column_types[col],
                        "test_name": "Chi-Square / Cramér's V",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"No overlapping non-null data for '{col}' and '{target_column}'.",
                    })
                    continue

                contingency = pd.crosstab(aligned[target_column], aligned[col])
                if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                    associations.append({
                        "column": col, "column_type": column_types[col],
                        "test_name": "Chi-Square / Cramér's V",
                        "statistic": None, "p_value": None, "effect_size": None,
                        "strength": "none",
                        "insight": f"Contingency table for '{col}' is degenerate (fewer than 2 rows or columns).",
                    })
                    continue

                try:
                    chi2, p_val, dof, _ = stats.chi2_contingency(contingency)
                except Exception:
                    chi2, p_val, dof = None, None, None

                # Cramér's V = sqrt(chi2 / (n * (min(r, c) - 1)))
                cramers_v = None
                if chi2 is not None:
                    n = contingency.values.sum()
                    min_dim = min(contingency.shape[0], contingency.shape[1]) - 1
                    cramers_v = float(np.sqrt(chi2 / (n * min_dim))) if n > 0 and min_dim > 0 else 0.0

                s = _strength(cramers_v)
                chi_str = f"{chi2:.2f}" if chi2 is not None else "N/A"
                p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
                v_str = f"{cramers_v:.3f}" if cramers_v is not None else "N/A"
                insight = (
                    f"Chi-Square test between '{col}' and '{target_column}': "
                    f"χ² = {chi_str}, p = {p_str}, "
                    f"Cramér's V = {v_str} ({s} association)."
                    if chi2 is not None and p_val is not None and cramers_v is not None
                    else f"Could not compute Chi-Square for '{col}' vs '{target_column}'."
                )

                associations.append({
                    "column": col,
                    "column_type": column_types[col],
                    "test_name": "Chi-Square / Cramér's V",
                    "statistic": to_json_value(chi2),
                    "p_value": to_json_value(p_val),
                    "effect_size": to_json_value(cramers_v),
                    "strength": s,
                    "insight": insight,
                })

                # Chart: grouped bar (contingency counts)
                bar_data: dict[str, dict[str, int]] = {}
                for target_val in contingency.index:
                    bar_data[str(target_val)] = {
                        str(feat_val): int(contingency.loc[target_val, feat_val])
                        for feat_val in contingency.columns
                    }

                bivariate_charts.append({
                    "chart_type": "grouped_bar",
                    "chart_config": {
                        "title": f"{col} vs {target_column}",
                        "x_label": col,
                        "y_label": "Count",
                    },
                    "chart_data": {"groups": bar_data, "categories": [str(c) for c in contingency.columns]},
                    "feature_column": col,
                    "insight": f"Contingency counts of '{col}' across '{target_column}' classes.",
                })

        return {
            "target_column": target_column,
            "target_type": target_type,
            "associations": associations,
            "bivariate_charts": bivariate_charts,
        }
