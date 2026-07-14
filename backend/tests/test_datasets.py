"""Tests for the Dataset ingestion pipeline (Phase 4).

Covers:
    - CSV upload (metadata extraction: row count, column count, column names)
    - Duplicate file detection (SHA-256 hash conflict)
    - Invalid file type rejection
    - Dataset listing
    - Dataset preview (first N rows via Pandas)
    - Dataset deletion (file + DB record cleanup)
"""

import io

import pytest
from httpx import AsyncClient


def _csv_bytes(rows: int = 5) -> bytes:
    """Generate a simple CSV file as bytes."""
    lines = ["name,age,city"]
    for i in range(rows):
        lines.append(f"user{i},{20 + i},city{i}")
    return "\n".join(lines).encode("utf-8")


async def _get_token(client: AsyncClient, suffix: str = "") -> str:
    """Register a user and return the access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"ds{suffix}@example.com",
            "username": f"dsuser{suffix}",
            "password": "Test@1234",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _upload_csv(client: AsyncClient, token: str, csv: bytes | None = None, filename: str = "test.csv"):
    """Upload a CSV file and return the response."""
    content = csv or _csv_bytes()
    files = {"file": (filename, io.BytesIO(content), "text/csv")}
    return await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Upload Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_csv_success(client: AsyncClient):
    """Uploading a valid CSV returns 201 with correct metadata."""
    token = await _get_token(client, "upload1")
    resp = await _upload_csv(client, token)

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "test.csv"
    assert data["file_type"] == "csv"
    assert data["row_count"] == 5
    assert data["column_count"] == 3
    assert data["column_names"] == ["name", "age", "city"]
    assert data["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_duplicate_returns_conflict(client: AsyncClient):
    """Uploading the same file twice should return 409 Conflict."""
    token = await _get_token(client, "dup1")
    csv = _csv_bytes(3)

    resp1 = await _upload_csv(client, token, csv)
    assert resp1.status_code == 201

    resp2 = await _upload_csv(client, token, csv)
    assert resp2.status_code == 409
    assert "duplicate" in resp2.json()["detail"].lower() or "already" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_invalid_extension(client: AsyncClient):
    """Uploading a .txt file returns 400."""
    token = await _get_token(client, "ext1")
    content = b"hello world"
    files = {"file": ("data.txt", io.BytesIO(content), "text/plain")}
    resp = await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient):
    """Uploading an empty file returns 400."""
    token = await _get_token(client, "empty1")
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    resp = await client.post(
        "/api/v1/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ── List Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_datasets(client: AsyncClient):
    """GET /datasets/ returns the user's uploaded datasets."""
    token = await _get_token(client, "list1")

    # Upload two files
    await _upload_csv(client, token, _csv_bytes(2), "file_a.csv")
    await _upload_csv(client, token, _csv_bytes(4), "file_b.csv")

    resp = await client.get(
        "/api/v1/datasets/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    datasets = resp.json()
    assert len(datasets) == 2
    names = {ds["name"] for ds in datasets}
    assert "file_a.csv" in names
    assert "file_b.csv" in names


# ── Preview Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_dataset(client: AsyncClient):
    """GET /datasets/{id}/preview returns column names and rows."""
    token = await _get_token(client, "prev1")
    upload_resp = await _upload_csv(client, token, _csv_bytes(10))
    ds_id = upload_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/datasets/{ds_id}/preview?rows=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == ["name", "age", "city"]
    assert len(data["rows"]) == 3
    assert data["total_rows"] == 10


# ── Delete Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_dataset(client: AsyncClient):
    """DELETE /datasets/{id} removes the record and returns 204."""
    token = await _get_token(client, "del1")
    upload_resp = await _upload_csv(client, token)
    ds_id = upload_resp.json()["id"]

    # Delete
    resp = await client.delete(
        f"/api/v1/datasets/{ds_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(
        f"/api/v1/datasets/{ds_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
