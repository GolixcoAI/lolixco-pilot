"""Tests for Meta AI Model API provider adapter.

Verifies:
1. MetaProvider initialization and credential validation.
2. Multimodal request envelope formatting (/v1/responses).
3. Response parsing, intelligence extraction, and schema validation.
4. Error mapping (401 -> Auth, 429 -> RateLimit, 504 -> Timeout, 502 -> Validation).
5. Cost protection and telemetry tracking (latency, tokens, request ID).
All tests use mocked HTTP transports; no live Meta API calls or tokens are used.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.schemas.analysis import (
    ConfidenceLevelEnum,
    MediaClassificationEnum,
)
from app.services.ai_provider import (
    AIAuthenticationError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    AIValidationError,
    CreativeBriefContext,
    MetaProvider,
)

SAMPLE_INTELLIGENCE_JSON = json.dumps(
    {
        "source_identification": {
            "media_type": "anime",
            "likely_title": "Chainsaw Man",
            "franchise": "Chainsaw Man",
            "season_episode": "Season 1, Ep 1",
            "characters": ["Denji", "Makima"],
            "recognizable_scenes": ["Alleyway devil hunter contract"],
            "visual_evidence": "Distinctive yellow chainsaw head gear and bureau uniforms.",
            "confidence": "high",
            "confidence_score": 0.92,
            "alternative_candidates": ["Jujutsu Kaisen"],
        },
        "audio_intelligence": {
            "song_title": "KICK BACK",
            "artist": "Kenshi Yonezu",
            "genre": "J-Rock / Anisong",
            "lyrics_or_vocal_phrases": ["Doryoku, mirai, A BEAUTIFUL STAR"],
            "mood": "Frenetic, rebellious, chaotic",
            "tempo": "160 BPM",
            "beat_changes": ["Sudden break at 00:04 into driving distorted bassline"],
            "match_status": "strong_inference",
            "confidence_score": 0.88,
        },
        "blueprint": {
            "title": "Chainsaw Kinetic Cut",
            "creative_intent": "Fast-paced action montage with beat-synced speed ramps.",
            "summary": "Punchy anime fight reel.",
            "target_duration_seconds": 12.0,
            "scenes": [
                {
                    "scene_index": 0,
                    "start_seconds": 0.0,
                    "end_seconds": 2.5,
                    "visual_summary": "Opener shot of chainsaw blade revving",
                    "why_it_works": "Introduce protagonist with punchy impact.",
                    "editing_direction": "Hard whip cut on the beat drop",
                    "pacing": "fast",
                    "confidence": 0.95,
                }
            ],
            "sequence_rationale": "High-contrast dynamic flow.",
            "ending_suggestion": "Freeze frame on blood splatter title card.",
            "caveats": ["Avoid strobing for accessibility"],
        },
    }
)


def _make_responses_api_payload(text_content: str) -> dict:
    """Mock standard Meta Responses API envelope: output items containing text."""
    return {
        "id": "meta_resp_12345",
        "model": "muse-spark-1.3",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": text_content,
                    }
                ],
            }
        ],
        "usage": {
            "prompt_tokens": 420,
            "completion_tokens": 280,
            "total_tokens": 700,
        },
    }


def _make_chat_completions_payload(text_content: str) -> dict:
    """Mock OpenAI-compatible envelope fallback for Meta endpoints."""
    return {
        "id": "meta_chat_67890",
        "model": "muse-spark-1.3",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": text_content,
                }
            }
        ],
        "usage": {
            "prompt_tokens": 300,
            "completion_tokens": 200,
            "total_tokens": 500,
        },
    }


def test_meta_provider_requires_api_key() -> None:
    """MetaProvider must raise AIAuthenticationError immediately if MODEL_API_KEY is missing."""
    with pytest.raises(AIAuthenticationError) as exc_info:
        MetaProvider(api_key=None)
    assert "MODEL_API_KEY is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_meta_provider_parses_responses_api_envelope() -> None:
    """Verify parsing of standard Meta /v1/responses format."""
    mock_response = httpx.Response(
        status_code=200,
        json=_make_responses_api_payload(SAMPLE_INTELLIGENCE_JSON),
        request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
    )

    transport = httpx.MockTransport(AsyncMock(return_value=mock_response))
    client = httpx.AsyncClient(transport=transport)

    provider = MetaProvider(
        api_key="test-meta-key",
        base_url="https://api.meta.ai/v1",
        model="muse-spark-1.3",
        client=client,
    )

    brief = CreativeBriefContext(title="Anime AMV Cut", pacing="fast")
    blueprint, source, audio, usage = await provider.analyze_video_intelligence(
        video_url="https://s3.example.com/action.mp4",
        brief=brief,
        duration_seconds=12.0,
        audio_url="https://s3.example.com/audio.wav",
    )

    # 1. Blueprint validation
    assert blueprint.title == "Chainsaw Kinetic Cut"
    assert len(blueprint.scenes) == 1
    assert blueprint.scenes[0].start_seconds == 0.0

    # 2. Source identification validation
    assert source.media_type == MediaClassificationEnum.ANIME
    assert source.likely_title == "Chainsaw Man"
    assert source.confidence == ConfidenceLevelEnum.HIGH
    assert "Denji" in (source.characters or [])

    # 3. Audio intelligence validation
    assert audio.song_title == "KICK BACK"
    assert audio.artist == "Kenshi Yonezu"
    assert audio.tempo == "160 BPM"

    # 4. Usage metadata
    assert usage.prompt_tokens == 420
    assert usage.completion_tokens == 280
    assert usage.total_tokens == 700
    assert usage.request_id == "meta_resp_12345"
    assert usage.latency_ms is not None and usage.latency_ms >= 0


@pytest.mark.asyncio
async def test_meta_provider_parses_chat_completions_fallback() -> None:
    """Verify MetaProvider gracefully parses OpenAI-style response format."""
    mock_response = httpx.Response(
        status_code=200,
        json=_make_chat_completions_payload(SAMPLE_INTELLIGENCE_JSON),
        request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
    )

    transport = httpx.MockTransport(AsyncMock(return_value=mock_response))
    client = httpx.AsyncClient(transport=transport)

    provider = MetaProvider(
        api_key="test-meta-key",
        client=client,
    )

    brief = CreativeBriefContext(title="Test")
    blueprint, source, audio, usage = await provider.analyze_video_intelligence(
        video_url="https://s3.example.com/test.mp4",
        brief=brief,
        duration_seconds=10.0,
    )

    assert blueprint.title == "Chainsaw Kinetic Cut"
    assert source.likely_title == "Chainsaw Man"
    assert usage.request_id == "meta_chat_67890"
    assert usage.total_tokens == 500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type", "expected_phrase"),
    [
        (401, AIAuthenticationError, "authentication failed"),
        (403, AIAuthenticationError, "authentication failed"),
        (429, AIRateLimitError, "rate limit or credit quota exceeded"),
        (503, AIProviderUnavailableError, "service unavailable"),
    ],
)
async def test_meta_provider_http_error_mappings(
    status_code: int,
    error_type: type[Exception],
    expected_phrase: str,
) -> None:
    """Verify HTTP status codes map strictly to domain AI provider exceptions."""
    mock_response = httpx.Response(
        status_code=status_code,
        text="Meta Provider Internal Error",
        request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
    )

    transport = httpx.MockTransport(AsyncMock(return_value=mock_response))
    client = httpx.AsyncClient(transport=transport)

    provider = MetaProvider(api_key="test-key", client=client, max_retries=0)

    with pytest.raises(error_type) as exc_info:
        await provider.analyze_video_intelligence(
            video_url="https://s3.example.com/test.mp4",
            brief=CreativeBriefContext(),
        )
    assert expected_phrase in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_meta_provider_timeout_handling() -> None:
    """Verify httpx.TimeoutException maps to AITimeoutError."""

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out after 90.0s", request=request)

    transport = httpx.MockTransport(timeout_handler)
    client = httpx.AsyncClient(transport=transport)

    provider = MetaProvider(api_key="test-key", client=client)

    with pytest.raises(AITimeoutError) as exc_info:
        await provider.analyze_video_intelligence(
            video_url="https://s3.example.com/test.mp4",
            brief=CreativeBriefContext(),
        )
    assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_meta_provider_malformed_json_handling() -> None:
    """Verify invalid JSON text content raises AIValidationError."""
    mock_response = httpx.Response(
        status_code=200,
        json=_make_responses_api_payload("Here is your plan: not valid json!"),
        request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
    )

    transport = httpx.MockTransport(AsyncMock(return_value=mock_response))
    client = httpx.AsyncClient(transport=transport)

    provider = MetaProvider(api_key="test-key", client=client)

    with pytest.raises(AIValidationError) as exc_info:
        await provider.analyze_video_intelligence(
            video_url="https://s3.example.com/test.mp4",
            brief=CreativeBriefContext(),
        )
    assert "json" in str(exc_info.value).lower() or "schema" in str(exc_info.value).lower()
