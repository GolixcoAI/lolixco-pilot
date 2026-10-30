"""Integration tests for project and media API endpoints."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.repository import InMemoryRepository, get_repository
from app.main import app
from app.services.s3 import MockStorageService, get_storage

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())


@pytest.fixture
def test_repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def test_storage() -> MockStorageService:
    return MockStorageService()


@pytest.fixture
def client(
    test_repo: InMemoryRepository, test_storage: MockStorageService
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_repository] = lambda: test_repo
    app.dependency_overrides[get_storage] = lambda: test_storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_missing_authentication(client: TestClient) -> None:
    res = client.get("/api/projects")
    assert res.status_code == 401


def test_create_and_list_projects(client: TestClient) -> None:
    headers = auth_header(USER_A_ID)

    # Initially empty
    res = client.get("/api/projects", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # Create project
    create_res = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "My Reel Cut", "aspect_ratio": "9:16"},
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["name"] == "My Reel Cut"
    assert data["user_id"] == USER_A_ID
    project_id = data["id"]

    # List projects returns the created project
    list_res = client.get("/api/projects", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["id"] == project_id


def test_cross_user_project_isolation(client: TestClient) -> None:
    headers_a = auth_header(USER_A_ID)
    headers_b = auth_header(USER_B_ID)

    # User A creates a project
    create_res = client.post(
        "/api/projects",
        headers=headers_a,
        json={"name": "User A Private Project"},
    )
    project_id = create_res.json()["id"]

    # User B cannot access User A's project
    get_res = client.get(f"/api/projects/{project_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B's project list does not show User A's project
    list_res = client.get("/api/projects", headers=headers_b)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 0


def test_presign_upload_valid_video(client: TestClient) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    # Request presigned upload for valid MP4
    req_payload = {
        "filename": "raw_footage.mp4",
        "content_type": "video/mp4",
        "size_bytes": 50 * 1024 * 1024,  # 50 MB
    }
    res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json=req_payload,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["project_id"] == project_id
    assert "upload_url" in data
    assert data["s3_key"].startswith(f"users/{USER_A_ID}/projects/{project_id}/media/")
    assert data["s3_key"].endswith(".mp4")


def test_presign_upload_invalid_extension(client: TestClient) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={
            "filename": "script.pdf",
            "content_type": "video/mp4",
            "size_bytes": 1000,
        },
    )
    assert res.status_code == 422


def test_presign_upload_invalid_mime(client: TestClient) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={
            "filename": "test.mp4",
            "content_type": "application/x-executable",
            "size_bytes": 1000,
        },
    )
    assert res.status_code == 422


def test_presign_upload_oversized(client: TestClient) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={
            "filename": "test.mp4",
            "content_type": "video/mp4",
            "size_bytes": 150 * 1024 * 1024,  # 150 MB (limit is 100MB)
        },
    )
    assert res.status_code in (413, 422)


def test_upload_confirm_success_and_preview(
    client: TestClient,
    test_storage: MockStorageService,
) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    # 1. Presign
    presign_res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={"filename": "cut.mov", "content_type": "video/quicktime", "size_bytes": 2048},
    )
    media_id = presign_res.json()["media_id"]
    s3_key = presign_res.json()["s3_key"]

    # Mock S3 object upload
    test_storage.set_mock_object(s3_key, size_bytes=2048, exists=True)

    # 2. Confirm
    confirm_res = client.post(
        f"/api/projects/{project_id}/media/{media_id}/confirm",
        headers=headers,
        json={"duration_seconds": 15.5},
    )
    assert confirm_res.status_code == 200
    confirmed = confirm_res.json()
    assert confirmed["status"] == "verified"
    assert confirmed["verified_size_bytes"] == 2048
    assert confirmed["duration_seconds"] == 15.5
    assert confirmed["preview_url"] is not None

    # 3. Retrieve preview URL
    prev_res = client.get(
        f"/api/projects/{project_id}/media/{media_id}/preview-url",
        headers=headers,
    )
    assert prev_res.status_code == 200
    assert "mock-s3.localhost" in prev_res.json()["preview_url"]


def test_upload_confirm_missing_object(
    client: TestClient, test_storage: MockStorageService
) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    presign_res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={"filename": "cut.mp4", "content_type": "video/mp4", "size_bytes": 1000},
    )
    media_id = presign_res.json()["media_id"]
    s3_key = presign_res.json()["s3_key"]

    # Object does NOT exist in storage
    test_storage.set_mock_object(s3_key, size_bytes=0, exists=False)

    confirm_res = client.post(
        f"/api/projects/{project_id}/media/{media_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status_code == 400
    assert "not found in storage" in confirm_res.json()["detail"].lower()


def test_cross_user_media_access_forbidden(
    client: TestClient, test_storage: MockStorageService
) -> None:
    headers_a = auth_header(USER_A_ID)
    headers_b = auth_header(USER_B_ID)

    proj_res = client.post("/api/projects", headers=headers_a, json={"name": "User A Project"})
    project_id = proj_res.json()["id"]

    presign_res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers_a,
        json={"filename": "cut.mp4", "content_type": "video/mp4", "size_bytes": 1000},
    )
    media_id = presign_res.json()["media_id"]

    # User B attempts to confirm or preview User A's media
    confirm_res = client.post(
        f"/api/projects/{project_id}/media/{media_id}/confirm",
        headers=headers_b,
    )
    assert confirm_res.status_code == 404

    prev_res = client.get(
        f"/api/projects/{project_id}/media/{media_id}/preview-url",
        headers=headers_b,
    )
    assert prev_res.status_code == 404

    del_res = client.delete(
        f"/api/projects/{project_id}/media/{media_id}",
        headers=headers_b,
    )
    assert del_res.status_code == 404


def test_media_retention_expired_handling(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    presign_res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={"filename": "expired.mp4", "content_type": "video/mp4", "size_bytes": 1000},
    )
    media_id = presign_res.json()["media_id"]
    s3_key = presign_res.json()["s3_key"]
    test_storage.set_mock_object(s3_key, size_bytes=1000, exists=True)

    client.post(f"/api/projects/{project_id}/media/{media_id}/confirm", headers=headers)

    # Force expiration date into the past
    media_rec = test_repo.get_media(media_id, USER_A_ID)
    assert media_rec is not None
    media_rec.expires_at = datetime.now(UTC) - timedelta(days=1)

    # Request preview on expired media -> returns 410 Gone
    res = client.get(
        f"/api/projects/{project_id}/media/{media_id}/preview-url",
        headers=headers,
    )
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


def test_media_delete_idempotent(
    client: TestClient,
    test_storage: MockStorageService,
) -> None:
    headers = auth_header(USER_A_ID)
    proj_res = client.post("/api/projects", headers=headers, json={"name": "Test Project"})
    project_id = proj_res.json()["id"]

    presign_res = client.post(
        f"/api/projects/{project_id}/media/presign-upload",
        headers=headers,
        json={"filename": "delete_me.mp4", "content_type": "video/mp4", "size_bytes": 1000},
    )
    media_id = presign_res.json()["media_id"]
    s3_key = presign_res.json()["s3_key"]
    test_storage.set_mock_object(s3_key, size_bytes=1000, exists=True)

    # Delete
    del_res = client.delete(f"/api/projects/{project_id}/media/{media_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # S3 object is removed
    assert test_storage.verify_object(s3_key).exists is False

    # Second delete returns 404 because record is gone
    del_again = client.delete(f"/api/projects/{project_id}/media/{media_id}", headers=headers)
    assert del_again.status_code == 404
