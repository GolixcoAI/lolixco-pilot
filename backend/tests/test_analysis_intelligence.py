"""Integration and route tests for media intelligence, cost protection, and analysis feedback.

Verifies:
1. Mock and provider-based media intelligence analysis flow.
2. Structured response: source_identification, audio_intelligence, blueprint, usage.
3. Cost protection: duplicate brief + provider within TTL returns cached analysis.
4. Latest analysis retrieval GET /analyze/latest.
5. User feedback submission POST /analyze/feedback.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db.repository import InMemoryRepository, get_repository
from app.main import app
from app.services.s3 import MockStorageService, get_storage

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def storage() -> MockStorageService:
    return MockStorageService()


@pytest.fixture
def client(
    repo: InMemoryRepository, storage: MockStorageService
) -> Generator[TestClient, None, None]:
    test_settings = Settings(
        APP_ENV="test",
        ALLOW_DEV_TEST_AUTH=True,
        DATABASE_PROVIDER="memory",
        USE_MOCK_STORAGE=True,
        AI_PROVIDER="mock",
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_USER_ID}"}


def test_analyze_returns_structured_media_intelligence(
    client: TestClient, repo: InMemoryRepository
) -> None:
    """Analyze returns source_identification, audio_intelligence, and editing_blueprint."""
    project = repo.create_project(user_id=TEST_USER_ID, name="Anime Project")
    media = repo.create_media(
        project_id=project.id,
        user_id=TEST_USER_ID,
        original_filename="jjk_fight.mp4",
        s3_object_key=f"users/{TEST_USER_ID}/{project.id}/med-123/jjk_fight.mp4",
        content_type="video/mp4",
        declared_size_bytes=5_000_000,
    )
    repo.update_media_status(
        media.id, TEST_USER_ID, status="verified", verified_size_bytes=5_000_000
    )

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        headers=auth_header(),
        json={
            "brief": {"title": "Anime Battle AMV", "pacing": "fast"},
            "provider": "mock",
            "confirmed_consent": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # 1. Blueprint
    assert "blueprint" in data
    assert data["blueprint"]["title"] is not None
    assert len(data["blueprint"]["scenes"]) > 0

    # 2. Source identification
    assert "source_identification" in data
    source = data["source_identification"]
    assert source["media_type"] in [
        "anime",
        "movie",
        "tv_series",
        "game",
        "music_video",
        "other",
        "unknown",
    ]
    assert "likely_title" in source
    assert "confidence" in source

    # 3. Audio intelligence
    assert "audio_intelligence" in data
    audio = data["audio_intelligence"]
    assert "match_status" in audio

    # 4. Usage metadata
    assert "usage_metadata" in data or "usage" in data


def test_analyze_cost_protection_caches_duplicate_requests(
    client: TestClient, repo: InMemoryRepository
) -> None:
    """Duplicate brief and provider returns existing analysis without re-running inference."""
    project = repo.create_project(user_id=TEST_USER_ID, name="Caching Project")
    media = repo.create_media(
        project_id=project.id,
        user_id=TEST_USER_ID,
        original_filename="clip.mp4",
        s3_object_key=f"users/{TEST_USER_ID}/{project.id}/m1/clip.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, TEST_USER_ID, status="verified", verified_size_bytes=1000)

    payload = {
        "brief": {"title": "Same Brief"},
        "provider": "mock",
        "confirmed_consent": True,
    }

    # First request
    res1 = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        headers=auth_header(),
        json=payload,
    )
    assert res1.status_code == 200
    id1 = res1.json()["id"]

    # Second identical request within TTL
    res2 = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        headers=auth_header(),
        json=payload,
    )
    assert res2.status_code == 200
    id2 = res2.json()["id"]

    # Must return identical cached analysis
    assert id1 == id2


def test_get_latest_analysis_endpoint(client: TestClient, repo: InMemoryRepository) -> None:
    """GET /analyze/latest retrieves most recent analysis for media asset."""
    project = repo.create_project(user_id=TEST_USER_ID)
    media = repo.create_media(
        project_id=project.id,
        user_id=TEST_USER_ID,
        original_filename="clip.mp4",
        s3_object_key=f"users/{TEST_USER_ID}/{project.id}/m1/clip.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, TEST_USER_ID, status="verified", verified_size_bytes=1000)

    # 404 before any analysis exists
    res_none = client.get(
        f"/api/projects/{project.id}/media/{media.id}/analyze/latest",
        headers=auth_header(),
    )
    assert res_none.status_code == 404

    # Run analysis
    res_post = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        headers=auth_header(),
        json={"brief": {"title": "Test"}, "provider": "mock", "confirmed_consent": True},
    )
    assert res_post.status_code == 200
    created_id = res_post.json()["id"]

    # Retrieve latest
    res_latest = client.get(
        f"/api/projects/{project.id}/media/{media.id}/analyze/latest",
        headers=auth_header(),
    )
    assert res_latest.status_code == 200
    assert res_latest.json()["id"] == created_id
    assert res_latest.json()["source_identification"] is not None


def test_submit_analysis_feedback(client: TestClient, repo: InMemoryRepository) -> None:
    """POST /api/projects/{project_id}/media/{media_id}/analyze/feedback saves user corrections."""
    project = repo.create_project(user_id=TEST_USER_ID)
    media = repo.create_media(
        project_id=project.id,
        user_id=TEST_USER_ID,
        original_filename="clip.mp4",
        s3_object_key=f"users/{TEST_USER_ID}/{project.id}/m1/clip.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, TEST_USER_ID, status="verified", verified_size_bytes=1000)

    # Run analysis first
    res_post = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        headers=auth_header(),
        json={
            "brief": {"title": "Initial Analysis"},
            "provider": "mock",
            "confirmed_consent": True,
        },
    )
    analysis_id = res_post.json()["id"]

    # Submit user correction
    feedback_payload = {
        "confirmed_by_user": False,
        "corrected_source_title": "Vinland Saga",
        "corrected_song_title": "Mukanjyo",
        "notes": "Recognized Thorfinn in the opening sequence.",
    }
    res_fb = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze/feedback?analysis_id={analysis_id}",
        headers=auth_header(),
        json=feedback_payload,
    )
    assert res_fb.status_code == 200
    data = res_fb.json()
    assert data["user_feedback"] is not None
    assert data["user_feedback"]["corrected_source_title"] == "Vinland Saga"
    assert data["user_feedback"]["corrected_song_title"] == "Mukanjyo"
    assert data["user_feedback"]["confirmed_by_user"] is False
