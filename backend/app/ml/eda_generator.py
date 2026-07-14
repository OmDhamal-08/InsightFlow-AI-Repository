"""ML EDA generator engine.

Computes pre-calculated statistical coordinates for summary visualizations (heatmaps,
missing values, distributions) and custom interactive plots (normality tests, boxplots,
QQ-plots, and scatter plots with linear regression lines).
"""

import numpy as np
import pandas as pd
import scipy.stats as stats


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

        # ── 1. Correlation Heatmap ──────────────────────────────────
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
                        [cls._to_json_val(corr_matrix.loc[y, x]) for x in x_labels]
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

        # ── 2. Missing Values Bar Chart ─────────────────────────────
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

        # ── 3. Categorical Counts (Target candidate) ────────────────
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

        # ── 4. Feature Skewness Overview ─────────────────────────────
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
                    insight += f" Highly skewed features (>1.0 or <-1.0) found: {', '.join(highly_skewed[:3])}. We suggest log or Yeo-Johnson transforms (Phase 7)."
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

        # ── 5. Outlier Densities Overview ─────────────────────────────
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

        # ── 6. Categorical Cardinality Overview ───────────────────────
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

        # ── A. Normality & Distribution ─────────────────────────────
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
                insight += f"The column fails the normality test (p-value = {p_value:.4f} <= 0.05), indicating a non-normal/skewed distribution. Applying log, power, or Yeo-Johnson transforms (Phase 7) is recommended before model training."

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

        # ── B. Boxplot & Outliers ───────────────────────────────────
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

        # ── C. Q-Q Plot (Quantile-Quantile) ─────────────────────────
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

        # ── D. Bivariate Scatter Plot with Linear Trend ──────────────
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
    def _to_json_val(cls, val):
        """Convert numpy numeric types to serializable python numbers."""
        if pd.isna(val):
            return None
        if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(val)
        if isinstance(val, (np.floating, np.float64, np.float32)):
            if np.isnan(val) or np.isinf(val):
                return None
            return float(val)
        return val
