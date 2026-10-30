"""AI Provider adapter interface and implementations for LolixCopilot.

Provides:
- BaseAIProvider: Abstract provider contract.
- BasetenProvider: Implementation calling Baseten's OpenAI-compatible inference endpoint
  for meta-models/muse-spark-open-1026 with timeouts, controlled retries, bounded output
  tokens, and strict Pydantic blueprint validation.
- MockAIProvider: Deterministic, offline provider for automated testing and zero-credit safety.
- get_ai_provider: FastAPI dependency factory.
"""

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends
from pydantic import ValidationError

from app.config import Settings, get_settings
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
    """Raised when the model output fails JSON decoding or EditingBlueprint schema validation."""


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
# Abstract Base Provider
# ---------------------------------------------------------------------------


class BaseAIProvider(ABC):
    """Abstract interface for editing blueprint generation from video footage."""

    @abstractmethod
    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        """Analyze video footage and generate a validated EditingBlueprint.

        Args:
            video_url: Accessible URL (e.g. short-lived presigned S3 GET URL) for the video.
            brief: The creative brief parameters and goals.
            duration_seconds: Verified source video duration in seconds, if known.

        Returns:
            A validated EditingBlueprint instance.

        Raises:
            AIAuthenticationError: If credentials are invalid.
            AIRateLimitError: If rate limits or quotas are hit.
            AITimeoutError: If inference times out.
            AIValidationError: If model output does not conform to the schema.
            AIProviderError: For general or unexpected inference failures.
        """
        ...


# ---------------------------------------------------------------------------
# Baseten Muse Spark Open Provider
# ---------------------------------------------------------------------------


SYSTEM_BLUEPRINT_PROMPT = """You are LolixCopilot's AI Video Director, an expert assistant for
video editors and creators. Analyze the provided video footage and user creative brief.
Generate an actionable editing blueprint with precise approximate timestamped moments and guidance.

Output strictly valid JSON conforming to the following structure:
{
  "title": "string (working title or hook name for the edit)",
  "creative_intent": "string (normalized intent derived from user brief)",
  "summary": "string (concise overview of the recommended cut)",
  "target_duration_seconds": number (target duration of final cut, e.g. 15.0 to 60.0),
  "aspect_ratio": "string (e.g. 9:16, 16:9, 1:1)",
  "hook": "string (opening hook recommendation to capture immediate attention)",
  "scenes": [
    {
      "id": "scene-01",
      "start_seconds": number (approx start timecode in source footage, >= 0.0),
      "end_seconds": number (approx end timecode in source footage, strictly > start_seconds),
      "moment": "string (what visibly and audibly happens)",
      "why_it_works": "string (why this moment supports the creative brief)",
      "editing_direction": "string (suggested cut, speed ramp, zoom, or transition)",
      "pacing": "slow" | "medium" | "fast",
      "confidence": number | null (calibrated confidence score 0.0 to 1.0, or null)
    }
  ],
  "sequence_rationale": "string (explanation of how the sequence builds narrative energy)",
  "ending_suggestion": "string (recommended closing transition or call to action)",
  "caveats": ["string (notes regarding lighting, audio, or boundary suggestions)"]
}

Rules:
1. Every scene must have start_seconds < end_seconds. All timestamps must be non-negative.
2. Order scenes chronologically according to the suggested narrative progression.
3. Keep directions concrete and practical for a human video editor.
4. Output ONLY the JSON object. Do not include markdown code block backticks or commentary.
"""


class BasetenProvider(BaseAIProvider):
    """Adapter for Baseten's OpenAI-compatible inference endpoint for Muse Spark Open.

    Endpoint: POST {base_url}/chat/completions
    Model: meta-models/muse-spark-open-1026
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
            "Analyze the attached video footage and output the editing blueprint JSON object."
        )

        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_BLUEPRINT_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt_text,
                        },
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": video_url,
                            },
                        },
                    ],
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
    ) -> httpx.Response:
        """Send the inference request with bounded retries and exponential backoff."""
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "LolixCopilot/0.1.0 (Meta-Hackathon)",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    return response

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

                    # Exhausted retries for 429
                    if response.status_code == 429:
                        raise AIRateLimitError(
                            "Baseten rate limit or quota exceeded (HTTP 429). "
                            "Please wait before re-analyzing footage."
                        )

                    # Exhausted retries for 5xx
                    raise AIProviderUnavailableError(
                        f"Baseten inference service unavailable (HTTP {response.status_code}) "
                        f"after {self.max_retries} retries."
                    )

                # Any other client error (e.g. 400 Bad Request, 422 Unprocessable)
                error_body = response.text[:200]
                logger.error(
                    "Baseten inference error: HTTP %s, body: %s",
                    response.status_code,
                    error_body,
                )
                msg = f"Baseten inference rejected HTTP {response.status_code}: {error_body}"
                raise AIProviderError(msg)

            except httpx.TimeoutException as exc:
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

    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        """Call Baseten chat completions endpoint and validate structured blueprint."""
        sanitized_video_url = sanitize_url(video_url)
        payload = self._build_payload(video_url, brief, duration_seconds)

        timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout_seconds,
            write=10.0,
            pool=10.0,
        )

        if self._injected_client is not None:
            response = await self._send_request_with_retries(
                self._injected_client, payload, sanitized_video_url
            )
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await self._send_request_with_retries(
                    client, payload, sanitized_video_url
                )

        try:
            data = response.json()
        except Exception as exc:
            raise AIValidationError("Baseten response was not valid JSON") from exc

        # Extract content from choices[0].message.content
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIValidationError("Baseten response contained no choices")
            content = choices[0]["message"]["content"]
            if not content:
                raise AIValidationError("Baseten response returned empty content")
        except (KeyError, IndexError, TypeError) as exc:
            raise AIValidationError(f"Unexpected Baseten response envelope: {exc}") from exc

        # Validate with Pydantic EditingBlueprint contract
        try:
            blueprint = EditingBlueprint.model_validate_json(content)
        except ValidationError as exc:
            logger.error("EditingBlueprint schema validation failed on model output: %s", exc)
            raise AIValidationError(
                f"Model response did not adhere to EditingBlueprint contract: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise AIValidationError(f"Model content was not valid JSON string: {exc}") from exc

        return blueprint


# ---------------------------------------------------------------------------
# Mock AI Provider (Deterministic, Zero-Credit, Offline)
# ---------------------------------------------------------------------------


class MockAIProvider(BaseAIProvider):
    """Deterministic offline provider for automated testing and local development.

    Never makes network requests. Generates compliant EditingBlueprint data
    grounded in the user's creative brief.
    """

    async def generate_blueprint(
        self,
        video_url: str,
        brief: CreativeBriefContext,
        duration_seconds: float | None = None,
    ) -> EditingBlueprint:
        """Return a deterministic, schema-compliant EditingBlueprint."""
        total_duration = duration_seconds if duration_seconds and duration_seconds > 0 else 30.0
        target_duration = min(brief.target_duration, total_duration)

        # Build 4 sequential scenes that fit cleanly within the target duration
        t_hook = round(min(3.5, target_duration * 0.2), 2)
        t_build = round(min(t_hook + 5.5, target_duration * 0.5), 2)
        t_climax = round(min(t_build + 8.0, target_duration * 0.85), 2)
        t_end = round(target_duration, 2)

        # Ensure strictly ascending timestamps
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

        return EditingBlueprint(
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


# ---------------------------------------------------------------------------
# Provider Factory Dependency
# ---------------------------------------------------------------------------


def get_ai_provider(settings: Settings = Depends(get_settings)) -> BaseAIProvider:
    """FastAPI dependency returning the configured AI Provider."""
    if settings.AI_PROVIDER.lower() == "baseten":
        if not settings.BASETEN_API_KEY:
            msg = (
                "AI_PROVIDER is set to 'baseten', but BASETEN_API_KEY is not configured on server."
            )
            raise AIAuthenticationError(msg)
        return BasetenProvider(
            api_key=settings.BASETEN_API_KEY,
            base_url=settings.BASETEN_BASE_URL,
            model=settings.BASETEN_MODEL,
            timeout_seconds=float(settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=settings.AI_MAX_RETRIES,
        )

    return MockAIProvider()
