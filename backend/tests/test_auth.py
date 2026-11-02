"""Tests for authentication endpoints.

Covers registration, login, token refresh, logout, and /me.
Uses an in-memory SQLite database via conftest fixtures.
"""

import re

import pytest
from httpx import AsyncClient

from app.core.security import create_refresh_token, create_reset_token, verify_access_token
from app.routers import auth as auth_router


def _refresh_cookie_value(resp) -> str | None:
    """Extract the refresh_token value from a response's Set-Cookie header."""
    match = re.search(r"refresh_token=([^;]+)", resp.headers.get("set-cookie", ""))
    return match.group(1) if match else None


async def _register(client: AsyncClient, email: str, username: str, password: str = "Test@1234"):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


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


# ── Token types ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token_rejected_as_bearer(client: AsyncClient):
    """A refresh token must not authenticate API calls."""
    reg = await _register(client, "types@example.com", "typesuser")
    payload = verify_access_token(reg.json()["access_token"])
    refresh = create_refresh_token({"sub": payload["sub"], "username": payload["username"]})

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_token_rejected_as_bearer(client: AsyncClient):
    """A password reset token must not authenticate API calls."""
    await _register(client, "resettype@example.com", "resettype")
    reset = create_reset_token("resettype@example.com")

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {reset}"})
    assert resp.status_code == 401


# ── Refresh / logout via cookie ──────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_rotates_cookie_and_revokes_old_token(client: AsyncClient):
    """POST /refresh reads the cookie, issues new tokens, and revokes the old refresh token."""
    await _register(client, "rotate@example.com", "rotateuser")
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "rotateuser", "password": "Test@1234"},
    )
    old_refresh = _refresh_cookie_value(login)
    assert old_refresh

    resp = await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    new_refresh = _refresh_cookie_value(resp)
    assert new_refresh and new_refresh != old_refresh

    # The old refresh token has been rotated out and must no longer work
    replay = await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"}
    )
    assert replay.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient):
    """POST /refresh without the refresh cookie is rejected (not a 422 from a bad dependency)."""
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    """After logout, the refresh cookie can no longer be used."""
    await _register(client, "logout@example.com", "logoutuser")
    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "logoutuser", "password": "Test@1234"},
    )
    refresh = _refresh_cookie_value(login)

    out = await client.post("/api/v1/auth/logout", headers={"Cookie": f"refresh_token={refresh}"})
    assert out.status_code == 200

    resp = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"})
    assert resp.status_code == 401


# ── Password reset ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient, monkeypatch):
    """With DEBUG on, the reset link is returned and the new password works."""
    monkeypatch.setattr(auth_router.settings, "DEBUG", True)
    await _register(client, "resetme@example.com", "resetme")

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "resetme@example.com"})
    assert resp.status_code == 200
    match = re.search(r"token=(\S+)", resp.json()["message"])
    assert match, "debug mode should expose the reset link"

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": match.group(1), "new_password": "Newer@5678"},
    )
    assert reset.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "resetme", "password": "Newer@5678"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_never_leaks_token_outside_debug(client: AsyncClient, monkeypatch):
    """Outside DEBUG, no reset token is returned to the client."""
    monkeypatch.setattr(auth_router.settings, "DEBUG", False)
    await _register(client, "private@example.com", "privateuser")

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "private@example.com"})
    assert resp.status_code == 200
    assert "token=" not in resp.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password_does_not_reveal_registered_emails(client: AsyncClient, monkeypatch):
    """Outside DEBUG, registered and unknown emails get identical responses."""
    monkeypatch.setattr(auth_router.settings, "DEBUG", False)
    await _register(client, "exists@example.com", "existsuser")

    known = await client.post("/api/v1/auth/forgot-password", json={"email": "exists@example.com"})
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
