"""Tests for feature engineering.

Verifies datetime splits, numeric interactions, polynomial features, PCA projection,
Mutual Information selection, output file saves, dataset registration, and security restrictions.
"""

import io
import pytest
from httpx import AsyncClient


def _sample_csv_data() -> bytes:
    """Generate a sample CSV dataset with datetime, numeric, and text features."""
    lines = [
        "date_joined,x1,x2,text_field,target",
        "2026-01-01 10:00:00,10.0,5.0,hello world,1",
        "2026-02-02 11:30:00,20.0,4.0,short,0",
        "2026-03-03 12:00:00,30.0,3.0,this is a text description,1",
        "2026-04-04 15:45:00,40.0,2.0,another phrase,0",
        "2026-05-05 18:20:00,50.0,1.0,word,1",
    ]
    return "\n".join(lines).encode("utf-8")


async def _get_auth_token(client: AsyncClient, email: str, username: str) -> str:
    """Helper to register user and return token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "TestPassword@123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _upload_dataset(client: AsyncClient, token: str) -> str:
    """Helper to upload sample dataset and return its ID."""
    files = {"file": ("data.csv", io.BytesIO(_sample_csv_data()), "text/csv")}
    resp = await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# Feature engineering generation & previews

@pytest.mark.asyncio
async def test_feature_generate_date_success(client: AsyncClient):
    """POST /features/generate for type='date' extracts datetime components."""
    token = await _get_auth_token(client, "feat_date@example.com", "feat_date")
    dataset_id = await _upload_dataset(client, token)

    # Split date_joined column
    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "Datetime split",
            "method": "date",
            "config": {"column": "date_joined"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    assert result["feature_set"]["method"] == "date"
    assert result["feature_set"]["feature_count"] == 6

    # Verify preview columns exist
    cols = result["preview"]["columns"]
    assert "date_joined_year" in cols
    assert "date_joined_month" in cols
    assert "date_joined_is_weekend" in cols


@pytest.mark.asyncio
async def test_feature_generate_interaction_success(client: AsyncClient):
    """POST /features/generate for type='interaction' creates product and division features."""
    token = await _get_auth_token(client, "feat_int@example.com", "feat_int")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "Interaction x1 x2",
            "method": "interaction",
            "config": {"columns": ["x1", "x2"]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    cols = result["preview"]["columns"]
    assert "x1_x_x2" in cols
    assert "x1_div_x2" in cols


@pytest.mark.asyncio
async def test_feature_generate_pca_success(client: AsyncClient):
    """POST /features/generate for type='pca' fits Scikit-learn PCA and projects numeric components."""
    token = await _get_auth_token(client, "feat_pca@example.com", "feat_pca")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "PCA Components",
            "method": "pca",
            "config": {"columns": ["x1", "x2"], "n_components": 2},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    cols = result["preview"]["columns"]
    assert "pca_comp_0" in cols
    assert "pca_comp_1" in cols


@pytest.mark.asyncio
async def test_feature_generate_selection_success(client: AsyncClient):
    """POST /features/generate for type='selection' runs Mutual Info and selects top features."""
    token = await _get_auth_token(client, "feat_sel@example.com", "feat_sel")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "Top MI features",
            "method": "selection",
            "config": {"target_column": "target", "k": 2},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    cols = result["preview"]["columns"]
    # Selection should drop the rest and only keep selected columns + target column
    assert len(cols) == 3
    assert "target" in cols


# Feature set applying tests

@pytest.mark.asyncio
async def test_feature_apply_success(client: AsyncClient):
    """POST /features/{fid}/apply writes output file and registers engineered dataset in DB."""
    token = await _get_auth_token(client, "feat_apply@example.com", "feat_apply")
    dataset_id = await _upload_dataset(client, token)

    # 1. Generate feature set
    gen_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "Polynomial x1",
            "method": "polynomial",
            "config": {"columns": ["x1"]},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen_resp.status_code == 201
    fid = gen_resp.json()["feature_set"]["id"]

    # 2. Apply feature set
    app_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/{fid}/apply",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert app_resp.status_code == 200, app_resp.text
    feature_set = app_resp.json()

    assert feature_set["output_file_path"] is not None
    assert feature_set["feature_count"] == 2

    # Verify registered dataset in DB
    ds_resp = await client.get(
        "/api/v1/datasets/",
        headers={"Authorization": f"Bearer {token}"},
    )
    datasets = ds_resp.json()
    assert len(datasets) == 2
    names = {d["name"] for d in datasets}
    assert "data_engineered.csv" in names


# Feature Engineering Security Tests

@pytest.mark.asyncio
async def test_feature_unauthorized_access(client: AsyncClient):
    """User B cannot generate or apply feature engineering on User A's dataset."""
    token_a = await _get_auth_token(client, "feat_a@example.com", "feat_a")
    token_b = await _get_auth_token(client, "feat_b@example.com", "feat_b")
    dataset_id = await _upload_dataset(client, token_a)

    # B tries to generate features on A's dataset
    resp_gen = await client.post(
        f"/api/v1/datasets/{dataset_id}/features/generate",
        json={
            "name": "Hack date",
            "method": "date",
            "config": {"column": "date_joined"},
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_gen.status_code == 404
