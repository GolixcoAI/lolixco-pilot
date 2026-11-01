"""Unit tests for Modal CPU media worker functions and client adapter service.

Verifies:
1. Pure parsing of ffprobe stream metadata in workers/media_worker.py.
2. Subprocess execution helpers for probing, audio extraction, and frame extraction.
3. Presigned URL streaming uploads.
4. ModalMediaProcessingService client adapter with mocked remote functions.
5. Graceful fallback to LocalMediaProcessingService when Modal is unavailable.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from workers.media_worker import (
    execute_audio_extraction,
    execute_ffprobe,
    execute_frame_extraction,
    parse_media_metadata,
    upload_file_to_presigned_url,
)

from app.config import Settings
from app.services.media_processing import (
    AudioExtractionResult,
    LocalMediaProcessingService,
    MediaProbeResult,
    get_media_processing_service,
)
from app.services.modal_media_service import ModalMediaProcessingService


def test_parse_media_metadata_valid_streams() -> None:
    """parse_media_metadata correctly extracts resolution, FPS, duration, and audio attributes."""
    probe_data = {
        "format": {"duration": "28.500000"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "24/1",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
    }

    result = parse_media_metadata(probe_data)
    assert result["duration_seconds"] == 28.5
    assert result["width"] == 1920
    assert result["height"] == 1080
    assert result["fps"] == 24.0
    assert result["codec_name"] == "h264"
    assert result["has_audio"] is True
    assert result["audio_codec"] == "aac"
    assert result["sample_rate"] == 48000
    assert result["channels"] == 2


def test_parse_media_metadata_empty_or_video_only() -> None:
    """parse_media_metadata handles videos without audio tracks gracefully."""
    probe_data = {
        "format": {"duration": "10.0"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1280,
                "height": 720,
                "r_frame_rate": "30000/1001",
            }
        ],
    }
    result = parse_media_metadata(probe_data)
    assert result["duration_seconds"] == 10.0
    assert result["width"] == 1280
    assert result["fps"] == 29.97
    assert result["has_audio"] is False
    assert result["audio_codec"] is None


def test_execute_ffprobe_mocked_success() -> None:
    """execute_ffprobe parses valid JSON returned by the ffprobe binary."""
    mock_payload = {"format": {"duration": "15.0"}, "streams": []}
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(mock_payload)

    with patch("subprocess.run", return_value=mock_proc):
        data = execute_ffprobe("https://example.com/clip.mp4")
        assert data == mock_payload


def test_execute_ffprobe_mocked_error() -> None:
    """execute_ffprobe returns an empty dict on process failure or timeouts."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "Invalid data found when processing input"

    with patch("subprocess.run", return_value=mock_proc):
        data = execute_ffprobe("https://example.com/corrupt.mp4")
        assert data == {}

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 20.0)):
        data_timeout = execute_ffprobe("https://example.com/timeout.mp4")
        assert data_timeout == {}


def test_execute_audio_extraction_mocked() -> None:
    """execute_audio_extraction creates file and returns structured size and format."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = os.path.join(tmp_dir, "test.wav")

        def mock_run(*args: object, **kwargs: object) -> MagicMock:
            with open(out_path, "wb") as f:
                f.write(b"RIFF_MOCK_WAV_BYTES_DATA")
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            return mock_proc

        with patch("subprocess.run", side_effect=mock_run):
            res = execute_audio_extraction("https://example.com/video.mp4", out_path)
            assert res["success"] is True
            assert res["format"] == "wav"
            assert res["file_size_bytes"] > 0


def test_execute_frame_extraction_mocked() -> None:
    """execute_frame_extraction creates JPEG frame and reports metadata."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = os.path.join(tmp_dir, "frame_01.jpg")

        def mock_run(*args: object, **kwargs: object) -> MagicMock:
            with open(out_path, "wb") as f:
                f.write(b"\xff\xd8\xff_MOCK_JPEG")
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            return mock_proc

        with patch("subprocess.run", side_effect=mock_run):
            res = execute_frame_extraction("https://example.com/video.mp4", 12.5, out_path)
            assert res["success"] is True
            assert res["timestamp_seconds"] == 12.5
            assert res["file_size_bytes"] > 0


def test_upload_file_to_presigned_url_mocked() -> None:
    """upload_file_to_presigned_url streams bytes via HTTP PUT."""
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(b"SAMPLE_UPLOAD_DATA")
        tmp.flush()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            success = upload_file_to_presigned_url(tmp.name, "https://s3.amazonaws.com/put-url")
            assert success is True


@pytest.mark.asyncio
async def test_modal_media_processing_service_probe_remote_success() -> None:
    """ModalMediaProcessingService converts remote worker dictionary into MediaProbeResult."""
    mock_fn = MagicMock()
    mock_fn.remote.aio = AsyncMock(
        return_value={
            "duration_seconds": 45.2,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "codec_name": "h264",
            "has_audio": True,
            "audio_codec": "aac",
            "sample_rate": 44100,
            "channels": 2,
        }
    )

    def mock_lookup(app_name: str, fn_name: str) -> MagicMock:
        return mock_fn

    service = ModalMediaProcessingService(modal_function_lookup=mock_lookup)
    result = await service.probe_media("https://s3.amazonaws.com/video.mp4")

    assert isinstance(result, MediaProbeResult)
    assert result.duration_seconds == 45.2
    assert result.width == 1920
    assert result.height == 1080
    assert result.has_audio is True


@pytest.mark.asyncio
async def test_modal_media_processing_service_extract_audio_remote_success() -> None:
    """ModalMediaProcessingService converts remote audio extraction into AudioExtractionResult."""
    mock_fn = MagicMock()
    mock_fn.remote.aio = AsyncMock(return_value={"success": True, "max_duration_seconds": 60.0})

    def mock_lookup(app_name: str, fn_name: str) -> MagicMock:
        return mock_fn

    service = ModalMediaProcessingService(modal_function_lookup=mock_lookup)
    result = await service.extract_audio("https://s3.amazonaws.com/video.mp4", "/tmp/audio.wav")

    assert isinstance(result, AudioExtractionResult)
    assert result.success is True
    assert result.duration_seconds == 60.0


@pytest.mark.asyncio
async def test_modal_media_processing_service_falls_back_when_remote_fails() -> None:
    """When Modal function raises an exception, service falls back to local processor."""
    mock_fallback = MagicMock(spec=LocalMediaProcessingService)
    mock_fallback.probe_media = AsyncMock(
        return_value=MediaProbeResult(duration_seconds=12.0, has_audio=False)
    )

    mock_fn = MagicMock()
    mock_fn.remote.aio = AsyncMock(side_effect=RuntimeError("Modal network disconnect"))

    def mock_lookup(app_name: str, fn_name: str) -> MagicMock:
        return mock_fn

    service = ModalMediaProcessingService(
        fallback_service=mock_fallback,
        modal_function_lookup=mock_lookup,
    )
    result = await service.probe_media("https://s3.amazonaws.com/video.mp4")

    assert result.duration_seconds == 12.0
    mock_fallback.probe_media.assert_called_once()


def test_get_media_processing_service_factory_with_modal_config() -> None:
    """Factory selects ModalMediaProcessingService when USE_MODAL_MEDIA_WORKER is True."""
    test_settings = Settings(
        APP_ENV="development",
        USE_MODAL_MEDIA_WORKER=True,
        MODAL_MEDIA_WORKER_APP="test-media-worker",
    )

    with patch("app.config.get_settings", return_value=test_settings):
        service = get_media_processing_service()
        assert isinstance(service, ModalMediaProcessingService)
        assert service.app_name == "test-media-worker"
