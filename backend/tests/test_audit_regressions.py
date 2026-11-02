"""Regression tests for bugs found during the full-project audit.

Each test names the bug it guards against. Most of them used to produce a
500 error or silently wrong output.
"""

import io

import numpy as np
import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.ml.automl import prepare_data
from app.ml.feature_engineer import FeatureEngineer
from app.ml.preprocessor import KNOWN_ACTIONS, DatasetPreprocessor, PreprocessingError
from app.ml.profiler import DatasetProfiler
from app.ml.quality_analyzer import DataQualityAnalyzer


def _messy_frame(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "signup_date": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "age": rng.integers(18, 80, n).astype(float),
        "tenure": rng.integers(0, 72, n),
        "bill": rng.normal(70, 20, n).round(2),
        "plan": rng.choice(["basic", "premium", "standard"], n),
        "feedback": rng.choice(["good", "bad service", None], n),
        "churn": rng.choice(["yes", "no"], n, p=[0.15, 0.85]),
    })
    df.loc[:9, "age"] = np.nan
    df.loc[:4, "plan"] = None
    df.loc[[3, 7], "bill"] = 5000.0
    return pd.concat([df, df.head(3)], ignore_index=True)


# ── Preprocessing engine ─────────────────────────────────────────────

def test_label_encoding_text_column_does_not_crash():
    """pandas 3 string columns rejected integer codes written in place."""
    df = _messy_frame()
    out, cfg = DatasetPreprocessor.apply(df, [{"action": "encode_label", "column": "plan"}])
    assert pd.api.types.is_integer_dtype(out["plan"])
    assert (out["plan"] == -1).sum() == df["plan"].isna().sum()  # missing values become -1
    assert cfg[next(iter(cfg))]["classes"] == ["basic", "premium", "standard"]


def test_kmeans_binning_on_integer_column():
    out, _ = DatasetPreprocessor.apply(_messy_frame(), [{"action": "discretize_kmeans", "column": "tenure"}])
    assert out["tenure"].nunique() <= 5


def test_random_imputation_on_text_column():
    out, _ = DatasetPreprocessor.apply(_messy_frame(), [{"action": "impute_random", "column": "plan"}])
    assert out["plan"].isna().sum() == 0
    assert set(out["plan"]) <= {"basic", "premium", "standard"}


@pytest.mark.parametrize("action", ["impute_knn", "impute_iterative"])
def test_knn_and_mice_use_other_columns(action):
    """Both used to ignore other columns (MICE was actually a median fill)."""
    df = _messy_frame()
    out, cfg = DatasetPreprocessor.apply(df, [{"action": action, "column": "age"}])
    step = cfg[next(iter(cfg))]
    assert out["age"].isna().sum() == 0
    assert "tenure" in step["predictor_columns"]
    # Imputed values vary by row instead of being one constant
    assert out.loc[:9, "age"].nunique() > 1


@pytest.mark.parametrize(
    "step, message",
    [
        ({"action": "not_real", "column": "age"}, "unknown preprocessing action"),
        ({"action": "impute_mean", "column": "missing_col"}, "column not found"),
        ({"action": "scale_standard", "column": "plan"}, "needs a numeric column"),
        ({"action": "impute_mean"}, "a column is required"),
    ],
)
def test_invalid_steps_raise_clear_errors(step, message):
    """These used to be silently skipped or crash with a 500."""
    with pytest.raises(PreprocessingError, match=message):
        DatasetPreprocessor.apply(_messy_frame(), [step])


def test_every_quality_recommendation_is_a_real_preprocessing_action():
    """Recommendations used to include actions the preprocessor didn't implement."""
    df = _messy_frame()
    profile = DatasetProfiler.profile(df)
    recs = DataQualityAnalyzer.analyze(df, profile["column_types"])["recommendations"]
    actions = {r["recommended_action"] for r in recs}
    assert actions, "expected some recommendations for messy data"
    assert actions <= KNOWN_ACTIONS
    steps = [{"action": r["recommended_action"], "column": r["column"]} for r in recs]
    out, _ = DatasetPreprocessor.apply(df, steps)  # applying them all must work
    assert len(out) > 0


# ── Feature engineering ──────────────────────────────────────────────

def test_text_features_treat_missing_as_empty():
    """Missing text was counted as the 3-letter word 'nan'."""
    df = pd.DataFrame({"t": ["hello world", None]})
    out, _ = FeatureEngineer.generate_features(df, "text", {"column": "t"})
    assert out.loc[1, "t_char_len"] == 0 and out.loc[1, "t_word_count"] == 0


def test_feature_selection_ignores_id_columns_and_records_target():
    df = _messy_frame()
    out, features = FeatureEngineer.generate_features(df, "selection", {"target_column": "churn", "k": 3})
    names = [f["name"] for f in features]
    assert "customer_id" not in names
    assert all(f["target_column"] == "churn" for f in features)


# ── AutoML ───────────────────────────────────────────────────────────

def test_automl_explains_date_columns():
    data = prepare_data(_messy_frame(), "churn")
    reasons = {d["column"]: d["reason"] for d in data.dropped_columns}
    assert "Date column" in reasons["signup_date"]
    assert "customer_id" in reasons


# ── API flows ────────────────────────────────────────────────────────

async def _setup(client: AsyncClient, name: str, frame: pd.DataFrame | None = None):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": f"{name}@example.com", "username": name, "password": "Test@1234"},
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    buf = io.BytesIO((frame if frame is not None else _messy_frame()).to_csv(index=False).encode())
    up = await client.post("/api/v1/datasets/upload", files={"file": ("messy.csv", buf, "text/csv")}, headers=headers)
    assert up.status_code == 201, up.text
    return headers, up.json()["id"]


@pytest.mark.asyncio
async def test_bad_preprocessing_step_returns_400_not_500(client: AsyncClient):
    headers, ds = await _setup(client, "prep400")
    resp = await client.post(
        f"/api/v1/datasets/{ds}/preprocess/preview",
        json={"steps": [{"action": "scale_standard", "column": "plan"}]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "numeric" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dataset_with_eda_features_and_pipelines_can_be_deleted(client: AsyncClient):
    """Deleting a dataset with child records used to fail with an IntegrityError (500)."""
    headers, ds = await _setup(client, "cascade_all")
    assert (await client.post(f"/api/v1/datasets/{ds}/eda/generate", headers=headers)).status_code == 201
    fs = await client.post(
        f"/api/v1/datasets/{ds}/features/generate",
        json={"name": "poly", "method": "polynomial", "config": {"columns": ["age"]}},
        headers=headers,
    )
    assert fs.status_code == 201
    pipe = await client.post(
        f"/api/v1/datasets/{ds}/preprocess/apply",
        json={"name": "p", "steps": [{"action": "drop_duplicates"}]},
        headers=headers,
    )
    assert pipe.status_code == 201

    resp = await client.delete(f"/api/v1/datasets/{ds}", headers=headers)
    assert resp.status_code == 204, resp.text
    assert (await client.get(f"/api/v1/datasets/{ds}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_polynomial_apply_uses_every_selected_column(client: AsyncClient):
    """Apply used to rebuild the config from the first feature only."""
    headers, ds = await _setup(client, "poly_apply")
    gen = await client.post(
        f"/api/v1/datasets/{ds}/features/generate",
        json={"name": "poly2", "method": "polynomial", "config": {"columns": ["age", "tenure"]}},
        headers=headers,
    )
    fs_id = gen.json()["feature_set"]["id"]
    assert (await client.post(f"/api/v1/datasets/{ds}/features/{fs_id}/apply", headers=headers)).status_code == 200

    engineered = [d for d in (await client.get("/api/v1/datasets/", headers=headers)).json() if d["name"].endswith("_engineered.csv")]
    cols = engineered[0]["column_names"]
    assert {"age_squared", "age_cubed", "tenure_squared", "tenure_cubed"} <= set(cols)


@pytest.mark.asyncio
async def test_selection_apply_keeps_target_even_if_not_last_column(client: AsyncClient):
    """Apply used to assume the target was the dataset's last column."""
    frame = _messy_frame()
    frame = frame[["churn"] + [c for c in frame.columns if c != "churn"]]  # target first
    headers, ds = await _setup(client, "sel_apply", frame)
    gen = await client.post(
        f"/api/v1/datasets/{ds}/features/generate",
        json={"name": "sel", "method": "selection", "config": {"target_column": "churn", "k": 2}},
        headers=headers,
    )
    assert gen.status_code == 201, gen.text
    fs_id = gen.json()["feature_set"]["id"]
    assert (await client.post(f"/api/v1/datasets/{ds}/features/{fs_id}/apply", headers=headers)).status_code == 200

    engineered = [d for d in (await client.get("/api/v1/datasets/", headers=headers)).json() if d["name"].endswith("_engineered.csv")]
    cols = engineered[0]["column_names"]
    assert "churn" in cols and len(cols) == 3


@pytest.mark.asyncio
async def test_unexpected_errors_return_json(client: AsyncClient, monkeypatch):
    """Unhandled exceptions used to return plain text / drop the connection."""
    from app.main import app
    from app.services import dataset_service

    async def boom(self, user_id):
        raise RuntimeError("simulated failure")

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "boom@example.com", "username": "boomuser", "password": "Test@1234"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    monkeypatch.setattr(dataset_service.DatasetService, "list_datasets", boom)

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as raw:
        resp = await raw.get("/api/v1/datasets/", headers=headers)
    assert resp.status_code == 500
    assert "detail" in resp.json()


# ── Settings: change password (was a fake "demo mode" form) ──────────

@pytest.mark.asyncio
async def test_change_password_rotates_sessions(client: AsyncClient):
    import re

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "chpw@example.com", "username": "chpw", "password": "Test@1234"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    login = await client.post("/api/v1/auth/login", json={"username_or_email": "chpw", "password": "Test@1234"})
    old_refresh = re.search(r"refresh_token=([^;]+)", login.headers["set-cookie"]).group(1)

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Test@1234", "new_password": "Newer@5678"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json() and "refresh_token=" in resp.headers["set-cookie"]

    # Old password and old sessions no longer work; the new password does
    assert (await client.post("/api/v1/auth/login", json={"username_or_email": "chpw", "password": "Test@1234"})).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"username_or_email": "chpw", "password": "Newer@5678"})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body, status",
    [
        ({"current_password": "Wrong@1234", "new_password": "Newer@5678"}, 400),
        ({"current_password": "Test@1234", "new_password": "Test@1234"}, 400),   # unchanged
        ({"current_password": "Test@1234", "new_password": "weakpassword"}, 422),
    ],
)
async def test_change_password_rejects_bad_input(client: AsyncClient, body, status):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": f"bad{status}{len(body['new_password'])}@example.com", "username": f"bad{status}{len(body['new_password'])}", "password": "Test@1234"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.post("/api/v1/auth/change-password", json=body, headers=headers)
    assert resp.status_code == status, resp.text


@pytest.mark.asyncio
async def test_dashboard_counts_experiments(client: AsyncClient):
    headers, ds = await _setup(client, "dash_counts")
    exp = await client.post(
        "/api/v1/experiments/",
        json={"dataset_id": ds, "target_column": "churn", "algorithms": ["logistic_regression"], "cv_folds": 3},
        headers=headers,
    )
    assert exp.status_code == 201, exp.text
    summary = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()
    assert summary["experiments_count"] == 1 and summary["models_count"] == 1
