"""Media processing and probing service for LolixCopilot.

Provides:
- BaseMediaProcessingService: Abstract contract for media inspection and audio extraction.
- LocalMediaProcessingService: Local subprocess implementation using ffprobe/ffmpeg when
  available on the host system, with graceful fallbacks and strict timeouts.
- MockMediaProcessingService: Deterministic mock implementation for offline test suites.
- get_media_processing_service: Dependency factory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaProbeResult:
    """Probed metadata for a media asset."""

    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec_name: str | None = None
    has_audio: bool = False
    audio_codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(frozen=True)
class AudioExtractionResult:
    """Result of an audio extraction operation."""

    success: bool
    output_path: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None


class BaseMediaProcessingService(ABC):
    """Abstract interface for audio/video media probing and processing."""

    @abstractmethod
    async def probe_media(self, file_path_or_url: str) -> MediaProbeResult:
        """Inspect media asset duration, streams, and codecs."""
        ...

    @abstractmethod
    async def extract_audio(
        self,
        video_path: str,
        output_audio_path: str,
        max_duration_seconds: float = 60.0,
    ) -> AudioExtractionResult:
        """Extract bounded audio track (16 kHz mono MP3/WAV) from video asset."""
        ...


class LocalMediaProcessingService(BaseMediaProcessingService):
    """Local media processor leveraging system ffprobe and ffmpeg binaries when available."""

    def __init__(
        self,
        ffprobe_bin: str | None = None,
        ffmpeg_bin: str | None = None,
        probe_timeout_seconds: float = 10.0,
        extract_timeout_seconds: float = 30.0,
    ) -> None:
        self.ffprobe_path = ffprobe_bin or shutil.which("ffprobe")
        self.ffmpeg_path = ffmpeg_bin or shutil.which("ffmpeg")
        self.probe_timeout_seconds = probe_timeout_seconds
        self.extract_timeout_seconds = extract_timeout_seconds

    @property
    def is_available(self) -> bool:
        """True if both ffprobe and ffmpeg are installed on the host."""
        return bool(self.ffprobe_path and self.ffmpeg_path)

    async def probe_media(self, file_path_or_url: str) -> MediaProbeResult:
        """Inspect media using ffprobe or return safe empty result if uninstalled."""
        if not self.ffprobe_path:
            logger.debug("ffprobe not found on host; returning default probe result")
            return MediaProbeResult(has_audio=False)

        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path_or_url,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.probe_timeout_seconds,
            )

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace")[:200]
                logger.warning("ffprobe failed with returncode %s: %s", proc.returncode, err_msg)
                return MediaProbeResult(has_audio=False)

            data = json.loads(stdout.decode("utf-8", errors="replace"))
            return self._parse_ffprobe_output(data)

        except TimeoutError:
            logger.warning("ffprobe timed out after %.1fs", self.probe_timeout_seconds)
            return MediaProbeResult(has_audio=False)
        except Exception as exc:
            logger.warning("Unexpected error during ffprobe inspection: %s", exc)
            return MediaProbeResult(has_audio=False)

    def _parse_ffprobe_output(self, data: dict[str, object]) -> MediaProbeResult:
        format_info = data.get("format", {})
        streams = data.get("streams", [])

        duration: float | None = None
        if isinstance(format_info, dict) and "duration" in format_info:
            try:
                duration = float(str(format_info["duration"]))
            except (ValueError, TypeError):
                duration = None

        width: int | None = None
        height: int | None = None
        fps: float | None = None
        codec: str | None = None
        has_audio = False
        audio_codec: str | None = None
        sample_rate: int | None = None
        channels: int | None = None

        if isinstance(streams, list):
            for stream in streams:
                if not isinstance(stream, dict):
                    continue
                codec_type = stream.get("codec_type")
                if codec_type == "video" and width is None:
                    try:
                        width = int(str(stream.get("width", 0))) or None
                        height = int(str(stream.get("height", 0))) or None
                        codec = str(stream.get("codec_name", "")) or None
                        r_frame_rate = str(stream.get("r_frame_rate", ""))
                        if "/" in r_frame_rate:
                            num, den = r_frame_rate.split("/", 1)
                            fps = round(float(num) / float(den), 2) if float(den) > 0 else None
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass

                elif codec_type == "audio" and not has_audio:
                    has_audio = True
                    audio_codec = str(stream.get("codec_name", "")) or None
                    try:
                        sample_rate = int(str(stream.get("sample_rate", 0))) or None
                        channels = int(str(stream.get("channels", 0))) or None
                    except (ValueError, TypeError):
                        pass

        return MediaProbeResult(
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            codec_name=codec,
            has_audio=has_audio,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
            channels=channels,
        )

    async def extract_audio(
        self,
        video_path: str,
        output_audio_path: str,
        max_duration_seconds: float = 60.0,
    ) -> AudioExtractionResult:
        """Extract 16 kHz mono MP3 from video within bounded time and length limits."""
        if not self.ffmpeg_path:
            return AudioExtractionResult(
                success=False,
                error_message="ffmpeg binary not found in environment",
            )

        # Ensure output directory exists
        Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-t",
            str(max_duration_seconds),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_audio_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.extract_timeout_seconds,
            )

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace")[:200]
                logger.warning(
                    "ffmpeg audio extraction failed (rc=%s): %s",
                    proc.returncode,
                    err_msg,
                )
                return AudioExtractionResult(success=False, error_message=err_msg)

            if not os.path.exists(output_audio_path) or os.path.getsize(output_audio_path) == 0:
                return AudioExtractionResult(
                    success=False,
                    error_message="ffmpeg produced empty audio file",
                )

            return AudioExtractionResult(
                success=True,
                output_path=output_audio_path,
                duration_seconds=max_duration_seconds,
            )

        except TimeoutError:
            logger.warning(
                "ffmpeg audio extraction timed out after %.1fs",
                self.extract_timeout_seconds,
            )
            return AudioExtractionResult(
                success=False,
                error_message=f"ffmpeg extraction timed out after {self.extract_timeout_seconds}s",
            )
        except Exception as exc:
            logger.warning("Unexpected error during ffmpeg extraction: %s", exc)
            return AudioExtractionResult(success=False, error_message=str(exc))


class MockMediaProcessingService(BaseMediaProcessingService):
    """Deterministic mock media processor for testing suites."""

    def __init__(
        self,
        duration: float = 30.0,
        has_audio: bool = True,
        should_succeed: bool = True,
    ) -> None:
        self.duration = duration
        self.has_audio = has_audio
        self.should_succeed = should_succeed

    async def probe_media(self, file_path_or_url: str) -> MediaProbeResult:
        return MediaProbeResult(
            duration_seconds=self.duration,
            width=1080,
            height=1920,
            fps=30.0,
            codec_name="h264",
            has_audio=self.has_audio,
            audio_codec="aac" if self.has_audio else None,
            sample_rate=44100 if self.has_audio else None,
            channels=2 if self.has_audio else None,
        )

    async def extract_audio(
        self,
        video_path: str,
        output_audio_path: str,
        max_duration_seconds: float = 60.0,
    ) -> AudioExtractionResult:
        if not self.should_succeed:
            return AudioExtractionResult(success=False, error_message="Mock extraction failure")

        Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)
        # Write small dummy bytes
        with open(output_audio_path, "wb") as f:
            f.write(b"MOCK_MP3_AUDIO_HEADER_BYTES")

        return AudioExtractionResult(
            success=True,
            output_path=output_audio_path,
            duration_seconds=min(self.duration, max_duration_seconds),
        )


def get_media_processing_service() -> BaseMediaProcessingService:
    """FastAPI dependency for media processing service."""
    from app.config import get_settings

    settings = get_settings()
    if settings.APP_ENV == "test":
        return MockMediaProcessingService()
    if settings.USE_MODAL_MEDIA_WORKER:
        from app.services.modal_media_service import ModalMediaProcessingService

        return ModalMediaProcessingService(app_name=settings.MODAL_MEDIA_WORKER_APP)
    return LocalMediaProcessingService()
