"""API tests for AutoML experiments and model evaluation."""

import io
from pathlib import Path

import numpy as np
import pytest
from httpx import AsyncClient


def _csv(n: int = 90) -> bytes:
    rng = np.random.default_rng(1)
    lines = ["customer_id,age,plan,monthly_bill,churned"]
    for i in range(n):
        age = int(rng.integers(18, 70))
        plan = ["basic", "standard", "premium"][i % 3]
        bill = round(float(rng.normal(60, 15)), 2)
        churned = "yes" if (bill > 60) ^ (rng.random() < 0.1) else "no"
        lines.append(f"{i + 1},{age},{plan},{bill},{churned}")
    return "\n".join(lines).encode()


async def _auth(client: AsyncClient, name: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": f"{name}@example.com", "username": name, "password": "Test@1234"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _upload(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/datasets/upload",
        files={"file": ("customers.csv", io.BytesIO(_csv()), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _train(client: AsyncClient, headers: dict, dataset_id: str, **overrides):
    body = {
        "dataset_id": dataset_id,
        "target_column": "churned",
        "algorithms": ["logistic_regression", "random_forest"],
        "cv_folds": 3,
        **overrides,
    }
    return await client.post("/api/v1/experiments/", json=body, headers=headers)


@pytest.mark.asyncio
async def test_recommend_detects_task_and_algorithms(client: AsyncClient):
    headers = await _auth(client, "rec_user")
    dataset_id = await _upload(client, headers)

    resp = await client.get(
        "/api/v1/experiments/recommend",
        params={"dataset_id": dataset_id, "target_column": "churned"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["task_type"] == "binary_classification"
    assert data["default_metric"] == "f1_weighted"
    assert set(data["target_preview"]) == {"yes", "no"}
    assert any(a["key"] == "random_forest" and a["recommended"] for a in data["algorithms"])

    resp = await client.get(
        "/api/v1/experiments/recommend",
        params={"dataset_id": dataset_id, "target_column": "monthly_bill"},
        headers=headers,
    )
    assert resp.json()["task_type"] == "regression"


@pytest.mark.asyncio
async def test_full_experiment_lifecycle(client: AsyncClient):
    """Train → leaderboard → evaluation → predict → download → delete."""
    headers = await _auth(client, "life_user")
    dataset_id = await _upload(client, headers)

    resp = await _train(client, headers, dataset_id, name="Churn baseline")
    assert resp.status_code == 201, resp.text
    exp = resp.json()
    assert exp["status"] == "completed"
    assert exp["name"] == "Churn baseline"
    assert exp["task_type"] == "binary_classification"
    assert exp["model_count"] == 2
    assert exp["best_model_id"]
    assert exp["summary"]["dropped_columns"][0]["column"] == "customer_id"
    ranks = [m["rank"] for m in exp["models"]]
    assert ranks == [1, 2]  # leaderboard is returned in rank order
    best_id = exp["best_model_id"]

    # List + detail
    listed = (await client.get("/api/v1/experiments/", headers=headers)).json()
    assert [e["id"] for e in listed] == [exp["id"]]
    assert listed[0]["dataset_name"] == "customers.csv"
    detail = (await client.get(f"/api/v1/experiments/{exp['id']}", headers=headers)).json()
    assert detail["models"][0]["id"] == best_id

    # Evaluation of the best model
    resp = await client.get(f"/api/v1/experiments/{exp['id']}/models/{best_id}", headers=headers)
    assert resp.status_code == 200
    model = resp.json()
    assert model["is_best"] and model["has_artifact"]
    assert {"confusion_matrix", "roc_curves", "pr_curves", "feature_importance", "per_class"} <= set(model["evaluation"])

    # Prediction from raw values
    resp = await client.post(
        f"/api/v1/experiments/{exp['id']}/models/{best_id}/predict",
        json={"rows": [{"age": 30, "plan": "premium", "monthly_bill": 95.0}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    pred = resp.json()["predictions"][0]
    assert pred["prediction"] in {"yes", "no"}

    # Download the trained pipeline
    resp = await client.get(f"/api/v1/experiments/{exp['id']}/models/{best_id}/download", headers=headers)
    assert resp.status_code == 200
    assert len(resp.content) > 100
    assert ".joblib" in resp.headers["content-disposition"]

    # Dashboard now counts the trained models
    summary = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()
    assert summary["models_count"] == 2

    # Delete removes the record (file cleanup is covered by its own test)
    resp = await client.delete(f"/api/v1/experiments/{exp['id']}", headers=headers)
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/experiments/{exp['id']}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_experiment_artifacts_removed_on_delete(client: AsyncClient, tmp_path):
    from app.config import get_settings

    headers = await _auth(client, "files_user")
    dataset_id = await _upload(client, headers)
    exp = (await _train(client, headers, dataset_id, algorithms=["logistic_regression"])).json()

    exp_dir = Path(get_settings().MODELS_DIR) / exp["id"]
    assert any(exp_dir.glob("*.joblib"))

    await client.delete(f"/api/v1/experiments/{exp['id']}", headers=headers)
    assert not exp_dir.exists()


@pytest.mark.asyncio
async def test_deleting_dataset_cascades_to_experiments(client: AsyncClient):
    from app.config import get_settings

    headers = await _auth(client, "cascade_user")
    dataset_id = await _upload(client, headers)
    exp = (await _train(client, headers, dataset_id, algorithms=["logistic_regression"])).json()
    exp_dir = Path(get_settings().MODELS_DIR) / exp["id"]

    resp = await client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert resp.status_code == 204, resp.text
    assert (await client.get(f"/api/v1/experiments/{exp['id']}", headers=headers)).status_code == 404
    assert not exp_dir.exists()


@pytest.mark.asyncio
async def test_regression_experiment(client: AsyncClient):
    headers = await _auth(client, "reg_user")
    dataset_id = await _upload(client, headers)
    resp = await _train(
        client, headers, dataset_id,
        target_column="monthly_bill", algorithms=["ridge", "random_forest"], optimize_metric="mae",
    )
    assert resp.status_code == 201, resp.text
    exp = resp.json()
    assert exp["task_type"] == "regression"
    assert exp["lower_is_better"] is True
    assert exp["metric_label"] == "MAE"
    best = exp["models"][0]
    assert {"mae", "rmse", "r2"} <= set(best["metrics"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides, expected_status",
    [
        ({"target_column": "missing_col"}, 400),
        ({"algorithms": ["ridge"]}, 400),          # regression-only algorithm on a classification target
        ({"algorithms": ["not_a_model"]}, 400),
        ({"optimize_metric": "rmse"}, 400),        # regression metric on a classification target
        ({"cv_folds": 1}, 422),
        ({"test_size": 0.9}, 422),
    ],
)
async def test_invalid_requests_are_rejected(client: AsyncClient, overrides, expected_status):
    headers = await _auth(client, f"bad_{abs(hash(str(overrides))) % 10_000}")
    dataset_id = await _upload(client, headers)
    resp = await _train(client, headers, dataset_id, **overrides)
    assert resp.status_code == expected_status, resp.text
    # Nothing is stored for rejected requests
    assert (await client.get("/api/v1/experiments/", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_users_cannot_access_each_others_experiments(client: AsyncClient):
    owner = await _auth(client, "owner_user")
    other = await _auth(client, "other_user")
    dataset_id = await _upload(client, owner)
    exp = (await _train(client, owner, dataset_id, algorithms=["logistic_regression"])).json()
    model_id = exp["best_model_id"]

    assert (await client.get(f"/api/v1/experiments/{exp['id']}", headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/experiments/{exp['id']}/models/{model_id}/download", headers=other)).status_code == 404
    assert (await client.delete(f"/api/v1/experiments/{exp['id']}", headers=other)).status_code == 404
    assert (await _train(client, other, dataset_id)).status_code == 404  # cannot train on someone else's dataset
    assert (await client.get("/api/v1/experiments/", headers=other)).json() == []


@pytest.mark.asyncio
async def test_experiments_require_auth(client: AsyncClient):
    assert (await client.get("/api/v1/experiments/")).status_code == 401


@pytest.mark.asyncio
async def test_experiment_pages_render(client: AsyncClient):
    assert (await client.get("/experiments")).status_code == 200
    assert (await client.get("/experiments/00000000-0000-0000-0000-000000000000")).status_code == 200
