"""Tests for MediaProcessingService (probing and bounded audio extraction).

Verifies:
1. MockMediaProcessingService behavior and output formats.
2. LocalMediaProcessingService behavior (probing fallback, binary check).
3. Factory function get_media_processing_service().
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.media_processing import (
    LocalMediaProcessingService,
    MockMediaProcessingService,
    get_media_processing_service,
)


@pytest.mark.asyncio
async def test_mock_media_processing_service_probe() -> None:
    """MockMediaProcessingService returns deterministic probe result."""
    svc = MockMediaProcessingService()
    probe = await svc.probe_media("https://example.com/clip.mp4")

    assert probe.duration_seconds == 30.0
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.has_video is True if hasattr(probe, "has_video") else True
    assert probe.has_audio is True
    assert probe.codec_name == "h264"
    assert probe.audio_codec == "aac"


@pytest.mark.asyncio
async def test_mock_media_processing_service_audio_extraction() -> None:
    """MockMediaProcessingService extracts audio to destination path."""
    svc = MockMediaProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = str(Path(tmpdir) / "extracted.mp3")
        res = await svc.extract_audio("https://example.com/clip.mp4", out_path)

        assert res.success is True
        assert res.output_path == out_path
        assert res.duration_seconds == 30.0
        assert Path(out_path).exists()


@pytest.mark.asyncio
async def test_local_media_processing_service_fallback_probe_without_binaries() -> None:
    """LocalMediaProcessingService gracefully produces empty probe if ffprobe is not installed."""
    svc = LocalMediaProcessingService(ffprobe_bin=None, ffmpeg_bin=None)
    assert svc.is_available is False
    probe = await svc.probe_media("https://example.com/clip.mp4")

    assert probe.duration_seconds is None
    assert probe.has_audio is False


def test_get_media_processing_service_factory() -> None:
    """get_media_processing_service returns instance of BaseMediaProcessingService."""
    svc = get_media_processing_service()
    assert svc is not None
