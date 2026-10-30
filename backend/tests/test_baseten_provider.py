"""Unit tests for the Baseten Muse Spark Open provider adapter and analysis endpoint.

All external inference calls are mocked with zero live network or credit consumption.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings
from app.db.repository import InMemoryRepository, get_repository
from app.main import app
from app.schemas.blueprint import EditingBlueprint, PacingEnum
from app.services.ai_provider import (
    AIAuthenticationError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    AIValidationError,
    BasetenProvider,
    CreativeBriefContext,
    MockAIProvider,
    get_ai_provider,
    sanitize_url,
)
from app.services.s3 import MockStorageService, get_storage

VALID_BLUEPRINT_PAYLOAD: dict[str, Any] = {
    "title": "Neon Sunset Cut",
    "creative_intent": "High energy social montage",
    "summary": "Punchy sequence designed for maximum engagement",
    "target_duration_seconds": 25.0,
    "aspect_ratio": "9:16",
    "hook": "Jump cut immediately on motion at 0.0s",
    "scenes": [
        {
            "id": "scene-01",
            "start_seconds": 0.0,
            "end_seconds": 3.2,
            "moment": "Skater dropping into the bowl",
            "why_it_works": "Immediate kinetic hook",
            "editing_direction": "110% zoom with speed ramp",
            "pacing": "fast",
            "confidence": 0.95,
        },
        {
            "id": "scene-02",
            "start_seconds": 3.2,
            "end_seconds": 9.5,
            "moment": "Mid-air grab against sunset",
            "why_it_works": "Striking visual contrast",
            "editing_direction": "Slow motion 50% speed ramp",
            "pacing": "medium",
            "confidence": 0.90,
        },
    ],
    "sequence_rationale": "Transitions from dynamic hook to breathtaking mid-air payoff",
    "ending_suggestion": "Snap cut to black on skateboard landing",
    "caveats": ["Source audio requires EQ around 3.2s transition"],
}


def make_baseten_chat_response(content_obj_or_str: Any, status_code: int = 200) -> httpx.Response:
    """Helper to generate a mock httpx.Response matching Baseten chat completions envelope."""
    if isinstance(content_obj_or_str, (dict, list)):
        content_str = json.dumps(content_obj_or_str)
    else:
        content_str = str(content_obj_or_str)

    envelope = {
        "id": "chatcmpl-mock-baseten-123",
        "object": "chat.completion",
        "created": 1730000000,
        "model": "meta-models/muse-spark-open-1026",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content_str,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 340,
            "total_tokens": 460,
        },
    }
    return httpx.Response(
        status_code=status_code,
        json=envelope,
        request=httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions"),
    )


# ---------------------------------------------------------------------------
# Sanitize URL Tests
# ---------------------------------------------------------------------------


def test_sanitize_url_redacts_query_parameters() -> None:
    """Ensure sensitive S3 presigned tokens in query parameters are redacted."""
    raw_url = "https://my-bucket.s3.ap-south-1.amazonaws.com/video.mp4?X-Amz-Signature=secret123&X-Amz-Credential=cred456"
    sanitized = sanitize_url(raw_url)
    assert "secret123" not in sanitized
    assert "cred456" not in sanitized
    assert sanitized == "https://my-bucket.s3.ap-south-1.amazonaws.com/video.mp4?[REDACTED_PARAMS]"

    clean_url = "https://example.com/video.mp4"
    assert sanitize_url(clean_url) == clean_url


# ---------------------------------------------------------------------------
# MockAIProvider Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_ai_provider_generates_valid_blueprint() -> None:
    """Verify MockAIProvider generates a valid, schema-compliant EditingBlueprint."""
    provider = MockAIProvider()
    brief = CreativeBriefContext(
        title="Urban Drift",
        description="Fast drift sequence for short-form video",
        style="Kinetic",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=20.0,
    )
    blueprint = await provider.generate_blueprint(
        video_url="https://mock-storage.local/drift.mp4",
        brief=brief,
        duration_seconds=30.0,
    )

    assert isinstance(blueprint, EditingBlueprint)
    assert blueprint.title == "Urban Drift"
    assert blueprint.aspect_ratio == "9:16"
    assert blueprint.target_duration_seconds == 20.0
    assert len(blueprint.scenes) == 4

    # Verify timestamps are strictly ascending and valid
    prev_end = 0.0
    for scene in blueprint.scenes:
        assert scene.start_seconds < scene.end_seconds
        assert scene.start_seconds >= prev_end
        assert scene.pacing in (PacingEnum.SLOW, PacingEnum.MEDIUM, PacingEnum.FAST)
        prev_end = scene.start_seconds


# ---------------------------------------------------------------------------
# BasetenProvider Tests
# ---------------------------------------------------------------------------


def test_baseten_provider_requires_api_key() -> None:
    """Verify BasetenProvider raises AIAuthenticationError if API key is empty."""
    with pytest.raises(AIAuthenticationError, match="BASETEN_API_KEY must be provided"):
        BasetenProvider(api_key="")


def test_baseten_provider_builds_correct_payload() -> None:
    """Verify OpenAI-compatible multimodal chat completions payload structure."""
    provider = BasetenProvider(
        api_key="mock_key_test",
        base_url="https://inference.baseten.co/v1",
        model="meta-models/muse-spark-open-1026",
    )
    brief = CreativeBriefContext(
        title="Speed Run",
        description="High intensity cuts",
        style="Punchy",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=15.0,
    )
    payload = provider._build_payload(
        video_url="https://s3.ap-south-1.amazonaws.com/test.mp4?sig=abc",
        brief=brief,
        duration_seconds=32.0,
    )

    assert payload["model"] == "meta-models/muse-spark-open-1026"
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 2500
    assert payload["response_format"] == {"type": "json_object"}

    messages = payload["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "You are LolixCopilot's AI Video Director" in messages[0]["content"]

    assert messages[1]["role"] == "user"
    contents = messages[1]["content"]
    assert len(contents) == 2
    assert contents[0]["type"] == "text"
    assert "Speed Run" in contents[0]["text"]
    assert contents[1]["type"] == "video_url"
    assert contents[1]["video_url"]["url"] == "https://s3.ap-south-1.amazonaws.com/test.mp4?sig=abc"


@pytest.mark.asyncio
async def test_baseten_provider_successful_inference() -> None:
    """Verify successful inference parsing and schema validation."""
    mock_resp = make_baseten_chat_response(VALID_BLUEPRINT_PAYLOAD)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    provider = BasetenProvider(
        api_key="valid_secret_key",
        client=mock_client,
        max_retries=1,
    )
    brief = CreativeBriefContext(title="Neon Sunset Cut")

    blueprint = await provider.generate_blueprint(
        video_url="https://s3.local/video.mp4",
        brief=brief,
        duration_seconds=25.0,
    )

    assert blueprint.title == "Neon Sunset Cut"
    assert len(blueprint.scenes) == 2
    assert blueprint.scenes[0].moment == "Skater dropping into the bowl"
    assert blueprint.scenes[0].start_seconds == 0.0
    assert blueprint.scenes[0].end_seconds == 3.2

    # Verify authorization header was passed
    call_args = mock_client.post.call_args
    assert call_args[1]["headers"]["Authorization"] == "Bearer valid_secret_key"


@pytest.mark.asyncio
async def test_baseten_provider_handles_malformed_json() -> None:
    """Verify AIValidationError is raised when model output is not valid JSON."""
    mock_resp = make_baseten_chat_response("NOT_JSON_AT_ALL {{{")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    provider = BasetenProvider(api_key="valid_secret_key", client=mock_client)
    with pytest.raises(AIValidationError):
        await provider.generate_blueprint(
            video_url="https://s3.local/video.mp4",
            brief=CreativeBriefContext(),
        )


@pytest.mark.asyncio
async def test_baseten_provider_handles_invalid_schema_timestamps() -> None:
    """Verify AIValidationError is raised when timestamps violate start < end."""
    invalid_payload = dict(VALID_BLUEPRINT_PAYLOAD)
    invalid_payload["scenes"] = [
        {
            "id": "scene-01",
            "start_seconds": 10.0,
            "end_seconds": 5.0,  # Invalid: end < start!
            "moment": "Backwards time leap",
            "why_it_works": "Impossible",
            "editing_direction": "Cut",
            "pacing": "fast",
        }
    ]
    mock_resp = make_baseten_chat_response(invalid_payload)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    provider = BasetenProvider(api_key="valid_secret_key", client=mock_client)
    with pytest.raises(AIValidationError, match="EditingBlueprint contract"):
        await provider.generate_blueprint(
            video_url="https://s3.local/video.mp4",
            brief=CreativeBriefContext(),
        )


@pytest.mark.asyncio
async def test_baseten_provider_handles_authentication_failure() -> None:
    """Verify HTTP 401 raises AIAuthenticationError without unnecessary retries."""
    mock_resp = httpx.Response(
        status_code=401,
        json={"error": "Invalid API key provided"},
        request=httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    provider = BasetenProvider(api_key="bad_key", client=mock_client, max_retries=2)
    with pytest.raises(AIAuthenticationError, match="Baseten API authentication failed"):
        await provider.generate_blueprint(
            video_url="https://s3.local/video.mp4",
            brief=CreativeBriefContext(),
        )

    # 401 must not trigger retries
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_baseten_provider_handles_rate_limits_with_retries() -> None:
    """Verify HTTP 429 retries and raises AIRateLimitError when exhausted."""
    mock_resp = httpx.Response(
        status_code=429,
        json={"error": "Rate limit exceeded"},
        request=httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        provider = BasetenProvider(api_key="test_key", client=mock_client, max_retries=2)
        with pytest.raises(AIRateLimitError, match="Baseten rate limit or quota exceeded"):
            await provider.generate_blueprint(
                video_url="https://s3.local/video.mp4",
                brief=CreativeBriefContext(),
            )

        assert mock_client.post.call_count == 3  # initial + 2 retries
        assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_baseten_provider_handles_timeout() -> None:
    """Verify request timeout raises AITimeoutError."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.ReadTimeout("Read timed out")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        provider = BasetenProvider(
            api_key="test_key",
            client=mock_client,
            timeout_seconds=30.0,
            max_retries=1,
        )
        with pytest.raises(AITimeoutError, match="timed out after 30.0s"):
            await provider.generate_blueprint(
                video_url="https://s3.local/video.mp4",
                brief=CreativeBriefContext(),
            )


@pytest.mark.asyncio
async def test_baseten_provider_handles_server_unavailable() -> None:
    """Verify HTTP 503 retries and raises AIProviderUnavailableError."""
    mock_resp = httpx.Response(
        status_code=503,
        text="Service Unavailable",
        request=httpx.Request("POST", "https://inference.baseten.co/v1/chat/completions"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    with patch("asyncio.sleep", new_callable=AsyncMock):
        provider = BasetenProvider(api_key="test_key", client=mock_client, max_retries=1)
        with pytest.raises(
            AIProviderUnavailableError, match="Baseten inference service unavailable"
        ):
            await provider.generate_blueprint(
                video_url="https://s3.local/video.mp4",
                brief=CreativeBriefContext(),
            )


# ---------------------------------------------------------------------------
# Factory Tests
# ---------------------------------------------------------------------------


def test_get_ai_provider_factory() -> None:
    """Verify factory returns appropriate provider based on settings."""
    # Default is mock
    mock_settings = Settings(AI_PROVIDER="mock")
    provider = get_ai_provider(mock_settings)
    assert isinstance(provider, MockAIProvider)

    # Baseten without API key raises AIAuthenticationError
    baseten_no_key = Settings(AI_PROVIDER="baseten", BASETEN_API_KEY="")
    with pytest.raises(AIAuthenticationError, match="BASETEN_API_KEY is not configured"):
        get_ai_provider(baseten_no_key)

    # Baseten with API key returns BasetenProvider
    baseten_configured = Settings(AI_PROVIDER="baseten", BASETEN_API_KEY="secret_key_123")
    baseten_p = get_ai_provider(baseten_configured)
    assert isinstance(baseten_p, BasetenProvider)
    assert baseten_p.model == "meta-models/muse-spark-open-1026"


# ---------------------------------------------------------------------------
# FastAPI Route Integration Tests (/api/projects/{p}/media/{m}/analyze)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_setup() -> Any:
    """Provide isolated TestClient, repo, and mock storage."""
    repo = InMemoryRepository()
    storage = MockStorageService()

    user_uuid = "11111111-1111-1111-1111-111111111111"
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=user_uuid, is_anonymous=True
    )

    client = TestClient(app)
    try:
        yield client, repo, storage
    finally:
        app.dependency_overrides.clear()


def test_analyze_requires_user_authorization(
    test_setup: tuple[TestClient, InMemoryRepository, MockStorageService],
) -> None:
    """Verify HTTP 400 when confirmed_baseten_consent is False."""
    client, repo, _ = test_setup
    user_uuid = "11111111-1111-1111-1111-111111111111"
    project = repo.create_project(user_id=user_uuid)
    media = repo.create_media(
        project_id=project.id,
        user_id=user_uuid,
        original_filename="clip.mp4",
        s3_object_key="users/user/test.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, user_uuid, status="verified", verified_size_bytes=1000)

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={
            "brief": {"title": "Test Brief"},
            "confirmed_baseten_consent": False,
        },
    )
    assert res.status_code == 400
    assert "User authorization required" in res.json()["detail"]


def test_analyze_rejects_unverified_media(
    test_setup: tuple[TestClient, InMemoryRepository, MockStorageService],
) -> None:
    """Verify HTTP 400 when media asset status is not 'verified'."""
    client, repo, _ = test_setup
    user_uuid = "11111111-1111-1111-1111-111111111111"
    project = repo.create_project(user_id=user_uuid)
    media = repo.create_media(
        project_id=project.id,
        user_id=user_uuid,
        original_filename="clip.mp4",
        s3_object_key="users/user/test.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    # Status remains 'pending'

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={
            "brief": {"title": "Test Brief"},
            "confirmed_baseten_consent": True,
        },
    )
    assert res.status_code == 400
    assert "must be verified before analysis" in res.json()["detail"]


def test_analyze_rejects_expired_media(
    test_setup: tuple[TestClient, InMemoryRepository, MockStorageService],
) -> None:
    """Verify HTTP 410 when media has passed 7-day retention expiry."""
    client, repo, _ = test_setup
    user_uuid = "11111111-1111-1111-1111-111111111111"
    project = repo.create_project(user_id=user_uuid)
    media = repo.create_media(
        project_id=project.id,
        user_id=user_uuid,
        original_filename="clip.mp4",
        s3_object_key="users/user/test.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, user_uuid, status="verified", verified_size_bytes=1000)
    # Manually expire
    media.expires_at = datetime.now(UTC) - timedelta(days=1)

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={
            "brief": {"title": "Test Brief"},
            "confirmed_baseten_consent": True,
        },
    )
    assert res.status_code == 410
    assert "expired" in res.json()["detail"]


def test_analyze_success_with_mock_provider(
    test_setup: tuple[TestClient, InMemoryRepository, MockStorageService],
) -> None:
    """Verify 200 OK with valid AnalysisResponse when user authorizes analysis."""
    client, repo, storage = test_setup
    user_uuid = "11111111-1111-1111-1111-111111111111"
    project = repo.create_project(user_id=user_uuid)
    media = repo.create_media(
        project_id=project.id,
        user_id=user_uuid,
        original_filename="clip.mp4",
        s3_object_key="placeholder",
        content_type="video/mp4",
        declared_size_bytes=5000000,
    )
    s3_key = storage.generate_object_key(user_uuid, project.id, media.id, ".mp4")
    media.s3_object_key = s3_key
    repo.update_media_status(
        media.id,
        user_uuid,
        status="verified",
        verified_size_bytes=5000000,
        duration_seconds=28.5,
    )

    app.dependency_overrides[get_ai_provider] = lambda: MockAIProvider()

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={
            "brief": {
                "title": "Neon Night Run",
                "description": "Dynamic night run in cyberpunk aesthetic",
                "style": "Cinematic Flow",
                "pacing": "fast",
                "aspect_ratio": "9:16",
                "target_duration": 25.0,
            },
            "confirmed_baseten_consent": True,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == project.id
    assert data["media_id"] == media.id
    assert "blueprint" in data
    assert data["blueprint"]["title"] == "Neon Night Run"
    assert len(data["blueprint"]["scenes"]) == 4


def test_analyze_error_mapping_baseten_provider(
    test_setup: tuple[TestClient, InMemoryRepository, MockStorageService],
) -> None:
    """Verify HTTP status code mappings for domain provider errors."""
    client, repo, storage = test_setup
    user_uuid = "11111111-1111-1111-1111-111111111111"
    project = repo.create_project(user_id=user_uuid)
    media = repo.create_media(
        project_id=project.id,
        user_id=user_uuid,
        original_filename="clip.mp4",
        s3_object_key="users/u/p/m/test.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    repo.update_media_status(media.id, user_uuid, status="verified", verified_size_bytes=1000)

    # 1. Rate Limit Error -> 429
    failing_provider = AsyncMock(spec=BasetenProvider)
    failing_provider.generate_blueprint.side_effect = AIRateLimitError("Rate limit exceeded")
    app.dependency_overrides[get_ai_provider] = lambda: failing_provider

    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={"brief": {"title": "T"}, "confirmed_baseten_consent": True},
    )
    assert res.status_code == 429
    assert "rate limit" in res.json()["detail"].lower()

    # 2. Timeout Error -> 504
    failing_provider.generate_blueprint.side_effect = AITimeoutError("Timed out")
    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={"brief": {"title": "T"}, "confirmed_baseten_consent": True},
    )
    assert res.status_code == 504
    assert "timed out" in res.json()["detail"].lower()

    # 3. Validation Error -> 502
    failing_provider.generate_blueprint.side_effect = AIValidationError("Schema mismatch")
    res = client.post(
        f"/api/projects/{project.id}/media/{media.id}/analyze",
        json={"brief": {"title": "T"}, "confirmed_baseten_consent": True},
    )
    assert res.status_code == 502
    assert "blueprint schema" in res.json()["detail"].lower()
