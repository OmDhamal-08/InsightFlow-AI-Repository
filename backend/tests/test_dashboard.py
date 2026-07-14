"""Tests for dashboard API endpoints.

Covers summary stats, notifications, recent reports, and recent datasets.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_dashboard_summary_unauthenticated(client: AsyncClient):
    """GET /summary without token returns 401."""
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_summary_authenticated(client: AsyncClient):
    """GET /summary with valid token returns stats."""
    # Register & Login to get token
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dash@example.com",
            "username": "dashuser",
            "password": "Test@1234",
        },
    )
    token = reg.json()["access_token"]

    resp = await client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets_count" in data
    assert "models_count" in data
    assert "reports_count" in data
    assert "data_quality_score" in data


@pytest.mark.asyncio
async def test_get_notifications_authenticated(client: AsyncClient):
    """GET /notifications returns a welcome notification for new users."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "notify@example.com",
            "username": "notifyuser",
            "password": "Test@1234",
        },
    )
    token = reg.json()["access_token"]

    resp = await client.get(
        "/api/v1/dashboard/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert data[0]["title"] == "Welcome to AI BI Platform"
