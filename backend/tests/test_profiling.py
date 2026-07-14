"""Tests for dataset profiling endpoints (Phase 5).

Verifies type detection, Descriptive Statistics, duplicate rows,
null counts, access control, and retrieval endpoints.
"""

import io
import uuid

import pytest
from httpx import AsyncClient


def _sample_csv_content() -> bytes:
    """Generate a sample CSV dataset with multiple datatypes and nulls."""
    lines = [
        "age,salary,gender,is_active,joined_date",
        "25,50000.50,M,True,2021-01-01",
        "30,60000.00,F,False,2022-06-15",
        ",70000.75,F,True,2023-09-20",  # age is null
        "40,80000.00,M,True,",           # joined_date is null
        "25,50000.50,M,True,2021-01-01",  # duplicate row
    ]
    return "\n".join(lines).encode("utf-8")


async def _get_auth_token(client: AsyncClient, email: str, username: str) -> str:
    """Helper to register a user and get auth token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "TestPassword@123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _upload_dataset(client: AsyncClient, token: str, filename: str = "sample.csv") -> str:
    """Helper to upload a sample dataset and return its ID."""
    files = {"file": (filename, io.BytesIO(_sample_csv_content()), "text/csv")}
    resp = await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Ingestion & Profiling Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_profiling_success(client: AsyncClient):
    """POST /datasets/{id}/profile successfully profiles dataset and extracts stats."""
    token = await _get_auth_token(client, "profiler@example.com", "profiler_user")
    dataset_id = await _upload_dataset(client, token)

    # Trigger profiling
    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    # Verify response structure
    assert result["dataset_id"] == dataset_id
    assert result["total_rows"] == 5
    assert result["total_columns"] == 5
    assert result["duplicate_row_count"] == 1  # 1 duplicate row (row 5 is duplicate of row 1)

    # Verify column type classifications
    types = result["column_types"]
    assert types["age"] == "numeric"
    assert types["salary"] == "numeric"
    assert types["gender"] == "boolean" or types["gender"] == "categorical"  # M/F
    assert types["is_active"] == "boolean"
    assert types["joined_date"] == "datetime"

    # Verify null/missing counts
    nulls = result["null_counts"]
    assert nulls["age"] == 1          # Row 3 is null
    assert nulls["joined_date"] == 1   # Row 4 is null
    assert nulls["salary"] == 0

    # Verify descriptive statistics
    stats = result["descriptive_stats"]
    assert "mean" in stats["salary"]
    assert "min" in stats["salary"]
    assert "max" in stats["salary"]
    assert stats["salary"]["min"] == 50000.5
    assert stats["salary"]["max"] == 80000.0


@pytest.mark.asyncio
async def test_get_profiling_results_success(client: AsyncClient):
    """GET /datasets/{id}/profile returns previously computed results."""
    token = await _get_auth_token(client, "profile_get@example.com", "profile_get_user")
    dataset_id = await _upload_dataset(client, token)

    # 1. Fetching profile before computation returns 404
    get_resp_before = await client.get(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp_before.status_code == 404

    # 2. Trigger profiling
    post_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_resp.status_code == 201

    # 3. Retrieve profile results
    get_resp_after = await client.get(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp_after.status_code == 200
    assert get_resp_after.json()["total_rows"] == 5


@pytest.mark.asyncio
async def test_profiling_unauthorized_access(client: AsyncClient):
    """User cannot profile or retrieve results of another user's dataset."""
    token_a = await _get_auth_token(client, "usera@example.com", "usera")
    token_b = await _get_auth_token(client, "userb@example.com", "userb")
    
    # User A uploads dataset
    dataset_id = await _upload_dataset(client, token_a)

    # User B tries to profile User A's dataset
    resp_post = await client.post(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_post.status_code == 404

    # User B tries to get User A's dataset profile
    resp_get = await client.get(
        f"/api/v1/datasets/{dataset_id}/profile",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_get.status_code == 404


@pytest.mark.asyncio
async def test_profiling_nonexistent_dataset(client: AsyncClient):
    """Triggering profile on non-existent dataset returns 404."""
    token = await _get_auth_token(client, "usernonexist@example.com", "usernonexist")
    fake_uuid = str(uuid.uuid4())
    
    resp = await client.post(
        f"/api/v1/datasets/{fake_uuid}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
