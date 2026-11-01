"""AI Provider adapter interface and implementations for LolixCopilot.

Provides:
- BaseAIProvider: Abstract provider contract for video understanding and media intelligence.
- BasetenProvider: Implementation calling Baseten's OpenAI-compatible inference endpoint
  for Muse Spark Open (meta-models/muse-spark-open-1026) with multimodal video/audio ingestion,
  timeouts, controlled retries, bounded output tokens, and strict Pydantic validation.
- MetaProvider: Implementation calling the official Meta Model API (POST /v1/responses)
  for muse-spark-1.3 with structured outputs, latency and usage tracking, and safe error mapping.
- MockAIProvider: Deterministic, offline provider for automated testing and zero-credit safety.
- BaseMusicFingerprintProvider & MockMusicFingerprintProvider: Clean optional specialist
  interface for future ACRCloud integration without inventing external credentials.
- get_ai_provider: FastAPI dependency and factory supporting allowlisted provider selection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.analysis import (
    AudioIntelligence,
    ConfidenceLevelEnum,
    MediaClassificationEnum,
    MusicMatchStatusEnum,
    SourceIdentification,
    UsageMetadata,
)
from app.schemas.blueprint import EditingBlueprint, PacingEnum, SceneRecommendation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Exceptions (Clean abstraction isolated from external HTTP codes)
# ---------------------------------------------------------------------------


class AIProviderError(Exception):
    """Base exception for AI provider failures."""


class AIAuthenticationError(AIProviderError):
    """Raised when provider credentials are missing, invalid, or unauthorized (HTTP 401/403)."""


class AIRateLimitError(AIProviderError):
    """Raised when provider rate limits or credit quotas are exceeded (HTTP 429)."""


class AITimeoutError(AIProviderError):
    """Raised when the inference call exceeds the configured read or connect timeout."""


class AIValidationError(AIProviderError):
    """Raised when the model output fails JSON decoding or schema validation."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when the provider service is unavailable (HTTP 502/503/504)."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class CreativeBriefContext:
    """Creative brief inputs provided by the user for video understanding."""

    title: str = "Untitled Cut"
    description: str = "Punchy hook for social media"
    style: str = "Punchy & Fast"
    pacing: str = "fast"
    aspect_ratio: str = "9:16"
    target_duration: float = 30.0


def sanitize_url(url: str) -> str:
    """Strip query string parameters from URLs to prevent leaking signed tokens in logs."""
    if "?" in url:
        return url.split("?")[0] + "?[REDACTED_PARAMS]"
    return url


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------


SYSTEM_MEDIA_INTELLIGENCE_PROMPT = """You are LolixCopilot's AI Video Director.
Analyze the provided video footage and user creative brief.
Your goals:
1. Identify the source material (Anime, Movie, TV Series, Game, Music Video, or Other/Unknown).
   Do NOT invent titles, characters, or episodes if uncertain.
2. Analyze the soundtrack and audio (Genre, Mood, Tempo, Beat drops, and possible Song/Artist).
   Do NOT present unverified predictions as confirmed fingerprints.
3. Generate an actionable editing blueprint with precise approximate timestamped cut points.

Output strictly valid JSON adhering to this schema:
{
  "source_identification": {
    "media_type": "anime" | "movie" | "tv_series" | "game" | "music_video" | "other" | "unknown",
    "likely_title": "string or null",
    "franchise": "string or null",
    "season_episode": "string or null",
    "characters": ["string"],
    "recognizable_scenes": ["string"],
    "visual_evidence": "string",
    "confidence": "high" | "medium" | "low" | "unrated",
    "confidence_score": number or null,
    "alternative_candidates": ["string"]
  },
  "audio_intelligence": {
    "song_title": "string or null",
    "artist": "string or null",
    "genre": "string or null",
    "lyrics_or_vocal_phrases": ["string"],
    "mood": "string or null",
    "tempo": "string or null",
    "beat_changes": ["string"],
    "match_status": "confirmed_fingerprint" | "strong_inference" | "possible_match" | "unknown",
    "confidence_score": number or null
  },
  "blueprint": {
    "title": "string",
    "creative_intent": "string",
    "summary": "string",
    "target_duration_seconds": number,
    "aspect_ratio": "string",
    "hook": "string",
    "scenes": [
      {
        "id": "scene-01",
        "start_seconds": number,
        "end_seconds": number,
        "moment": "string",
        "why_it_works": "string",
        "editing_direction": "string",
        "pacing": "slow" | "medium" | "fast",
        "confidence": number or null
      }
    ],
    "sequence_rationale": "string",
    "ending_suggestion": "string",
    "caveats": ["string"]
  }
}

Rules:
1. Every scene must have start_seconds < end_seconds. Timestamps must be non-negative.
2. Order scenes chronologically.
3. Output ONLY the JSON object. Do not include markdown code block backticks or commentary.
"""


# ---------------------------------------------------------------------------
# Abstract Base Provider
# ---------------------------------------------------------------------------


class BaseAIProvider(ABC):
    """Abstract interface for editing blueprint generation and media intelligence."""

    @abstractmethod
    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        """Analyze video footage and generate a validated EditingBlueprint."""
        ...

    @abstractmethod
    async def analyze_video_intelligence(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        """Perform video understanding, source/audio intelligence, and blueprinting."""
        ...


# ---------------------------------------------------------------------------
# Music Fingerprint Provider Interface (Phase C / Future Specialist Extension)
# ---------------------------------------------------------------------------


class BaseMusicFingerprintProvider(ABC):
    """Clean interface for optional audio fingerprinting services (e.g. ACRCloud)."""

    @abstractmethod
    async def identify_music(self, audio_url: str) -> AudioIntelligence:
        """Identify music by querying an acoustic fingerprint database."""
        ...


class MockMusicFingerprintProvider(BaseMusicFingerprintProvider):
    """Offline placeholder implementation for acoustic fingerprinting."""

    async def identify_music(self, audio_url: str) -> AudioIntelligence:
        return AudioIntelligence(
            song_title=None,
            artist=None,
            genre="Electronic / Phonk",
            mood="Energetic",
            tempo="130 BPM",
            beat_changes=["Beat drop at 00:04.2"],
            match_status=MusicMatchStatusEnum.UNKNOWN,
        )


# ---------------------------------------------------------------------------
# Helper: Parse Model JSON Output
# ---------------------------------------------------------------------------


def parse_multimodal_analysis_json(
    raw_content: str,
    brief: CreativeBriefContext,
    target_duration: float,
) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence]:
    """Parse raw model output JSON into validated Pydantic models.

    Handles both the combined media intelligence schema and legacy standalone blueprints.
    """
    clean_text = raw_content.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise AIValidationError(f"Model output was not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise AIValidationError("Model output did not return a JSON object")

    # Helper to normalize blueprint fields
    def _normalize_blueprint_dict(bp: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(bp)
        if not normalized.get("title"):
            normalized["title"] = brief.title or "Untitled Cut"
        if not normalized.get("creative_intent"):
            normalized["creative_intent"] = (
                brief.description or "Dynamic edit based on source footage"
            )
        if not normalized.get("summary"):
            normalized["summary"] = f"Structured edit recommendation for {normalized['title']}"
        if not normalized.get("target_duration_seconds"):
            normalized["target_duration_seconds"] = float(target_duration)
        if not normalized.get("hook"):
            normalized["hook"] = normalized.get("title") or "High energy opening hook"
        if not normalized.get("sequence_rationale"):
            normalized["sequence_rationale"] = "Progressive pacing from opening hook to peak action"
        if not normalized.get("ending_suggestion"):
            normalized["ending_suggestion"] = "Final punch cut on beat or title frame"

        scenes_raw = normalized.get("scenes")
        if isinstance(scenes_raw, list):
            norm_scenes = []
            for idx, sc in enumerate(scenes_raw):
                if not isinstance(sc, dict):
                    continue
                s = dict(sc)
                if not s.get("id"):
                    s["id"] = f"scene-{idx + 1}"
                if not s.get("moment"):
                    s["moment"] = s.get("visual_summary") or f"Moment {idx + 1}"
                if not s.get("why_it_works"):
                    s["why_it_works"] = "Matches rhythm and visual momentum"
                if not s.get("editing_direction"):
                    s["editing_direction"] = "Cut on action"
                if "start_seconds" in s and "end_seconds" in s:
                    try:
                        start_f = float(s["start_seconds"])
                        end_f = float(s["end_seconds"])
                        if end_f <= start_f:
                            end_f = start_f + 1.0
                        s["start_seconds"] = start_f
                        s["end_seconds"] = end_f
                    except (ValueError, TypeError):
                        s["start_seconds"] = float(idx * 2)
                        s["end_seconds"] = float((idx + 1) * 2)
                norm_scenes.append(s)
            normalized["scenes"] = norm_scenes
        return normalized

    # If the response contains nested "blueprint", parse combined structure
    if "blueprint" in data and isinstance(data["blueprint"], dict):
        try:
            norm_bp = _normalize_blueprint_dict(data["blueprint"])
            blueprint = EditingBlueprint.model_validate(norm_bp)
        except ValidationError as exc:
            raise AIValidationError(
                f"Model response did not adhere to EditingBlueprint contract: {exc}"
            ) from exc

        # Source identification
        raw_source = data.get("source_identification")
        if isinstance(raw_source, dict):
            try:
                source_id = SourceIdentification.model_validate(raw_source)
            except ValidationError:
                source_id = SourceIdentification(media_type=MediaClassificationEnum.UNKNOWN)
        else:
            source_id = SourceIdentification(media_type=MediaClassificationEnum.UNKNOWN)

        # Audio intelligence
        raw_audio = data.get("audio_intelligence")
        if isinstance(raw_audio, dict):
            try:
                audio_intel = AudioIntelligence.model_validate(raw_audio)
            except ValidationError:
                audio_intel = AudioIntelligence(match_status=MusicMatchStatusEnum.UNKNOWN)
        else:
            audio_intel = AudioIntelligence(match_status=MusicMatchStatusEnum.UNKNOWN)

        return blueprint, source_id, audio_intel

    # Standalone blueprint format (e.g. legacy prompt or direct blueprint output)
    try:
        blueprint = EditingBlueprint.model_validate(data)
    except ValidationError as exc:
        raise AIValidationError(
            f"Model response did not adhere to EditingBlueprint contract: {exc}"
        ) from exc

    source_id = SourceIdentification(
        media_type=MediaClassificationEnum.UNKNOWN,
        likely_title=None,
        confidence=ConfidenceLevelEnum.UNRATED,
    )
    audio_intel = AudioIntelligence(
        match_status=MusicMatchStatusEnum.UNKNOWN,
    )
    return blueprint, source_id, audio_intel


# ---------------------------------------------------------------------------
# Provider 1: Baseten Muse Spark Open Provider
# ---------------------------------------------------------------------------


class BasetenProvider(BaseAIProvider):
    """Adapter for Baseten's OpenAI-compatible inference endpoint for Muse Spark Open.

    Endpoint: POST {base_url}/chat/completions
    Model: meta-models/muse-spark-open-1026 (or configured override)
    """

    RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://inference.baseten.co/v1",
        model: str = "meta-models/muse-spark-open-1026",
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise AIAuthenticationError("BASETEN_API_KEY must be provided for BasetenProvider")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._injected_client = client

    def _build_payload(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> dict[str, Any]:
        """Construct the OpenAI-compatible multimodal chat completions payload."""
        dur_info = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
        user_prompt_text = (
            f"Creative Brief:\n"
            f"- Working Title: {brief.title}\n"
            f"- Intent: {brief.description}\n"
            f"- Target Style: {brief.style}\n"
            f"- Target Pacing: {brief.pacing}\n"
            f"- Aspect Ratio: {brief.aspect_ratio}\n"
            f"- Target Duration: {brief.target_duration}s\n"
            f"- Source Video Duration: {dur_info}\n\n"
            "Analyze the attached footage. Identify the source franchise, characters, soundtrack, "
            "and output the complete media intelligence and editing blueprint JSON object."
        )

        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": user_prompt_text},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]

        # Optional separate audio asset URL for dual multimodal understanding
        if audio_url:
            user_content.append({"type": "audio_url", "audio_url": {"url": audio_url}})

        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_MEDIA_INTELLIGENCE_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 2500,
        }

    async def _send_request_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        video_url_for_logging: str,
    ) -> tuple[httpx.Response, float]:
        """Send the inference request with bounded retries and measure wall-clock latency."""
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LolixCopilot/0.1.0 (Meta-Hackathon)",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if response.status_code == 200:
                    return response, latency_ms

                # Non-retryable authentication error
                if response.status_code in (401, 403):
                    logger.error("Baseten authentication failed (HTTP %s)", response.status_code)
                    raise AIAuthenticationError(
                        f"Baseten API authentication failed (HTTP {response.status_code}). "
                        "Verify that BASETEN_API_KEY is configured correctly."
                    )

                # Retryable status codes (429 rate limit or 5xx server issues)
                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries:
                        backoff = (0.5 * (2**attempt)) + (random.uniform(0.1, 0.3))
                        logger.warning(
                            "Baseten request returned HTTP %s (attempt %d/%d). Retrying in %.2fs",
                            response.status_code,
                            attempt + 1,
                            self.max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    if response.status_code == 429:
                        raise AIRateLimitError(
                            "Baseten rate limit or quota exceeded (HTTP 429). "
                            "Please wait before re-analyzing footage."
                        )

                    raise AIProviderUnavailableError(
                        f"Baseten inference service unavailable (HTTP {response.status_code}) "
                        f"after {self.max_retries} retries."
                    )

                error_body = response.text[:200]
                logger.error(
                    "Baseten inference error: HTTP %s, body: %s",
                    response.status_code,
                    error_body,
                )
                msg = f"Baseten inference rejected HTTP {response.status_code}: {error_body}"
                raise AIProviderError(msg)

            except (httpx.TimeoutException, TimeoutError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = 0.5 * (2**attempt)
                    logger.warning("Baseten request timed out, retrying in %.2fs...", backoff)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(
                    "Baseten inference timed out after %.1fs for video: %s",
                    self.timeout_seconds,
                    video_url_for_logging,
                )
                raise AITimeoutError(
                    f"Baseten model inference timed out after {self.timeout_seconds}s"
                ) from exc

            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = 0.5 * (2**attempt)
                    logger.warning("Baseten network error (%s), retrying in %.2fs...", exc, backoff)
                    await asyncio.sleep(backoff)
                    continue
                raise AIProviderUnavailableError(
                    f"Could not connect to Baseten inference endpoint: {exc}"
                ) from exc

        raise AIProviderError(f"Baseten request failed: {last_error}")

    async def _execute_inference(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        sanitized_video_url = sanitize_url(video_url)
        payload = self._build_payload(video_url, brief, duration_seconds, audio_url)

        timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout_seconds,
            write=10.0,
            pool=10.0,
        )

        if self._injected_client is not None:
            response, latency_ms = await self._send_request_with_retries(
                self._injected_client, payload, sanitized_video_url
            )
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response, latency_ms = await self._send_request_with_retries(
                    client, payload, sanitized_video_url
                )

        try:
            data = response.json()
        except Exception as exc:
            raise AIValidationError("Baseten response was not valid JSON") from exc

        # Extract content
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIValidationError("Baseten response contained no choices")
            content = choices[0]["message"]["content"]
            if not content:
                raise AIValidationError("Baseten response returned empty content")
        except (KeyError, IndexError, TypeError) as exc:
            raise AIValidationError(f"Unexpected Baseten response envelope: {exc}") from exc

        # Extract telemetry
        raw_usage = data.get("usage", {})
        usage_meta = UsageMetadata(
            prompt_tokens=raw_usage.get("prompt_tokens"),
            completion_tokens=raw_usage.get("completion_tokens"),
            total_tokens=raw_usage.get("total_tokens"),
            latency_ms=latency_ms,
            request_id=data.get("id"),
        )

        target_duration = duration_seconds or brief.target_duration
        blueprint, source_id, audio_intel = parse_multimodal_analysis_json(
            content, brief, target_duration
        )
        return blueprint, source_id, audio_intel, usage_meta

    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        blueprint, _, _, _ = await self._execute_inference(
            video_url, brief, duration_seconds, audio_url=None
        )
        return blueprint

    async def analyze_video_intelligence(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        return await self._execute_inference(video_url, brief, duration_seconds, audio_url)


# ---------------------------------------------------------------------------
# Provider 2: Meta — Official Meta Model API
# ---------------------------------------------------------------------------


class MetaProvider(BaseAIProvider):
    """Adapter for the official Meta Model API.

    Uses Meta's Responses API endpoint: POST {base_url}/responses
    Model: muse-spark-1.3 (or configured override)
    Auth: Authorization: Bearer {MODEL_API_KEY}
    """

    RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.meta.ai/v1",
        model: str = "muse-spark-1.3",
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise AIAuthenticationError("MODEL_API_KEY is not configured for MetaProvider")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._injected_client = client or http_client

    def _build_payload(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Construct the official Meta Responses API multimodal request payload."""
        dur_info = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
        user_prompt_text = (
            f"Creative Brief:\n"
            f"- Working Title: {brief.title}\n"
            f"- Intent: {brief.description}\n"
            f"- Target Style: {brief.style}\n"
            f"- Target Pacing: {brief.pacing}\n"
            f"- Aspect Ratio: {brief.aspect_ratio}\n"
            f"- Target Duration: {brief.target_duration}s\n"
            f"- Source Video Duration: {dur_info}\n\n"
            "Analyze the attached footage. Identify the source franchise, characters, soundtrack, "
            "and output the complete media intelligence and editing blueprint JSON object."
        )

        meta_prompt = f"{SYSTEM_MEDIA_INTELLIGENCE_PROMPT}\n\n{user_prompt_text}"
        return {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": meta_prompt},
                        {"type": "input_video", "video_url": video_url},
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 2500,
        }

    async def _send_request_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        video_url_for_logging: str,
    ) -> tuple[httpx.Response, float]:
        """Send the inference request to Meta's API with bounded retries."""
        endpoint = f"{self.base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LolixCopilot/0.1.0 (Meta-Hackathon)",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                if response.status_code == 200:
                    return response, latency_ms

                if response.status_code in (401, 403):
                    logger.error("Meta API authentication failed (HTTP %s)", response.status_code)
                    raise AIAuthenticationError(
                        f"Meta Model API authentication failed (HTTP {response.status_code}). "
                        "Verify that MODEL_API_KEY is configured correctly."
                    )

                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries:
                        backoff = (0.5 * (2**attempt)) + (random.uniform(0.1, 0.3))
                        logger.warning(
                            "Meta API request returned HTTP %s (attempt %d/%d). Retrying in %.2fs",
                            response.status_code,
                            attempt + 1,
                            self.max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    if response.status_code == 429:
                        raise AIRateLimitError(
                            "Meta Model API rate limit or credit quota exceeded (HTTP 429)."
                        )

                    raise AIProviderUnavailableError(
                        f"Meta Model API service unavailable (HTTP {response.status_code}) "
                        f"after {self.max_retries} retries."
                    )

                error_body = response.text[:200]
                logger.error(
                    "Meta Model API rejected request: HTTP %s, body: %s",
                    response.status_code,
                    error_body,
                )
                msg = f"Meta Model API rejected request (HTTP {response.status_code}): {error_body}"
                raise AIProviderError(msg)

            except (httpx.TimeoutException, TimeoutError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = 0.5 * (2**attempt)
                    logger.warning("Meta API request timed out, retrying in %.2fs...", backoff)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(
                    "Meta Model API timed out after %.1fs for video: %s",
                    self.timeout_seconds,
                    video_url_for_logging,
                )
                raise AITimeoutError(
                    f"Meta Model API inference timed out after {self.timeout_seconds}s"
                ) from exc

            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = 0.5 * (2**attempt)
                    logger.warning(
                        "Meta API network error (%s), retrying in %.2fs...",
                        exc,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise AIProviderUnavailableError(
                    f"Could not connect to Meta Model API endpoint: {exc}"
                ) from exc

        raise AIProviderError(f"Meta Model API request failed: {last_error}")

    def _extract_content(self, data: dict[str, Any]) -> str:
        """Extract text content from Meta's Responses API envelope."""
        # Check standard Responses API envelope: output[0].content[0].text
        output = data.get("output", [])
        if isinstance(output, list) and output:
            first_out = output[0]
            if isinstance(first_out, dict):
                content_list = first_out.get("content", [])
                if isinstance(content_list, list) and content_list:
                    first_item = content_list[0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        return str(first_item["text"])
                if "text" in first_out:
                    return str(first_out["text"])

        # Fallback for choices / chat completions compatibility
        choices = data.get("choices", [])
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            if isinstance(msg, dict) and "content" in msg:
                return str(msg["content"])

        raise AIValidationError(f"Unexpected Meta Model API response format: {data}")

    async def _execute_inference(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        sanitized_video_url = sanitize_url(video_url)
        payload = self._build_payload(video_url, brief, duration_seconds)

        timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout_seconds,
            write=10.0,
            pool=10.0,
        )

        if self._injected_client is not None:
            response, latency_ms = await self._send_request_with_retries(
                self._injected_client, payload, sanitized_video_url
            )
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response, latency_ms = await self._send_request_with_retries(
                    client, payload, sanitized_video_url
                )

        try:
            data = response.json()
        except Exception as exc:
            raise AIValidationError("Meta API response was not valid JSON") from exc

        content = self._extract_content(data)

        raw_usage = data.get("usage", {})
        usage_meta = UsageMetadata(
            prompt_tokens=raw_usage.get("prompt_tokens"),
            completion_tokens=raw_usage.get("completion_tokens"),
            total_tokens=raw_usage.get("total_tokens"),
            latency_ms=latency_ms,
            request_id=data.get("id"),
        )

        target_duration = duration_seconds or brief.target_duration
        blueprint, source_id, audio_intel = parse_multimodal_analysis_json(
            content, brief, target_duration
        )
        return blueprint, source_id, audio_intel, usage_meta

    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        blueprint, _, _, _ = await self._execute_inference(video_url, brief, duration_seconds)
        return blueprint

    async def analyze_video_intelligence(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        return await self._execute_inference(video_url, brief, duration_seconds)


# ---------------------------------------------------------------------------
# Mock AI Provider (Deterministic, Zero-Credit, Offline)
# ---------------------------------------------------------------------------


class MockAIProvider(BaseAIProvider):
    """Deterministic offline provider for automated testing and local development.

    Never makes network requests. Generates compliant EditingBlueprint and
    Media Intelligence data grounded in the user's creative brief.
    """

    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        blueprint, _, _, _ = await self.analyze_video_intelligence(
            video_url, brief, duration_seconds
        )
        return blueprint

    async def analyze_video_intelligence(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
        audio_url: str | None = None,
    ) -> tuple[EditingBlueprint, SourceIdentification, AudioIntelligence, UsageMetadata]:
        """Return deterministic, schema-compliant EditingBlueprint and Media Intelligence."""
        total_duration = duration_seconds if duration_seconds and duration_seconds > 0 else 30.0
        target_duration = min(brief.target_duration, total_duration)

        t_hook = round(min(3.5, target_duration * 0.2), 2)
        t_build = round(min(t_hook + 5.5, target_duration * 0.5), 2)
        t_climax = round(min(t_build + 8.0, target_duration * 0.85), 2)
        t_end = round(target_duration, 2)

        if t_build <= t_hook:
            t_build = round(t_hook + 1.0, 2)
        if t_climax <= t_build:
            t_climax = round(t_build + 1.0, 2)
        if t_end <= t_climax:
            t_end = round(t_climax + 1.0, 2)

        scenes = [
            SceneRecommendation(
                id="scene-01",
                start_seconds=0.0,
                end_seconds=t_hook,
                moment=f"High-energy opening hook establishing {brief.title}",
                why_it_works="Immediately stops scrolling with strong foreground motion.",
                editing_direction="Punch-in 110% zoom with rapid jump cut for curiosity.",
                pacing=PacingEnum.FAST,
                confidence=0.94,
            ),
            SceneRecommendation(
                id="scene-02",
                start_seconds=t_hook,
                end_seconds=t_build,
                moment=f"Context and narrative build: {brief.description[:60]}",
                why_it_works="Develops emotional momentum and contextual clarity for audience.",
                editing_direction="Match cut on motion, maintain brisk rhythmic tempo.",
                pacing=PacingEnum.MEDIUM,
                confidence=0.88,
            ),
            SceneRecommendation(
                id="scene-03",
                start_seconds=t_build,
                end_seconds=t_climax,
                moment="Peak action or core transformation reveal",
                why_it_works="Delivers the payoff promised in the hook with visual impact.",
                editing_direction="Hold wide framing for 1.5s, then cut dynamically on beat.",
                pacing=PacingEnum.FAST,
                confidence=0.92,
            ),
            SceneRecommendation(
                id="scene-04",
                start_seconds=t_climax,
                end_seconds=t_end,
                moment="Closing resolution and memorable hero frame",
                why_it_works="Leaves viewer with clear resolution and compelling reason to share.",
                editing_direction="Subtle ease-out deceleration, seamless loop transition.",
                pacing=PacingEnum.SLOW,
                confidence=0.85,
            ),
        ]

        blueprint = EditingBlueprint(
            title=brief.title or "High-Impact Short-Form Cut",
            creative_intent=brief.description or "Dynamic pacing optimized for social feeds",
            summary=(
                f"A {brief.style} cut paced at {brief.pacing} tempo, "
                f"structured into 4 narrative beats over {target_duration:.1f}s."
            ),
            target_duration_seconds=target_duration,
            aspect_ratio=brief.aspect_ratio or "9:16",
            hook=f"Start immediately on high-contrast motion at 0.0s to introduce {brief.title}.",
            scenes=scenes,
            sequence_rationale=(
                "Front-loads the strongest visual motion to arrest feed abandonment, "
                "then resolves into an energetic payoff that encourages looping."
            ),
            ending_suggestion="Clean kinetic snap transition into end frame or branded outro.",
            caveats=[
                "AI suggested timestamps are approximate; adjust cut points to audio beats.",
                "Ensure source lighting on hook matches the contrast of subsequent scenes.",
            ],
        )

        source_id = SourceIdentification(
            media_type=MediaClassificationEnum.ANIME,
            likely_title="Jujutsu Kaisen",
            franchise="Jujutsu Kaisen Series",
            season_episode="Season 2 (Shibuya Incident)",
            characters=["Satoru Gojo", "Suguru Geto"],
            recognizable_scenes=["Infinity barrier visual hallmark", "Urban Shibuya confrontation"],
            visual_evidence=(
                "Distinctive cel-shaded visual style, blindfold visual marker, "
                "and high-contrast spectral lighting effects."
            ),
            confidence=ConfidenceLevelEnum.HIGH,
            confidence_score=0.92,
            alternative_candidates=["Bleach: Thousand-Year Blood War", "Chainsaw Man"],
        )

        audio_intel = AudioIntelligence(
            song_title="Slava Funk",
            artist="DVRST",
            genre="Drift Phonk",
            lyrics_or_vocal_phrases=["Distorted 808 vocal snippet at 00:02.4"],
            mood="Aggressive & Kinetic",
            tempo="130 BPM",
            beat_changes=["Heavy 808 sub drop at 00:03.5", "Rhythmic syncopation at 00:12.0"],
            match_status=MusicMatchStatusEnum.POSSIBLE_MATCH,
            confidence_score=0.81,
        )

        usage_meta = UsageMetadata(
            prompt_tokens=148,
            completion_tokens=312,
            total_tokens=460,
            latency_ms=45.2,
            request_id="mock_req_test123",
        )

        return blueprint, source_id, audio_intel, usage_meta


# ---------------------------------------------------------------------------
# Provider Factory Dependency
# ---------------------------------------------------------------------------


def create_ai_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> BaseAIProvider:
    """Instantiate a provider instance by name with settings validation."""
    active_settings = settings or get_settings()
    chosen_provider = (provider_name or active_settings.AI_PROVIDER).strip().lower()

    if chosen_provider == "baseten":
        if not active_settings.BASETEN_API_KEY:
            raise AIAuthenticationError(
                "AI provider is set to 'baseten', but BASETEN_API_KEY is not configured on server."
            )
        return BasetenProvider(
            api_key=active_settings.BASETEN_API_KEY,
            base_url=active_settings.BASETEN_BASE_URL,
            model=active_settings.BASETEN_MODEL,
            timeout_seconds=float(active_settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=active_settings.AI_MAX_RETRIES,
        )

    if chosen_provider == "meta":
        if not active_settings.MODEL_API_KEY:
            raise AIAuthenticationError(
                "AI provider is set to 'meta', but MODEL_API_KEY is not configured on server."
            )
        return MetaProvider(
            api_key=active_settings.MODEL_API_KEY,
            base_url=active_settings.META_BASE_URL,
            model=active_settings.META_MODEL,
            timeout_seconds=float(active_settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=active_settings.AI_MAX_RETRIES,
        )

    return MockAIProvider()


def get_ai_provider(settings: Settings = Depends(get_settings)) -> BaseAIProvider:
    """FastAPI dependency returning the server default AI Provider."""
    return create_ai_provider(settings=settings)
