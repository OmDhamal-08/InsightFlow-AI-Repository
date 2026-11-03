"""Tests for the data quality engine.

Verifies multidimensional DQI scoring, missing value counts, outliers,
multicollinearity flagging, skewness, class imbalance, and recommendation mappings.
"""

import io
import uuid

import pytest
from httpx import AsyncClient


def _messy_csv_content() -> bytes:
    """Generate a messy CSV dataset for quality testing.

    Includes:
        - age: 1 null, 1 outlier (999)
        - income: highly correlated with income_dup (correlation = 1.0)
        - income_dup: identical to income
        - target: low-cardinality class imbalance (4 A's, 1 B)
        - 1 duplicate row
    """
    lines = [
        "age,income,income_dup,target",
        "25,50000,50000,A",
        "30,60000,60000,A",
        ",70000,70000,A",       # age null
        "999,80000,80000,A",    # age outlier
        "40,90000,90000,B",
        "25,50000,50000,A",     # duplicate row
    ]
    return "\n".join(lines).encode("utf-8")


async def _get_auth_token(client: AsyncClient, email: str, username: str) -> str:
    """Register a user and get auth token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "TestPassword@123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _upload_dataset(client: AsyncClient, token: str) -> str:
    """Upload the messy dataset and return its ID."""
    files = {"file": ("messy.csv", io.BytesIO(_messy_csv_content()), "text/csv")}
    resp = await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# Quality Analysis Tests

@pytest.mark.asyncio
async def test_run_quality_analysis_success(client: AsyncClient):
    """POST /datasets/{id}/quality calculates accurate score and flags issues."""
    token = await _get_auth_token(client, "quality@example.com", "quality_user")
    dataset_id = await _upload_dataset(client, token)

    # Trigger quality audit
    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()

    # Verify basic response structure
    assert result["dataset_id"] == dataset_id
    assert 0.0 <= result["quality_score"] <= 100.0

    # Verify dimension calculations
    assert result["duplicate_report"]["duplicate_count"] == 1
    assert result["missing_value_report"]["age"]["null_count"] == 1

    # Verify outlier count in age
    assert result["outlier_report"]["age"]["outlier_count"] == 1  # 999 is outlier

    # Verify correlation pair detection between income and income_dup
    corr = result["correlation_report"]
    pairs = corr["high_correlation_pairs"]
    assert len(pairs) >= 1
    assert {pairs[0]["col1"], pairs[0]["col2"]} == {"income", "income_dup"}
    assert pairs[0]["coefficient"] == 1.0

    # Verify class imbalance detection in target column
    assert "target" in result["imbalance_report"]
    assert result["imbalance_report"]["target"]["majority_to_minority_ratio"] == 5.0  # 5 A vs 1 B

    # Verify recommendations generation
    recs = result["recommendations"]
    actions = {r["recommended_action"] for r in recs}
    assert "drop_duplicates" in actions
    assert "drop_correlated_column" in actions
    assert "impute_knn" in actions or "impute_median" in actions


@pytest.mark.asyncio
async def test_get_quality_results_success(client: AsyncClient):
    """GET /datasets/{id}/quality returns calculated results."""
    token = await _get_auth_token(client, "quality_get@example.com", "quality_get_user")
    dataset_id = await _upload_dataset(client, token)

    # 1. Fetching quality audit before calculation returns 404
    get_resp_before = await client.get(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp_before.status_code == 404

    # 2. Trigger quality analysis
    post_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_resp.status_code == 201

    # 3. Retrieve quality results
    get_resp_after = await client.get(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp_after.status_code == 200
    assert get_resp_after.json()["quality_score"] == post_resp.json()["quality_score"]


@pytest.mark.asyncio
async def test_quality_unauthorized_access(client: AsyncClient):
    """User cannot audit or read quality results of another user's dataset."""
    token_a = await _get_auth_token(client, "usera_q@example.com", "usera_q")
    token_b = await _get_auth_token(client, "userb_q@example.com", "userb_q")
    dataset_id = await _upload_dataset(client, token_a)

    # User B tries to trigger quality audit on User A's dataset
    resp_post = await client.post(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_post.status_code == 404

    # User B tries to read User A's quality audit
    resp_get = await client.get(
        f"/api/v1/datasets/{dataset_id}/quality",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_get.status_code == 404
