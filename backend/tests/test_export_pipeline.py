"""Tests for video export, segment trimming, and proxy URL pipelines."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.db.repository import InMemoryRepository
from app.main import app
from app.routes.media import get_repository, get_storage
from app.schemas.export import ExportRequest, ExportSegment
from app.services.s3 import (
    MockStorageService,
    generate_export_object_key,
    generate_proxy_object_key,
)


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
    test_settings = Settings(
        APP_ENV="test",
        ALLOW_DEV_TEST_AUTH=True,
        DATABASE_PROVIDER="memory",
        USE_MOCK_STORAGE=True,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_repository] = lambda: test_repo
    app.dependency_overrides[get_storage] = lambda: test_storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_export_segment_validation() -> None:
    """Validate timestamp bounds and finite number checks on ExportSegment."""
    seg = ExportSegment(start_seconds=18.0, end_seconds=24.5, title="Convergence")
    assert seg.start_seconds == 18.0
    assert seg.end_seconds == 24.5
    assert seg.speed_multiplier == 1.0

    # Inverted timestamps
    with pytest.raises(ValidationError):
        ExportSegment(start_seconds=25.0, end_seconds=10.0)

    # Equal start and end
    with pytest.raises(ValidationError):
        ExportSegment(start_seconds=15.0, end_seconds=15.0)

    # Negative start
    with pytest.raises(ValidationError):
        ExportSegment(start_seconds=-1.0, end_seconds=10.0)


def test_export_request_validation() -> None:
    """Validate ExportRequest restrictions."""
    media_id = str(uuid.uuid4())
    # Empty segments list rejected
    with pytest.raises(ValidationError):
        ExportRequest(media_id=media_id, segments=[])

    # Invalid resolution rejected
    with pytest.raises(ValidationError):
        ExportRequest(
            media_id=media_id,
            segments=[ExportSegment(start_seconds=1.0, end_seconds=5.0)],
            resolution="8K",
        )


def test_storage_key_generators() -> None:
    """Verify proxy and export key generators produce valid scoped paths."""
    u_id = str(uuid.uuid4())
    p_id = str(uuid.uuid4())
    m_id = str(uuid.uuid4())
    e_id = str(uuid.uuid4())

    proxy_key = generate_proxy_object_key(u_id, p_id, m_id)
    assert proxy_key == f"proxies/users/{u_id}/projects/{p_id}/media/{m_id}/preview_h264.mp4"

    export_key = generate_export_object_key(u_id, p_id, e_id)
    assert export_key == f"exports/users/{u_id}/projects/{p_id}/exports/{e_id}.mp4"

    # Rejects invalid non-UUID strings
    with pytest.raises(ValueError):
        generate_proxy_object_key("not-a-uuid", p_id, m_id)


def test_export_endpoint_access_control_and_validation(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    """Test 404/400 validation paths on POST /api/projects/{project_id}/export."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id, name="Test Project")

    # 1. Non-existent media returns 404
    missing_media_id = str(uuid.uuid4())
    res_missing = client.post(
        f"/api/projects/{project.id}/export",
        headers=headers,
        json={
            "media_id": missing_media_id,
            "segments": [{"start_seconds": 1.0, "end_seconds": 5.0}],
        },
    )
    assert res_missing.status_code == 404

    # 2. Unverified media returns 400
    media_unverified = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="pending.mp4",
        s3_object_key="users/test/test.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    res_unverified = client.post(
        f"/api/projects/{project.id}/export",
        headers=headers,
        json={
            "media_id": media_unverified.id,
            "segments": [{"start_seconds": 1.0, "end_seconds": 5.0}],
        },
    )
    assert res_unverified.status_code == 400
    assert "unverified" in res_unverified.json()["detail"].lower()

    # 3. Verified media with segment beyond duration returns 400
    test_repo.update_media_status(
        media_id=media_unverified.id,
        user_id=user_id,
        status="verified",
        duration_seconds=30.0,
    )
    res_bounds = client.post(
        f"/api/projects/{project.id}/export",
        headers=headers,
        json={
            "media_id": media_unverified.id,
            "segments": [{"start_seconds": 45.0, "end_seconds": 50.0}],
        },
    )
    assert res_bounds.status_code == 400
    assert "exceeds video duration" in res_bounds.json()["detail"].lower()


def test_export_endpoint_success(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    """Test successful export job creating downloadable H.264 MP4."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id, name="Export Cut Project")

    media = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="gojo_clip.mp4",
        s3_object_key="users/test/gojo.mp4",
        content_type="video/mp4",
        declared_size_bytes=5000,
    )
    test_repo.update_media_status(
        media_id=media.id,
        user_id=user_id,
        status="verified",
        duration_seconds=68.08,
    )
    test_storage.set_mock_object(media.s3_object_key, size_bytes=5000, exists=True)

    res = client.post(
        f"/api/projects/{project.id}/export",
        headers=headers,
        json={
            "media_id": media.id,
            "segments": [
                {"start_seconds": 18.0, "end_seconds": 24.0, "title": "Incantation"},
                {"start_seconds": 34.0, "end_seconds": 40.0, "title": "Peak Discharge"},
            ],
            "resolution": "1080p",
            "include_audio": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["segment_count"] == 2
    assert data["duration_seconds"] == 12.0
    assert "exports/users/" in data["s3_key"]
    assert "download_url" in data
    assert data["download_url"].startswith("https://mock-s3.localhost")


def test_proxy_playback_url_endpoint(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    """Test GET /api/projects/{project_id}/media/{media_id}/proxy-url."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id)
    media = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="av1_test.mp4",
        s3_object_key="users/test/av1.mp4",
        content_type="video/mp4",
        declared_size_bytes=2000,
    )
    test_storage.set_mock_object(media.s3_object_key, size_bytes=2000, exists=True)

    res = client.get(
        f"/api/projects/{project.id}/media/{media.id}/proxy-url",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_proxy"] is True
    assert data["codec"] == "h264"
    assert "proxy_url" in data
    assert "proxies/users/" in data["proxy_url"]


def test_export_status_endpoint_workflow(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    """Test job-status polling workflow via GET /api/projects/{project_id}/export/{export_id}."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id, name="Export Status Project")

    media = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="render_test.mp4",
        s3_object_key="users/test/render_test.mp4",
        content_type="video/mp4",
        declared_size_bytes=4000,
    )
    test_repo.update_media_status(
        media_id=media.id,
        user_id=user_id,
        status="verified",
        duration_seconds=30.0,
    )
    test_storage.set_mock_object(media.s3_object_key, size_bytes=4000, exists=True)

    # 1. Trigger export
    res_export = client.post(
        f"/api/projects/{project.id}/export",
        headers=headers,
        json={
            "media_id": media.id,
            "segments": [{"start_seconds": 0.0, "end_seconds": 10.0}],
            "resolution": "1080p",
            "include_audio": True,
        },
    )
    assert res_export.status_code == 200
    export_id = res_export.json()["export_id"]

    # 2. Query export job status
    res_status = client.get(
        f"/api/projects/{project.id}/export/{export_id}",
        headers=headers,
    )
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["export_id"] == export_id
    assert status_data["status"] == "completed"
    assert status_data["progress"] == 100
    assert status_data["download_url"] != ""

    # 3. Query non-existent export job
    res_not_found = client.get(
        f"/api/projects/{project.id}/export/{uuid.uuid4()}",
        headers=headers,
    )
    assert res_not_found.status_code == 404
