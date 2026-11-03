"""Tests for the EDA engine and endpoints.

Verifies overview calculations (heatmaps, null counts, categorical counts), dynamic
custom plots (normality tests, regression scatters, boxplots), and access control security.
"""

import io
import pytest
from httpx import AsyncClient


def _sample_csv_data() -> bytes:
    """Generate a sample CSV dataset with outliers, nulls, correlations, and categories."""
    lines = [
        "age,salary,income_dup,gender",
        "25,50000.0,50000.0,M",
        "30,60000.0,60000.0,F",
        ",70000.0,70000.0,F",        # null age
        "999,80000.0,80000.0,M",     # outlier age
        "40,90000.0,90000.0,M",
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


# Overview EDA Tests

@pytest.mark.asyncio
async def test_run_summary_eda_success(client: AsyncClient):
    """POST /datasets/{id}/eda/generate calculates and commits summary charts to DB."""
    token = await _get_auth_token(client, "eda_sum@example.com", "eda_sum")
    dataset_id = await _upload_dataset(client, token)

    # Trigger generation
    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    charts = resp.json()

    # Verify summary chart generations
    assert len(charts) >= 5
    types = {c["chart_type"] for c in charts}
    assert "correlation_matrix" in types
    assert "missing_values" in types
    assert "categorical_counts" in types
    assert "numerical_skewness" in types
    assert "outlier_densities" in types
    assert "categorical_cardinality" in types

    # Verify database fetch endpoint
    get_resp = await client.get(
        f"/api/v1/datasets/{dataset_id}/eda",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    db_charts = get_resp.json()
    assert len(db_charts) == len(charts)


# Custom Plot EDA Tests

@pytest.mark.asyncio
async def test_custom_distribution_plot_success(client: AsyncClient):
    """POST /datasets/{id}/eda/custom for type='distribution' returns bin centers, curves and normality stats."""
    token = await _get_auth_token(client, "eda_dist@example.com", "eda_dist")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "distribution", "columns": ["salary"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()

    assert result["chart_type"] == "distribution"
    assert "counts" in result["chart_data"]
    assert "normal_curve" in result["chart_data"]
    assert "is_normal" in result["chart_data"]
    assert "p_value" in result["chart_data"]
    assert result["chart_data"]["skewness"] is not None


@pytest.mark.asyncio
async def test_custom_scatter_plot_success(client: AsyncClient):
    """POST /datasets/{id}/eda/custom for type='scatter' returns X-Y points and fitted trendline slope/intercept."""
    token = await _get_auth_token(client, "eda_scat@example.com", "eda_scat")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "scatter", "columns": ["salary", "income_dup"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()

    assert result["chart_type"] == "scatter"
    assert "points" in result["chart_data"]
    assert "line" in result["chart_data"]
    
    # Since salary and income_dup are perfectly correlated:
    assert result["chart_data"]["slope"] == pytest.approx(1.0, 0.01)
    assert result["chart_data"]["r_squared"] == pytest.approx(1.0, 0.01)


# EDA Security Tests

@pytest.mark.asyncio
async def test_eda_unauthorized_access(client: AsyncClient):
    """User cannot trigger summary generation or query custom plots on another user's dataset."""
    token_a = await _get_auth_token(client, "eda_a@example.com", "eda_a")
    token_b = await _get_auth_token(client, "eda_b@example.com", "eda_b")
    dataset_id = await _upload_dataset(client, token_a)

    # User B tries to trigger summary calculations
    resp_sum = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/generate",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_sum.status_code == 404

    # User B tries to query custom distribution
    resp_cust = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "distribution", "columns": ["salary"]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_cust.status_code == 404


@pytest.mark.asyncio
async def test_custom_categorical_plots_success(client: AsyncClient):
    """POST /datasets/{id}/eda/custom for categorical columns returns frequencies."""
    token = await _get_auth_token(client, "eda_cat@example.com", "eda_cat")
    dataset_id = await _upload_dataset(client, token)

    # 1. Test Categorical Counts (Bar)
    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "categorical_counts", "columns": ["gender"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["chart_type"] == "categorical_counts"
    assert "values" in result["chart_data"]
    assert "x_categories" in result["chart_config"]
    assert set(result["chart_config"]["x_categories"]) == {"M", "F"}

    # 2. Test Categorical Share (Pie)
    resp_pie = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "categorical_pie", "columns": ["gender"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_pie.status_code == 200, resp_pie.text
    assert resp_pie.json()["chart_type"] == "categorical_pie"


@pytest.mark.asyncio
async def test_custom_categorical_invalid_type_fails(client: AsyncClient):
    """POST /datasets/{id}/eda/custom returns 400 Bad Request if numeric plots are requested on text/category fields."""
    token = await _get_auth_token(client, "eda_fail_type@example.com", "eda_fail_type")
    dataset_id = await _upload_dataset(client, token)

    resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/eda/custom",
        json={"chart_type": "boxplot", "columns": ["gender"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "categorical" in resp.json()["detail"]

