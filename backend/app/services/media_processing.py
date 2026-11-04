"""Media processing and probing service for LolixCopilot.

Provides:
- BaseMediaProcessingService: Abstract contract for media inspection, proxy generation,
  audio extraction, beat analysis, and edit cut rendering.
- LocalMediaProcessingService: Local subprocess implementation using ffprobe/ffmpeg when
  available on the host system, with graceful fallbacks and strict timeouts.
- MockMediaProcessingService: Deterministic mock implementation for offline test suites.
- get_media_processing_service: Dependency factory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import shutil
import struct
import tempfile
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends

from app.config import Settings, get_settings

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


@dataclass(frozen=True)
class RenderCutResult:
    """Result of multi-segment video trimming and concatenation."""

    success: bool
    output_path: str | None = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    segment_count: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class AudioBeatsResult:
    """Result of audio beat and energy analysis."""

    success: bool
    duration_seconds: float = 0.0
    sample_rate: int = 16000
    peak_dbfs: float = 0.0
    mean_dbfs: float = 0.0
    estimated_bpm: float | None = None
    beat_timestamps: list[float] = field(default_factory=list)
    energy_timeline: list[dict[str, float]] = field(default_factory=list)
    has_speech: bool = False
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
        max_duration_seconds: float = 120.0,
    ) -> AudioExtractionResult:
        """Extract bounded audio track (16 kHz mono MP3/WAV) from video asset."""
        ...

    @abstractmethod
    async def generate_h264_proxy(
        self,
        video_path: str,
        output_proxy_path: str,
        max_width: int = 1280,
    ) -> bool:
        """Generate compatible H.264 MP4 preview proxy."""
        ...

    @abstractmethod
    async def render_edit_cut(
        self,
        video_path: str,
        segments: list[dict[str, Any]],
        output_cut_path: str,
        target_resolution: str = "1080p",
        include_audio: bool = True,
        text_overlays: list[dict[str, Any]] | None = None,
    ) -> RenderCutResult:
        """Trim and concatenate segments into an export cut."""
        ...

    @abstractmethod
    async def analyze_audio_beats(
        self,
        audio_or_video_path: str,
    ) -> AudioBeatsResult:
        """Analyze audio energy, beats/onsets, and tempo."""
        ...


_UNSET = object()


class LocalMediaProcessingService(BaseMediaProcessingService):
    """Local media processor leveraging system ffprobe and ffmpeg binaries when available."""

    def __init__(
        self,
        ffprobe_bin: str | None | Any = _UNSET,
        ffmpeg_bin: str | None | Any = _UNSET,
        probe_timeout_seconds: float = 10.0,
        extract_timeout_seconds: float = 30.0,
        render_timeout_seconds: float = 120.0,
    ) -> None:
        self.ffprobe_path = self._find_ffprobe() if ffprobe_bin is _UNSET else ffprobe_bin
        self.ffmpeg_path = self._find_ffmpeg() if ffmpeg_bin is _UNSET else ffmpeg_bin
        self.probe_timeout_seconds = probe_timeout_seconds
        self.extract_timeout_seconds = extract_timeout_seconds
        self.render_timeout_seconds = render_timeout_seconds

    @staticmethod
    def _find_ffmpeg() -> str | None:
        venv_ffmpeg = Path(".venv/bin/ffmpeg")
        if venv_ffmpeg.exists():
            return str(venv_ffmpeg.resolve())
        return shutil.which("ffmpeg")

    @staticmethod
    def _find_ffprobe() -> str | None:
        venv_ffprobe = Path(".venv/bin/ffprobe")
        if venv_ffprobe.exists():
            return str(venv_ffprobe.resolve())
        return shutil.which("ffprobe")

    @property
    def is_available(self) -> bool:
        """True if both ffmpeg and ffprobe are installed on the host."""
        return bool(self.ffmpeg_path and self.ffprobe_path)

    async def probe_media(self, file_path_or_url: str) -> MediaProbeResult:
        """Inspect media using ffprobe, or fallback to ffmpeg inspection."""
        if self.ffprobe_path:
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

                if proc.returncode == 0:
                    data = json.loads(stdout.decode("utf-8", errors="replace"))
                    return self._parse_ffprobe_output(data)

                err_msg = stderr.decode("utf-8", errors="replace")[:200]
                logger.warning("ffprobe failed with returncode %s: %s", proc.returncode, err_msg)
            except TimeoutError:
                logger.warning("ffprobe timed out after %.1fs", self.probe_timeout_seconds)
            except Exception as exc:
                logger.warning("Unexpected error during ffprobe inspection: %s", exc)

        # Fallback to ffmpeg -i inspection
        if self.ffmpeg_path:
            return await self._probe_with_ffmpeg(file_path_or_url)

        logger.debug("Neither ffprobe nor ffmpeg available on host; returning default probe result")
        return MediaProbeResult(has_audio=False)

    async def _probe_with_ffmpeg(self, file_path: str) -> MediaProbeResult:
        if not self.ffmpeg_path:
            return MediaProbeResult(has_audio=False)
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path,
                "-i",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.probe_timeout_seconds,
            )
            output = stderr.decode("utf-8", errors="replace")

            # Duration: 00:01:08.08
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
            duration = None
            if dur_match:
                h, m, s = dur_match.groups()
                duration = int(h) * 3600 + int(m) * 60 + float(s)

            # Video stream: Stream #0:0: Video: av1 (libdav1d) ... 2560x1440, 30 fps
            vid_match = re.search(
                r"Stream #\d+:\d+.*?: Video: ([^,\n]+),.*?(\d+)x(\d+).*?(\d+(?:\.\d+)?)\s*fps",
                output,
            )
            codec = None
            width = None
            height = None
            fps = None
            if vid_match:
                codec = vid_match.group(1).split()[0].strip()
                width = int(vid_match.group(2))
                height = int(vid_match.group(3))
                fps = float(vid_match.group(4))

            # Audio stream: Stream #0:1: Audio: aac (LC) ... 44100 Hz, stereo
            audio_match = re.search(r"Stream #\d+:\d+.*?: Audio: ([^,\n]+), (\d+) Hz", output)
            has_audio = bool(audio_match)
            audio_codec = audio_match.group(1).split()[0].strip() if audio_match else None
            sample_rate = int(audio_match.group(2)) if audio_match else None

            return MediaProbeResult(
                duration_seconds=duration,
                width=width,
                height=height,
                fps=fps,
                codec_name=codec,
                has_audio=has_audio,
                audio_codec=audio_codec,
                sample_rate=sample_rate,
                channels=2 if has_audio else None,
            )
        except Exception as exc:
            logger.warning("ffmpeg probe failed: %s", exc)
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
        max_duration_seconds: float = 120.0,
    ) -> AudioExtractionResult:
        """Extract 16 kHz mono MP3 from video within bounded time and length limits."""
        if not self.ffmpeg_path:
            return AudioExtractionResult(
                success=False,
                error_message="ffmpeg binary not found in environment",
            )

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

    async def generate_h264_proxy(
        self,
        video_path: str,
        output_proxy_path: str,
        max_width: int = 1280,
    ) -> bool:
        """Generate compatible H.264 MP4 preview proxy."""
        if not self.ffmpeg_path:
            return False

        Path(output_proxy_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-vf",
            f"scale='min({max_width},iw)':-2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "26",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
            "-movflags",
            "+faststart",
            output_proxy_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.render_timeout_seconds,
            )
            return (
                proc.returncode == 0
                and os.path.exists(output_proxy_path)
                and os.path.getsize(output_proxy_path) > 0
            )
        except Exception as exc:
            logger.warning("generate_h264_proxy error: %s", exc)
            return False

    def _create_ass_file(self, text_overlays: list[dict[str, Any]], output_path: str) -> None:
        """Generate an Advanced SubStation Alpha subtitle file for antialiased title overlays."""
        def format_tc(s: float) -> str:
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            return f"{h}:{m:02d}:{sec:05.2f}"

        events: list[str] = []
        for o in text_overlays:
            text = str(o.get("text", "")).strip()
            if not text:
                continue
            color_hex = str(o.get("color", "#a855f7")).lstrip("#")
            if len(color_hex) == 6:
                r, g, b = color_hex[0:2], color_hex[2:4], color_hex[4:6]
                ass_color = f"&H00{b}{g}{r}&"
            else:
                ass_color = "&H00F755A8&"

            start_s = max(0.0, float(o.get("start_seconds", 0.0)))
            end_s = max(start_s + 0.1, float(o.get("end_seconds", start_s + 5.0)))
            events.append(f"Dialogue: 0,{format_tc(start_s)},{format_tc(end_s)},TitleStyle,,0,0,0,,{{\\b1}}{text}")

        content = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: TitleStyle,Arial,60,&H00F755A8,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,2,2,20,20,80,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            + "\n".join(events) + "\n"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    async def render_edit_cut(
        self,
        video_path: str,
        segments: list[dict[str, Any]],
        output_cut_path: str,
        target_resolution: str = "1080p",
        include_audio: bool = True,
        text_overlays: list[dict[str, Any]] | None = None,
    ) -> RenderCutResult:
        """Trim and concatenate segments into a high-quality H.264 MP4 export cut."""
        if not self.ffmpeg_path:
            return RenderCutResult(success=False, error_message="ffmpeg binary not found")
        if not segments:
            return RenderCutResult(success=False, error_message="No segments provided for render")

        Path(output_cut_path).parent.mkdir(parents=True, exist_ok=True)

        filter_parts: list[str] = []
        concat_inputs: list[str] = []
        total_duration = 0.0

        for i, seg in enumerate(segments):
            start = max(0.0, float(seg.get("start_seconds", 0.0)))
            end = float(seg.get("end_seconds", start + 1.0))
            if end <= start:
                end = start + 1.0
            seg_dur = end - start
            total_duration += seg_dur

            filter_parts.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
            )
            if include_audio:
                filter_parts.append(
                    f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]"
                )
                concat_inputs.append(f"[v{i}][a{i}]")
            else:
                concat_inputs.append(f"[v{i}]")

        a_flag = 1 if include_audio else 0
        ass_path: str | None = None
        if text_overlays:
            ass_fd, ass_path = tempfile.mkstemp(suffix=".ass")
            os.close(ass_fd)
            self._create_ass_file(text_overlays, ass_path)

        if ass_path:
            sub_filter = f"; [v_concat]subtitles={ass_path}[outv]"
            concat_str = (
                f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a={a_flag}[v_concat]"
                + ("[outa]" if include_audio else "")
            )
            filter_str = "; ".join(filter_parts) + f"; {concat_str}{sub_filter}"
        else:
            filter_str = (
                "; ".join(filter_parts)
                + f"; {''.join(concat_inputs)}concat=n={len(segments)}:v=1:a={a_flag}[outv]"
                + ("[outa]" if include_audio else "")
            )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-filter_complex",
            filter_str,
            "-map",
            "[outv]",
        ]
        if include_audio:
            cmd.extend(["-map", "[outa]"])

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
            ]
        )
        if include_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.extend(["-movflags", "+faststart", output_cut_path])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.render_timeout_seconds,
            )
            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace")[:300]
                return RenderCutResult(
                    success=False,
                    error_message=f"FFmpeg render failed: {err_msg}",
                )

            if not os.path.exists(output_cut_path) or os.path.getsize(output_cut_path) == 0:
                return RenderCutResult(success=False, error_message="Render produced empty file")

            file_size = os.path.getsize(output_cut_path)
            return RenderCutResult(
                success=True,
                output_path=output_cut_path,
                duration_seconds=round(total_duration, 2),
                file_size_bytes=file_size,
                segment_count=len(segments),
            )
        except TimeoutError:
            return RenderCutResult(
                success=False,
                error_message=f"Render timed out after {self.render_timeout_seconds}s",
            )
        except Exception as exc:
            return RenderCutResult(success=False, error_message=str(exc))
        finally:
            if ass_path and os.path.exists(ass_path):
                try:
                    os.unlink(ass_path)
                except Exception:
                    pass

    async def analyze_audio_beats(self, audio_or_video_path: str) -> AudioBeatsResult:
        """Analyze audio energy, beats/onsets, and tempo without heavy external libraries."""
        if not self.ffmpeg_path:
            return AudioBeatsResult(success=False, error_message="ffmpeg binary not found")

        temp_wav: str | None = None
        try:
            target_wav = audio_or_video_path
            if not audio_or_video_path.endswith(".wav"):
                fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                extract_cmd = [
                    self.ffmpeg_path,
                    "-y",
                    "-i",
                    audio_or_video_path,
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    temp_wav,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *extract_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=self.extract_timeout_seconds)
                target_wav = temp_wav

            if not os.path.exists(target_wav) or os.path.getsize(target_wav) == 0:
                return AudioBeatsResult(success=False, error_message="WAV extraction failed")

            with wave.open(target_wav, "rb") as w:
                frames = w.getnframes()
                rate = w.getframerate()
                if rate == 0 or frames == 0:
                    return AudioBeatsResult(success=False, error_message="Empty audio stream")
                duration = frames / rate
                raw_bytes = w.readframes(frames)
                samples = struct.unpack(f"{frames}h", raw_bytes)

            win_size = int(rate * 0.1)
            energies: list[float] = []
            max_abs = max((abs(s) for s in samples), default=1)
            peak_dbfs = 20 * math.log10(max(1, max_abs) / 32767.0)

            for i in range(0, len(samples) - win_size, win_size):
                chunk = samples[i : i + win_size]
                rms = math.sqrt(sum(s * s for s in chunk) / win_size)
                energies.append(rms)

            avg_energy = sum(energies) / max(1, len(energies))
            mean_dbfs = 20 * math.log10(max(1.0, avg_energy) / 32767.0)

            beats: list[float] = []
            energy_timeline: list[dict[str, float]] = []
            max_e = max(energies, default=1.0) or 1.0

            for idx, e in enumerate(energies):
                t = round(idx * 0.1, 2)
                if e > avg_energy * 1.6 and (not beats or t - beats[-1] >= 0.25):
                    beats.append(t)
                if idx % 5 == 0:
                    energy_timeline.append(
                        {
                            "timestamp": t,
                            "normalized_energy": round(min(1.0, e / max_e), 3),
                        }
                    )

            bpm = None
            if len(beats) >= 4:
                intervals = [
                    round(beats[i] - beats[i - 1], 2)
                    for i in range(1, len(beats))
                    if 0.3 <= beats[i] - beats[i - 1] <= 1.2
                ]
                if intervals:
                    median_interval = sorted(intervals)[len(intervals) // 2]
                    if median_interval > 0:
                        bpm = round(60.0 / median_interval, 1)

            return AudioBeatsResult(
                success=True,
                duration_seconds=round(duration, 2),
                sample_rate=rate,
                peak_dbfs=round(peak_dbfs, 1),
                mean_dbfs=round(mean_dbfs, 1),
                estimated_bpm=bpm,
                beat_timestamps=beats,
                energy_timeline=energy_timeline,
                has_speech=False,
            )
        except Exception as exc:
            logger.warning("Audio beat analysis error: %s", exc)
            return AudioBeatsResult(success=False, error_message=str(exc))
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass


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
        max_duration_seconds: float = 120.0,
    ) -> AudioExtractionResult:
        if not self.should_succeed:
            return AudioExtractionResult(success=False, error_message="Mock extraction failure")

        Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_audio_path, "wb") as f:
            f.write(b"MOCK_MP3_AUDIO_HEADER_BYTES")

        return AudioExtractionResult(
            success=True,
            output_path=output_audio_path,
            duration_seconds=min(self.duration, max_duration_seconds),
        )

    async def generate_h264_proxy(
        self,
        video_path: str,
        output_proxy_path: str,
        max_width: int = 1280,
    ) -> bool:
        if not self.should_succeed:
            return False
        Path(output_proxy_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_proxy_path, "wb") as f:
            f.write(b"MOCK_H264_PROXY_BYTES")
        return True

    async def render_edit_cut(
        self,
        video_path: str,
        segments: list[dict[str, Any]],
        output_cut_path: str,
        target_resolution: str = "1080p",
        include_audio: bool = True,
        text_overlays: list[dict[str, Any]] | None = None,
    ) -> RenderCutResult:
        if not self.should_succeed:
            return RenderCutResult(success=False, error_message="Mock render failure")
        Path(output_cut_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_cut_path, "wb") as f:
            f.write(b"MOCK_RENDERED_CUT_BYTES")
        tot_dur = (
            sum(
                max(0.1, float(s.get("end_seconds", 0.0)) - float(s.get("start_seconds", 0.0)))
                for s in segments
            )
            or 15.0
        )
        return RenderCutResult(
            success=True,
            output_path=output_cut_path,
            duration_seconds=round(tot_dur, 2),
            file_size_bytes=1024 * 1024 * 2,
            segment_count=len(segments),
        )

    async def analyze_audio_beats(
        self,
        audio_or_video_path: str,
    ) -> AudioBeatsResult:
        if not self.should_succeed:
            return AudioBeatsResult(success=False, error_message="Mock audio failure")
        beats = [12.8, 19.6, 28.0, 35.0, 48.0]
        timeline = [
            {
                "timestamp": round(i * 0.5, 1),
                "normalized_energy": round(0.2 + (0.6 if i % 4 == 0 else 0.1), 2),
            }
            for i in range(max(1, int(self.duration * 2)))
        ]
        return AudioBeatsResult(
            success=True,
            duration_seconds=self.duration,
            sample_rate=16000,
            peak_dbfs=-0.8,
            mean_dbfs=-21.6,
            estimated_bpm=128.0,
            beat_timestamps=beats,
            energy_timeline=timeline,
            has_speech=False,
        )


def get_media_processing_service(
    settings: Settings | None = Depends(get_settings),
) -> BaseMediaProcessingService:
    """FastAPI dependency for media processing service."""
    if not isinstance(settings, Settings):
        import app.config

        settings = app.config.get_settings()
    if settings.APP_ENV == "test":
        return MockMediaProcessingService()
    if settings.USE_AWS_LAMBDA_MEDIA_WORKER:
        from app.services.aws_lambda_service import AWSLambdaMediaProcessingService

        return AWSLambdaMediaProcessingService(
            function_name=settings.AWS_LAMBDA_MEDIA_FUNCTION,
            region_name=settings.AWS_REGION,
            bucket_name=settings.AWS_S3_BUCKET,
        )
    if settings.USE_MODAL_MEDIA_WORKER:
        from app.services.modal_media_service import ModalMediaProcessingService

        return ModalMediaProcessingService(app_name=settings.MODAL_MEDIA_WORKER_APP)
    return LocalMediaProcessingService()
