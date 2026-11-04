"""Tests for AI Director chat assistant and audio beat analysis endpoints."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db.repository import InMemoryRepository
from app.main import app
from app.routes.media import get_repository, get_storage
from app.schemas.chat import ChatRequest
from app.services.chat_director import ChatDirectorService
from app.services.s3 import MockStorageService


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


def test_chat_director_service_direct_queries() -> None:
    """Verify chat service handles all required core queries accurately."""
    service = ChatDirectorService()
    media_data = {
        "original_filename": "gojo_hollow_purple_edit.mp4",
        "duration_seconds": 68.08,
    }

    # 1. Anime identification
    req_anime = ChatRequest(message="Identify this anime.")
    res_anime = service.process_chat_message(req_anime, media_data=media_data)
    assert "Jujutsu Kaisen" in res_anime.message.content
    assert res_anime.message.evidence_cards

    # 2. Character identification
    req_char = ChatRequest(message="Who is this character?")
    res_char = service.process_chat_message(req_char, media_data=media_data)
    assert "Satoru Gojo" in res_char.message.content
    assert res_char.message.timecode_jump == 6.0

    # 3. Hollow Purple retrieval
    req_hp = ChatRequest(message="Find Gojo using Hollow Purple.")
    res_hp = service.process_chat_message(req_hp, media_data=media_data)
    assert "Hollow Technique: Purple" in res_hp.message.content
    assert res_hp.message.timecode_jump == 35.0

    # 4. Peak discharge
    req_peak = ChatRequest(message="Find the peak discharge.")
    res_peak = service.process_chat_message(req_peak, media_data=media_data)
    assert "35.0s" in res_peak.message.content
    assert res_peak.message.timecode_jump == 35.0

    # 5. Cinematic 30s edit
    req_edit = ChatRequest(message="Make me a cinematic 30-second edit.")
    res_edit = service.process_chat_message(req_edit, media_data=media_data)
    assert res_edit.updated_blueprint is not None
    assert len(res_edit.updated_blueprint["scenes"]) == 4
    assert res_edit.message.timecode_jump == 18.0

    # 6. Faster cuts
    req_fast = ChatRequest(message="Give me faster cuts.")
    res_fast = service.process_chat_message(req_fast, media_data=media_data)
    assert "Pacing Adjustment" in res_fast.message.content

    # 7. Velocity ramps
    req_ramp = ChatRequest(message="Suggest velocity ramps.")
    res_ramp = service.process_chat_message(req_ramp, media_data=media_data)
    assert "Slow Motion" in res_ramp.message.content
    assert "Fast Acceleration" in res_ramp.message.content

    # 8. Beat synchronization
    req_beat = ChatRequest(message="Synchronize edits with the beat.")
    audio_data = {"beat_timestamps": [12.8, 19.6, 28.0, 35.0, 48.0]}
    res_beat = service.process_chat_message(
        req_beat, media_data=media_data, audio_analysis=audio_data
    )
    assert "Beat Synchronization" in res_beat.message.content

    # 9. Better opening
    req_open = ChatRequest(message="Give me a better opening.")
    res_open = service.process_chat_message(req_open, media_data=media_data)
    assert "Opening" in res_open.message.content
    assert res_open.message.timecode_jump == 18.4

    # 10. Impactful ending
    req_end = ChatRequest(message="Find an impactful ending.")
    res_end = service.process_chat_message(req_end, media_data=media_data)
    assert "Outro" in res_end.message.content or "Ending" in res_end.message.content
    assert res_end.message.timecode_jump == 48.0


    # 11. Greetings & Casual Inquiries
    for greeting_text in ("Hi", "Hello", "Hey", "Hi there!", "Good morning", "yo"):
        req_greet = ChatRequest(message=greeting_text)
        res_greet = service.process_chat_message(req_greet, media_data=media_data)
        assert "LolixCopilot AI Director" in res_greet.message.content
        assert res_greet.message.timecode_jump is None
        assert "Analyze Footage" in res_greet.message.content or "review raw footage" in res_greet.message.content.lower()


def test_chat_api_endpoint(client: TestClient, test_repo: InMemoryRepository) -> None:
    """Test POST /api/projects/{project_id}/chat endpoint integration."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id, name="Chat Project")

    media = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="gojo_hollow_purple_edit.mp4",
        s3_object_key="users/test/gojo.mp4",
        content_type="video/mp4",
        declared_size_bytes=5000,
    )

    res = client.post(
        f"/api/projects/{project.id}/chat",
        headers=headers,
        json={
            "message": "Identify this anime and find the strongest action moment.",
            "media_id": media.id,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert data["message"]["role"] == "assistant"
    assert "Jujutsu Kaisen" in data["message"]["content"]


def test_audio_analysis_endpoint(
    client: TestClient,
    test_repo: InMemoryRepository,
    test_storage: MockStorageService,
) -> None:
    """Test GET /api/projects/{project_id}/media/{media_id}/audio-analysis."""
    user_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {user_id}"}
    project = test_repo.create_project(user_id=user_id)
    media = test_repo.create_media(
        project_id=project.id,
        user_id=user_id,
        original_filename="sound_clip.mp4",
        s3_object_key="users/test/sound.mp4",
        content_type="video/mp4",
        declared_size_bytes=3000,
    )
    test_storage.set_mock_object(media.s3_object_key, size_bytes=3000, exists=True)

    res = client.get(
        f"/api/projects/{project.id}/media/{media.id}/audio-analysis",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["media_id"] == media.id
    assert "beat_timestamps" in data
    assert len(data["beat_timestamps"]) > 0
    assert "energy_timeline" in data
    assert "peak_dbfs" in data
    assert "mean_dbfs" in data
