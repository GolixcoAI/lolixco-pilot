"""Modal CPU Worker for LolixCopilot Media Processing.

Provides containerized, asynchronous media processing functions running on Modal:
- probe_video_metadata: Extracts duration, resolution, FPS, and stream codecs via ffprobe.
- extract_audio_track: Converts video audio into 16kHz mono WAV/MP3 for multimodal intelligence.
- extract_timestamped_frames: Extracts representative JPEG frames at target timestamp moments.
- extract_scene_keyframes: Detects scene change points and extracts cut-transition frames.

Safeguards:
- Uses ephemeral temporary working directories; no durable state stored in containers.
- Supports short-lived S3 presigned URLs for least-privilege private storage integration.
- Bounded processing timeouts and duration limits to prevent runaway compute costs.
- Pure helper functions exposed for 100% mocked offline unit testing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from typing import Any

import modal

logger = logging.getLogger("lolixcopilot.modal_worker")

# ---------------------------------------------------------------------------
# Modal Container Image & Application Definition
# ---------------------------------------------------------------------------

media_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "curl")
    .pip_install("pydantic>=2.10.0", "boto3>=1.34.0", "httpx>=0.28.0")
)

app = modal.App(
    name="lolixcopilot-media-worker",
    image=media_image,
)

# ---------------------------------------------------------------------------
# Core Subprocess Helpers (Directly testable without remote container invocation)
# ---------------------------------------------------------------------------


def execute_ffprobe(
    file_path_or_url: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    """Execute ffprobe and parse structured JSON metadata."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path_or_url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            logger.warning(
                "ffprobe exited with code %d: %s", proc.returncode, proc.stderr[:200]
            )
            return {}
        return json.loads(proc.stdout)  # type: ignore[no-any-return]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning("ffprobe execution failed: %s", exc)
        return {}


def parse_media_metadata(probe_data: dict[str, Any]) -> dict[str, Any]:
    """Extract normalized media metadata fields from ffprobe JSON output."""
    format_info = probe_data.get("format", {})
    streams = probe_data.get("streams", [])

    duration: float | None = None
    if isinstance(format_info, dict) and "duration" in format_info:
        try:
            duration = float(str(format_info["duration"]))
        except (ValueError, TypeError):
            duration = None

    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec_name: str | None = None
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
                    codec_name = str(stream.get("codec_name", "")) or None
                    r_frame_rate = str(stream.get("r_frame_rate", ""))
                    if "/" in r_frame_rate:
                        num, den = r_frame_rate.split("/", 1)
                        fps = (
                            round(float(num) / float(den), 2)
                            if float(den) > 0
                            else None
                        )
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

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec_name": codec_name,
        "has_audio": has_audio,
        "audio_codec": audio_codec,
        "sample_rate": sample_rate,
        "channels": channels,
    }


def execute_audio_extraction(
    video_path_or_url: str,
    output_audio_path: str,
    max_duration_seconds: float = 60.0,
    output_format: str = "wav",
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    """Extract bounded 16kHz mono audio track using ffmpeg."""
    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)

    codec_args = (
        ["-acodec", "pcm_s16le"]
        if output_format.lower() == "wav"
        else ["-acodec", "libmp3lame", "-b:a", "96k"]
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path_or_url,
        "-t",
        str(max_duration_seconds),
        "-vn",
        *codec_args,
        "-ar",
        "16000",
        "-ac",
        "1",
        output_audio_path,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr[:300]
            logger.warning(
                "ffmpeg audio extraction failed (rc=%d): %s", proc.returncode, err
            )
            return {"success": False, "error_message": err}

        if (
            not os.path.exists(output_audio_path)
            or os.path.getsize(output_audio_path) == 0
        ):
            return {
                "success": False,
                "error_message": "ffmpeg produced empty audio file",
            }

        size_bytes = os.path.getsize(output_audio_path)
        return {
            "success": True,
            "output_path": output_audio_path,
            "file_size_bytes": size_bytes,
            "format": output_format.lower(),
            "max_duration_seconds": max_duration_seconds,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {"success": False, "error_message": str(exc)}


def execute_frame_extraction(
    video_path_or_url: str,
    timestamp_seconds: float,
    output_image_path: str,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Extract a single high-quality JPEG frame at a given timestamp using ffmpeg."""
    os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        video_path_or_url,
        "-vframes",
        "1",
        "-q:v",
        "2",
        output_image_path,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            return {"success": False, "error_message": proc.stderr[:200]}

        if (
            not os.path.exists(output_image_path)
            or os.path.getsize(output_image_path) == 0
        ):
            return {
                "success": False,
                "error_message": "ffmpeg produced empty frame image",
            }

        return {
            "success": True,
            "timestamp_seconds": timestamp_seconds,
            "output_path": output_image_path,
            "file_size_bytes": os.path.getsize(output_image_path),
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {"success": False, "error_message": str(exc)}


def upload_file_to_presigned_url(
    file_path: str,
    presigned_put_url: str,
    content_type: str = "application/octet-stream",
) -> bool:
    """Stream a local file to an S3 presigned PUT URL via standard urllib."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        req = urllib.request.Request(
            presigned_put_url,
            data=data,
            headers={"Content-Type": content_type},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return bool(200 <= resp.status < 300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Presigned upload failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Modal Cloud Functions (CPU Serverless Compute)
# ---------------------------------------------------------------------------


@app.function(
    cpu=2.0,
    memory=2048,
    timeout=60,
)
def probe_video_metadata(presigned_url: str) -> dict[str, Any]:
    """Probe container metadata and streams using ffprobe."""
    raw_probe = execute_ffprobe(presigned_url, timeout_seconds=20.0)
    return parse_media_metadata(raw_probe)


@app.function(
    cpu=2.0,
    memory=2048,
    timeout=90,
)
def extract_audio_track(
    presigned_video_url: str,
    upload_presigned_url: str | None = None,
    max_duration_seconds: float = 60.0,
    output_format: str = "wav",
) -> dict[str, Any]:
    """Extract audio from video, optionally streaming output to S3 presigned PUT URL."""
    suffix = f".{output_format.lower()}"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_audio = os.path.join(tmp_dir, f"audio_track{suffix}")
        result = execute_audio_extraction(
            video_path_or_url=presigned_video_url,
            output_audio_path=tmp_audio,
            max_duration_seconds=max_duration_seconds,
            output_format=output_format,
        )

        if not result["success"]:
            return result

        uploaded = False
        if upload_presigned_url:
            content_type = (
                "audio/wav" if output_format.lower() == "wav" else "audio/mpeg"
            )
            uploaded = upload_file_to_presigned_url(
                tmp_audio, upload_presigned_url, content_type
            )
            result["uploaded"] = uploaded

        return result


@app.function(
    cpu=2.0,
    memory=2048,
    timeout=90,
)
def extract_timestamped_frames(
    presigned_video_url: str,
    timestamps: list[float],
    upload_urls: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Extract frames at specified timestamps and optionally upload to S3."""
    results: list[dict[str, Any]] = []
    upload_map = upload_urls or {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, ts in enumerate(timestamps):
            frame_filename = f"frame_{idx:03d}_{ts:.2f}.jpg"
            tmp_frame = os.path.join(tmp_dir, frame_filename)

            res = execute_frame_extraction(
                video_path_or_url=presigned_video_url,
                timestamp_seconds=ts,
                output_image_path=tmp_frame,
            )

            if res["success"]:
                ts_key = f"{ts:.2f}"
                put_url = upload_map.get(ts_key) or upload_map.get(str(idx))
                if put_url:
                    uploaded = upload_file_to_presigned_url(
                        tmp_frame, put_url, content_type="image/jpeg"
                    )
                    res["uploaded"] = uploaded

            results.append(res)

    return results


@app.function(
    cpu=2.0,
    memory=2048,
    timeout=120,
)
def extract_scene_keyframes(
    presigned_video_url: str,
    scene_threshold: float = 0.3,
    max_frames: int = 10,
    upload_urls: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect visual scene cuts using ffmpeg scene score and extract transition keyframes."""
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        pattern = os.path.join(tmp_dir, "scene_%03d.jpg")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            presigned_video_url,
            "-vf",
            f"select='gt(scene\\,{scene_threshold})',showinfo",
            "-vsync",
            "vfr",
            "-vframes",
            str(max_frames),
            "-q:v",
            "2",
            pattern,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60.0,
                check=False,
            )
            created_files = sorted(
                [
                    os.path.join(tmp_dir, f)
                    for f in os.listdir(tmp_dir)
                    if f.endswith(".jpg")
                ]
            )

            urls = upload_urls or []
            for idx, f_path in enumerate(created_files[:max_frames]):
                item_res: dict[str, Any] = {
                    "scene_index": idx,
                    "file_size_bytes": os.path.getsize(f_path),
                    "success": True,
                }
                if idx < len(urls):
                    uploaded = upload_file_to_presigned_url(
                        f_path, urls[idx], content_type="image/jpeg"
                    )
                    item_res["uploaded"] = uploaded
                results.append(item_res)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scene cut keyframe extraction failed: %s", exc)

    return results


# ---------------------------------------------------------------------------
# Local Dry-Run Entrypoint
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main(
    video_url: str = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
) -> None:
    """Local entrypoint for testing without deploying."""
    print("=" * 60)
    print("LolixCopilot Modal Media Worker — Local Entrypoint")
    print("=" * 60)
    print(f"Target Video URL: {video_url}")
    print("Executing probe_video_metadata...")
    metadata = probe_video_metadata.remote(video_url)
    print("Extracted Metadata:")
    print(json.dumps(metadata, indent=2))
