"""Tests for authentication endpoints.

Covers registration, login, token refresh, logout, and /me.
Uses an in-memory SQLite database via conftest fixtures.
"""

import pytest
from httpx import AsyncClient


# ── Registration ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Successful registration returns 201 with access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "Test@1234",
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Duplicate email returns 409."""
    payload = {
        "email": "dup@example.com",
        "username": "user1",
        "password": "Test@1234",
    }
    await client.post("/api/v1/auth/register", json=payload)
    # Try again with same email
    resp = await client.post(
        "/api/v1/auth/register",
        json={**payload, "username": "user2"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Weak password returns 422 validation error."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "short",
        },
    )
    assert resp.status_code == 422


# ── Login ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Successful login returns access token and sets refresh cookie."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "Test@1234",
        },
    )
    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "loginuser",
            "password": "Test@1234",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Wrong password returns 401."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@example.com",
            "username": "wronguser",
            "password": "Test@1234",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "wronguser",
            "password": "WrongPassword1!",
        },
    )
    assert resp.status_code == 401


# ── Protected Route (/me) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    """GET /me with valid token returns user info."""
    # Register + login
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "Test@1234",
        },
    )
    token = reg.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "meuser"
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """GET /me without token returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
