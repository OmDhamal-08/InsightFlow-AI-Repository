"""ML feature engineering engine.

Performs datetime splitting, numerical interactions, polynomial additions,
text metrics extraction, PCA projections, and Mutual Information feature selection.
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif


class FeatureEngineer:
    """Generates and applies feature engineering transformations to a DataFrame."""

    @classmethod
    def generate_features(cls, df: pd.DataFrame, method: str, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        """Run feature engineering on a copy of the dataframe.

        Args:
            df: The DataFrame.
            method: 'date', 'interaction', 'polynomial', 'text', 'pca', 'selection'.
            config: Parameters dictionary (e.g. columns list, target column, n_components).

        Returns:
            The modified DataFrame and a list of engineered feature definitions.
        """
        df = df.copy()
        new_features = []

        if method == "date":
            df, new_features = cls._apply_date_features(df, config)
        elif method == "interaction":
            df, new_features = cls._apply_interaction_features(df, config)
        elif method == "polynomial":
            df, new_features = cls._apply_polynomial_features(df, config)
        elif method == "text":
            df, new_features = cls._apply_text_features(df, config)
        elif method == "pca":
            df, new_features = cls._apply_pca_features(df, config)
        elif method == "selection":
            df, new_features = cls._apply_feature_selection(df, config)

        return df, new_features

    # ── 1. Date Splitting ─────────────────────────────────────────
    @classmethod
    def _apply_date_features(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        col = config.get("column")
        if not col or col not in df.columns:
            return df, []

        new_features = []
        try:
            dt_series = pd.to_datetime(df[col], errors="coerce")
            
            # Extract features
            df[f"{col}_year"] = dt_series.dt.year.fillna(-1).astype(int)
            df[f"{col}_month"] = dt_series.dt.month.fillna(-1).astype(int)
            df[f"{col}_day"] = dt_series.dt.day.fillna(-1).astype(int)
            df[f"{col}_dayofweek"] = dt_series.dt.dayofweek.fillna(-1).astype(int)
            df[f"{col}_hour"] = dt_series.dt.hour.fillna(-1).astype(int)
            df[f"{col}_is_weekend"] = (dt_series.dt.dayofweek >= 5).astype(int)

            new_cols = [
                f"{col}_year", f"{col}_month", f"{col}_day", 
                f"{col}_dayofweek", f"{col}_hour", f"{col}_is_weekend"
            ]
            for nc in new_cols:
                new_features.append({
                    "name": nc,
                    "parent_columns": [col],
                    "formula": f"datetime_extract({nc.split('_')[-1]})",
                })
        except Exception:
            pass

        return df, new_features

    # ── 2. Interaction Features ──────────────────────────────────
    @classmethod
    def _apply_interaction_features(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        cols = config.get("columns", [])
        if len(cols) != 2:
            return df, []

        c1, c2 = cols[0], cols[1]
        if c1 not in df.columns or c2 not in df.columns:
            return df, []

        new_features = []
        
        # Product: c1 * c2
        prod_name = f"{c1}_x_{c2}"
        df[prod_name] = df[c1] * df[c2]
        new_features.append({
            "name": prod_name,
            "parent_columns": [c1, c2],
            "formula": f"{c1} * {c2}",
        })

        # Ratio: c1 / c2
        ratio_name = f"{c1}_div_{c2}"
        df[ratio_name] = df[c1] / (df[c2] + 1e-5)
        new_features.append({
            "name": ratio_name,
            "parent_columns": [c1, c2],
            "formula": f"{c1} / {c2}",
        })

        return df, new_features

    # ── 3. Polynomial Features ───────────────────────────────────
    @classmethod
    def _apply_polynomial_features(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        cols = config.get("columns", [])
        new_features = []

        for col in cols:
            if col not in df.columns:
                continue
            
            # Squared
            sq_name = f"{col}_squared"
            df[sq_name] = df[col] ** 2
            new_features.append({
                "name": sq_name,
                "parent_columns": [col],
                "formula": f"{col}^2",
            })

            # Cubed
            cube_name = f"{col}_cubed"
            df[cube_name] = df[col] ** 3
            new_features.append({
                "name": cube_name,
                "parent_columns": [col],
                "formula": f"{col}^3",
            })

        return df, new_features

    # ── 4. Text Length Features ──────────────────────────────────
    @classmethod
    def _apply_text_features(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        col = config.get("column")
        if not col or col not in df.columns:
            return df, []

        new_features = []
        str_series = df[col].astype(str).fillna("")

        # Character length
        char_name = f"{col}_char_len"
        df[char_name] = str_series.apply(len)
        new_features.append({
            "name": char_name,
            "parent_columns": [col],
            "formula": "char_length",
        })

        # Word count
        word_name = f"{col}_word_count"
        df[word_name] = str_series.apply(lambda s: len(s.split()))
        new_features.append({
            "name": word_name,
            "parent_columns": [col],
            "formula": "word_count",
        })

        return df, new_features

    # ── 5. PCA Projections ───────────────────────────────────────
    @classmethod
    def _apply_pca_features(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        cols = config.get("columns", [])
        n_components = int(config.get("n_components", 2))
        
        valid_cols = [c for c in cols if c in df.columns]
        if len(valid_cols) < n_components or n_components < 1:
            return df, []

        new_features = []
        try:
            # Impute and standardize
            sub_df = df[valid_cols].copy()
            for col in valid_cols:
                sub_df[col] = sub_df[col].fillna(sub_df[col].median())
            
            # Scale features
            scaled = StandardScaler().fit_transform(sub_df.values)
            
            # Fit PCA
            pca = PCA(n_components=n_components)
            projected = pca.fit_transform(scaled)

            for i in range(n_components):
                pca_name = f"pca_comp_{i}"
                df[pca_name] = projected[:, i]
                new_features.append({
                    "name": pca_name,
                    "parent_columns": valid_cols,
                    "formula": f"PCA principal component {i} (explained variance: {float(pca.explained_variance_ratio_[i]):.4f})",
                })
        except Exception:
            pass

        return df, new_features

    # ── 6. Feature Selection (Mutual Information) ────────────────
    @classmethod
    def _apply_feature_selection(cls, df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
        target_col = config.get("target_column")
        k = int(config.get("k", 5))

        if not target_col or target_col not in df.columns:
            return df, []

        new_features = []
        try:
            # Prepare feature matrix X (drop target)
            x_df = df.drop(columns=[target_col]).copy()
            y = df[target_col].copy()

            # Align indices and drop target nulls
            valid_idx = y.dropna().index
            if len(valid_idx) < 5:
                return df, []

            X = x_df.loc[valid_idx]
            y = y.loc[valid_idx]

            # Impute nulls and encode objects in X for MI
            encoded_cols = []
            for col in X.columns:
                if pd.api.types.is_numeric_dtype(X[col]):
                    median_val = X[col].median()
                    X[col] = X[col].fillna(median_val if not pd.isna(median_val) else 0)
                else:
                    # Encode categorical
                    le = LabelEncoder()
                    X[col] = le.fit_transform(X[col].astype(str))
                encoded_cols.append(col)

            # Check if target is numeric to decide regressor vs classifier
            is_numeric_target = pd.api.types.is_numeric_dtype(y)
            if is_numeric_target:
                y = y.fillna(y.median())
                mi_scores = mutual_info_regression(X.values, y.values)
            else:
                le = LabelEncoder()
                y = le.fit_transform(y.astype(str))
                mi_scores = mutual_info_classif(X.values, y)

            # Sort and pick top K
            mi_series = pd.Series(mi_scores, index=X.columns).sort_values(ascending=False)
            top_k_cols = list(mi_series.head(k).index)

            # AI Feature Selection List
            for col in top_k_cols:
                score = float(mi_series[col])
                new_features.append({
                    "name": col,
                    "parent_columns": [col],
                    "formula": f"Selected feature (Mutual Information score: {score:.4f})",
                })

            # Drop other columns, keeping only target and selected K features!
            cols_to_keep = top_k_cols + [target_col]
            df = df[cols_to_keep]

        except Exception:
            pass

        return df, new_features
