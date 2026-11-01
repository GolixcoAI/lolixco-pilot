#!/usr/bin/env python3
"""LolixCopilot Controlled Live Inference Smoke-Test Script.

Usage:
  python scripts/smoke_test_inference.py --provider [baseten|meta] [--video-url URL]

Safeguards:
  - Requires explicit typed confirmation from the user ('RUN') before consuming credits.
  - Checks for API keys and endpoint configuration before attempting network calls.
  - Never logs or exposes raw secrets.
  - Issues exactly 1 bounded request and prints structured latency and token usage.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

# Ensure backend package can be imported
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)

from app.config import get_settings
from app.schemas.analysis import CreativeBriefInput
from app.services.ai_provider import (
    AIProviderError,
    BasetenProvider,
    MetaProvider,
)
from app.services.ai_provider import (
    CreativeBriefContext as AICreativeBriefContext,
)


def create_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser for live inference smoke-testing."""
    parser = argparse.ArgumentParser(
        description="LolixCopilot Controlled Live Inference Smoke-Test",
    )
    parser.add_argument(
        "--provider",
        choices=["baseten", "meta"],
        default="baseten",
        help="Inference provider to test (choices: baseten, meta; default: baseten)",
    )
    parser.add_argument(
        "--video-url",
        default=None,
        help="Optional public or presigned video URL (defaults to test clip)",
    )
    return parser


async def run_smoke_test(provider_name: str, video_url: str | None) -> None:
    settings = get_settings()
    print("=" * 60)
    print("LolixCopilot Controlled Live Inference Smoke-Test")
    print("=" * 60)
    print(f"Provider: {provider_name}")

    provider: BasetenProvider | MetaProvider
    if provider_name == "baseten":
        api_key = settings.BASETEN_API_KEY
        model = settings.BASETEN_MODEL
        base_url = settings.BASETEN_BASE_URL
        print(f"Base URL: {base_url}")
        print(f"Model ID: {model}")
        print(f"API Key configured: {'[YES]' if bool(api_key) else '[NO - MISSING]'}")
        if not api_key:
            print("ERROR: BASETEN_API_KEY is not set in environment or .env.")
            sys.exit(1)
        provider = BasetenProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=float(settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=settings.AI_MAX_RETRIES,
        )

    elif provider_name == "meta":
        api_key = settings.MODEL_API_KEY
        model = settings.META_MODEL
        base_url = settings.META_BASE_URL
        print(f"Base URL: {base_url}")
        print(f"Model ID: {model}")
        print(f"API Key configured: {'[YES]' if bool(api_key) else '[NO - MISSING]'}")
        if not api_key:
            print("ERROR: MODEL_API_KEY is not set in environment or .env.")
            sys.exit(1)
        provider = MetaProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=float(settings.AI_REQUEST_TIMEOUT_SECONDS),
            max_retries=settings.AI_MAX_RETRIES,
        )
    else:
        print(
            f"ERROR: Unknown provider '{provider_name}'. Must be 'baseten' or 'meta'."
        )
        sys.exit(1)

    test_video_url = (
        video_url
        or "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
    )
    print(f"Test Video URL: {test_video_url}")
    print("\nWARNING: This will consume LIVE API credits on your provider account.")
    print(
        "Type 'RUN' to execute exactly one live request, or press Ctrl+C / Enter to cancel:"
    )
    try:
        user_input = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)

    if user_input != "RUN":
        print("Confirmation was not 'RUN'. Aborting smoke test.")
        sys.exit(0)

    print("\nSending live inference request...")
    # Validate with CreativeBriefInput schema first
    brief_input = CreativeBriefInput(
        title="Smoke Test Montage",
        description="Verify multimodal understanding, source recognition, and editing blueprint.",
        style="Kinetic anime recap",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=15.0,
    )
    brief = AICreativeBriefContext(
        title=brief_input.title,
        description=brief_input.description,
        style=brief_input.style,
        pacing=brief_input.pacing,
        aspect_ratio=brief_input.aspect_ratio,
        target_duration=brief_input.target_duration,
    )

    t0 = time.monotonic()
    try:
        (
            blueprint,
            source_id,
            audio_intel,
            usage_meta,
        ) = await provider.analyze_video_intelligence(
            video_url=test_video_url,
            brief=brief,
        )
        elapsed = time.monotonic() - t0
        print(f"\n[SUCCESS] Completed in {elapsed:.2f}s")
        print("\n--- Usage Metadata ---")
        print(f"Provider: {provider_name}")
        print(f"Model: {provider.model}")
        if usage_meta.request_id:
            print(f"Request ID: {usage_meta.request_id}")
        print(f"Latency: {usage_meta.latency_ms} ms")
        print(f"Prompt Tokens: {usage_meta.prompt_tokens}")
        print(f"Completion Tokens: {usage_meta.completion_tokens}")
        print(f"Total Tokens: {usage_meta.total_tokens}")

        print("\n--- Source Identification ---")
        print(f"Classification: {source_id.media_type}")
        print(f"Likely Title: {source_id.likely_title}")
        print(f"Confidence: {source_id.confidence}")
        print(f"Franchise: {source_id.franchise}")
        print(f"Characters: {source_id.characters}")

        print("\n--- Audio Intelligence ---")
        print(f"Song: {audio_intel.song_title} by {audio_intel.artist}")
        print(f"Match Status: {audio_intel.match_status}")
        print(
            f"Genre: {audio_intel.genre} | Tempo: {audio_intel.tempo} | Mood: {audio_intel.mood}"
        )

        print("\n--- Editing Blueprint ---")
        print(
            f"Blueprint Title: {blueprint.title} ({blueprint.target_duration_seconds}s)"
        )
        print(f"Creative Intent: {blueprint.creative_intent}")
        print(f"Summary: {blueprint.summary}")
        print(f"Scenes Count: {len(blueprint.scenes)}")
        for s in blueprint.scenes[:3]:
            print(
                f"  [{s.start_seconds:.1f}s - {s.end_seconds:.1f}s] {s.moment} "
                f"({s.pacing.value}) - {s.editing_direction}"
            )
    except AIProviderError as exc:
        print(f"\n[ERROR] Inference provider error: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] Request failed: {type(exc).__name__}: {exc}")
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    """Entry point for CLI smoke test."""
    parser = create_parser()
    args = parser.parse_args(argv)
    asyncio.run(run_smoke_test(args.provider, args.video_url))


if __name__ == "__main__":
    main()
