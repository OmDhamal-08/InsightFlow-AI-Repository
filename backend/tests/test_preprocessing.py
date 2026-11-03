"""Tests for the preprocessing engine and endpoints.

Verifies preview generations, column-specific imputations, scaling, outlier capping,
column drops, clean CSV output registrations, and access controls.
"""

import io
import os
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient


def _sample_csv_data() -> bytes:
    """Generate a sample CSV dataset with outliers and missing cells."""
    lines = [
        "age,salary,gender,is_active",
        "25,50000.5,M,True",
        "30,60000.0,F,False",
        ",70000.7,F,True",       # age is null
        "999,80000.0,M,True",    # age outlier
        "40,90000.0,M,False",
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


# Preprocessing Preview Tests

@pytest.mark.asyncio
async def test_preprocess_preview_success(client: AsyncClient):
    """POST /datasets/{id}/preprocess/preview applies steps and returns comparative stats."""
    token = await _get_auth_token(client, "prep_prev@example.com", "prev_user")
    dataset_id = await _upload_dataset(client, token)

    # Trigger preview with column drop, outlier cap, median impute, and standard scaling
    steps = [
        {"action": "drop_column", "column": "is_active"},
        {"action": "impute_median", "column": "age"},
        {"action": "outliers_cap", "column": "age"},
        {"action": "scale_standard", "column": "salary"},
    ]

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/preprocess/preview",
        json={"steps": steps},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()

    # Verify shapes comparison
    assert result["before"]["shape"] == [5, 4]
    assert result["after"]["shape"] == [5, 3]  # is_active column dropped

    # Verify age column nulls are imputed
    assert result["before"]["summary"]["age"]["null_count"] == 1
    assert result["after"]["summary"]["age"]["null_count"] == 0

    # Verify age outlier is capped (mean should drop drastically after capping 999)
    assert result["before"]["summary"]["age"]["mean"] > 100
    assert result["after"]["summary"]["age"]["mean"] < 40


# Preprocessing Apply Tests

@pytest.mark.asyncio
async def test_preprocess_apply_success(client: AsyncClient):
    """POST /datasets/{id}/preprocess/apply writes output file and registers processed dataset."""
    token = await _get_auth_token(client, "prep_apply@example.com", "apply_user")
    dataset_id = await _upload_dataset(client, token)

    # Steps: impute mode on gender, mean on age, standard scale salary
    steps = [
        {"action": "impute_mode", "column": "gender"},
        {"action": "impute_mean", "column": "age"},
        {"action": "scale_standard", "column": "salary"},
    ]

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/preprocess/apply",
        json={"name": "Standard Preprocessing Pipeline", "steps": steps},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    pipeline = resp.json()

    # Verify pipeline model registration
    assert pipeline["name"] == "Standard Preprocessing Pipeline"
    assert pipeline["status"] == "applied"
    assert pipeline["output_file_path"] is not None
    assert Path(pipeline["output_file_path"]).exists()

    # Verify new preprocessed dataset exists in DB
    ds_resp = await client.get(
        "/api/v1/datasets/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ds_resp.status_code == 200
    datasets = ds_resp.json()
    
    # We should have 2 datasets now: original 'data.csv' and processed 'data_cleaned.csv'
    assert len(datasets) == 2
    names = {d["name"] for d in datasets}
    assert "data_cleaned.csv" in names

    cleaned_ds = next(d for d in datasets if d["name"] == "data_cleaned.csv")
    assert cleaned_ds["status"] == "processed"
    assert cleaned_ds["row_count"] == 5
    assert cleaned_ds["column_count"] == 4


# Preprocessing Security Tests

@pytest.mark.asyncio
async def test_preprocess_unauthorized_access(client: AsyncClient):
    """User cannot preview or apply preprocessing on another user's dataset."""
    token_a = await _get_auth_token(client, "prep_a@example.com", "prep_a")
    token_b = await _get_auth_token(client, "prep_b@example.com", "prep_b")
    dataset_id = await _upload_dataset(client, token_a)

    # User B tries to preview User A's dataset transformations
    resp_prev = await client.post(
        f"/api/v1/datasets/{dataset_id}/preprocess/preview",
        json={"steps": []},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_prev.status_code == 404

    # User B tries to apply preprocessing pipeline on User A's dataset
    resp_apply = await client.post(
        f"/api/v1/datasets/{dataset_id}/preprocess/apply",
        json={"name": "Hack", "steps": []},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_apply.status_code == 404
