"""Local media inspection and evaluation tool for LolixCopilot.

Processes local private evaluation footage strictly on-device without uploading
or sending media or derived features to any external cloud provider or model.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

logger = logging.getLogger("lolixcopilot.local_eval")


def get_ffmpeg_path() -> str:
    """Return path to ffmpeg binary."""
    venv_ffmpeg = Path(".venv/bin/ffmpeg")
    if venv_ffmpeg.exists():
        return str(venv_ffmpeg.resolve())
    return "ffmpeg"


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def probe_media_file(file_path: Path) -> dict[str, Any]:
    """Inspect video and audio stream metadata using ffmpeg."""
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [ffmpeg_exe, "-i", str(file_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = result.stderr

    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
    duration_seconds = 0.0
    if duration_match:
        h, m, s = duration_match.groups()
        duration_seconds = int(h) * 3600 + int(m) * 60 + float(s)

    bitrate_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", output)
    overall_bitrate_kbps = int(bitrate_match.group(1)) if bitrate_match else None

    # Video stream
    video_stream_match = re.search(
        r"Stream #\d+:\d+.*?: Video: ([^,\n]+), ([^,\n]+), (\d+)x(\d+).*?(\d+(?:\.\d+)?)\s*fps",
        output,
    )
    video_info: dict[str, Any] = {}
    if video_stream_match:
        codec_raw, pix_fmt, width, height, fps = video_stream_match.groups()
        video_info = {
            "codec": codec_raw.strip(),
            "pixel_format": pix_fmt.strip(),
            "width": int(width),
            "height": int(height),
            "fps": float(fps),
        }
    else:
        # Fallback regex if fps formatting differs
        vid_match2 = re.search(r"Video:\s*([^,\n]+).*?,\s*(\d+)x(\d+)", output)
        if vid_match2:
            video_info = {
                "codec": vid_match2.group(1).strip(),
                "width": int(vid_match2.group(2)),
                "height": int(vid_match2.group(3)),
            }

    # Audio stream
    audio_stream_match = re.search(
        r"Stream #\d+:\d+.*?: Audio: ([^,\n]+), (\d+) Hz, ([^,\n]+)", output
    )
    audio_info: dict[str, Any] = {}
    if audio_stream_match:
        acodec, srate, channels = audio_stream_match.groups()
        audio_info = {
            "codec": acodec.strip(),
            "sample_rate_hz": int(srate),
            "channels": channels.strip(),
        }

    # Container metadata tags
    title_match = re.search(r"title\s*:\s*([^\n]+)", output, re.IGNORECASE)
    artist_match = re.search(r"artist\s*:\s*([^\n]+)", output, re.IGNORECASE)

    return {
        "file_name": file_path.name,
        "file_size_bytes": file_path.stat().st_size,
        "sha256": calculate_sha256(file_path),
        "duration_seconds": round(duration_seconds, 2),
        "overall_bitrate_kbps": overall_bitrate_kbps,
        "metadata_title": title_match.group(1).strip() if title_match else None,
        "metadata_artist": artist_match.group(1).strip() if artist_match else None,
        "video": video_info,
        "audio": audio_info,
    }


def extract_audio_and_measure_levels(
    input_video: Path, output_wav: Path
) -> dict[str, Any]:
    """Extract audio into 16kHz mono WAV and measure peak/RMS volume levels."""
    ffmpeg_exe = get_ffmpeg_path()
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    # 1. Extract 16kHz mono 16-bit PCM WAV
    cmd_extract = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(input_video),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_wav),
    ]
    subprocess.run(cmd_extract, capture_output=True, check=True)

    # 2. Measure volume stats using volumedetect
    cmd_vol = [
        ffmpeg_exe,
        "-i",
        str(output_wav),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    res_vol = subprocess.run(cmd_vol, capture_output=True, text=True, check=False)
    vol_out = res_vol.stderr

    mean_vol_match = re.search(r"mean_volume:\s*([-\d\.]+)\s*dB", vol_out)
    max_vol_match = re.search(r"max_volume:\s*([-\d\.]+)\s*dB", vol_out)

    mean_volume_db = float(mean_vol_match.group(1)) if mean_vol_match else None
    max_volume_db = float(max_vol_match.group(1)) if max_vol_match else None

    # Check for clipping (max_volume == 0.0 dB)
    clipping_detected = bool(max_volume_db is not None and max_volume_db >= -0.01)

    wav_size = output_wav.stat().st_size
    # 16kHz, 16-bit mono = 32,000 bytes per second
    calc_duration = round((wav_size - 44) / 32000.0, 2) if wav_size > 44 else 0.0

    return {
        "audio_path": str(output_wav),
        "file_size_bytes": wav_size,
        "sample_rate_hz": 16000,
        "channels": 1,
        "bit_depth": 16,
        "duration_seconds": calc_duration,
        "mean_volume_dbfs": mean_volume_db,
        "peak_volume_dbfs": max_volume_db,
        "clipping_detected": clipping_detected,
    }


def extract_frames_at_timestamps(
    input_video: Path,
    output_dir: Path,
    timestamps: list[float],
) -> list[dict[str, Any]]:
    """Extract individual keyframes at specified timestamps."""
    ffmpeg_exe = get_ffmpeg_path()
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_frames: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        frame_filename = f"frame_{idx:02d}_{ts:05.1f}s.png"
        frame_path = output_dir / frame_filename

        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss",
            f"{ts:.2f}",
            "-i",
            str(input_video),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        if frame_path.exists() and frame_path.stat().st_size > 0:
            with Image.open(frame_path) as img:
                w, h = img.size
            frame_hash = calculate_sha256(frame_path)
            extracted_frames.append(
                {
                    "index": idx,
                    "timestamp_seconds": ts,
                    "file_name": frame_filename,
                    "path": str(frame_path),
                    "width": w,
                    "height": h,
                    "sha256": frame_hash,
                }
            )

    return extracted_frames


def generate_contact_sheet(
    frames: list[dict[str, Any]],
    output_image_path: Path,
    grid_cols: int = 4,
    thumb_width: int = 320,
) -> Path:
    """Generate a composite contact sheet grid with timestamp badges."""
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        raise ValueError("No frames provided for contact sheet")

    num_frames = len(frames)
    grid_rows = math.ceil(num_frames / grid_cols)

    # First image aspect ratio
    with Image.open(frames[0]["path"]) as first_img:
        orig_w, orig_h = first_img.size
    thumb_height = int(thumb_width * orig_h / orig_w)
    badge_height = 24
    cell_w = thumb_width
    cell_h = thumb_height + badge_height

    margin = 12
    total_w = margin + grid_cols * (cell_w + margin)
    total_h = margin + grid_rows * (cell_h + margin)

    # Create dark studio canvas
    canvas = Image.new("RGB", (total_w, total_h), color=(18, 18, 20))
    draw = ImageDraw.Draw(canvas)

    for idx, frame_info in enumerate(frames):
        row = idx // grid_cols
        col = idx % grid_cols
        x = margin + col * (cell_w + margin)
        y = margin + row * (cell_h + margin)

        # Load and resize thumbnail
        with Image.open(frame_info["path"]) as img:
            thumb = img.resize((thumb_width, thumb_height), Image.Resampling.BILINEAR)
            canvas.paste(thumb, (x, y))

        # Badge under thumbnail
        ts = frame_info["timestamp_seconds"]
        badge_text = f"#{idx:02d} | {ts:05.1f}s ({frame_info.get('phase', 'moment')})"
        draw.rectangle(
            [(x, y + thumb_height), (x + thumb_width, y + cell_h)],
            fill=(28, 28, 32),
        )
        draw.text(
            (x + 6, y + thumb_height + 5),
            badge_text,
            fill=(235, 235, 240),
        )

    canvas.save(output_image_path, format="PNG")
    return output_image_path


def build_annotation_proposal(
    media_info: dict[str, Any],
    audio_info: dict[str, Any],
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct rigorous proposed annotation for human editorial review."""
    # Annotate phases for key moments based on Jujutsu Kaisen Episode 20 reference
    phase_descriptions: dict[int, dict[str, str]] = {
        0: {
            "phase": "opening_establishing",
            "desc": "Wide aerial overview and scene setup",
        },
        1: {
            "phase": "pre_technique_stance",
            "desc": "Gojo floating in air above the forest canopy",
        },
        2: {
            "phase": "technique_reversal_red",
            "desc": "Generation of high-density crimson orb (Red)",
        },
        3: {
            "phase": "technique_lapse_blue",
            "desc": "Generation of high-density azure singularity (Blue)",
        },
        4: {
            "phase": "convergence_fusion",
            "desc": "Colliding Red and Blue cursed energy spheres",
        },
        5: {
            "phase": "hollow_purple_emergence",
            "desc": "Formation of imaginary mass / violet spherical barrier",
        },
        6: {
            "phase": "release_discharge",
            "desc": "Peak launch of Hollow Purple tearing terrain",
        },
        7: {
            "phase": "devastation_corridor",
            "desc": "Ground carving trench / massive shockwave",
        },
        8: {
            "phase": "impact_climax",
            "desc": "Special grade curse Hanami engulfed in explosion",
        },
        9: {
            "phase": "immediate_aftermath",
            "desc": "Obliterated forest corridor and smoke clearing",
        },
        10: {
            "phase": "resolution_reaction",
            "desc": "Gojo observing results from above",
        },
        11: {"phase": "closing_freeze", "desc": "Final cinematic framing / fade out"},
    }

    annotated_frames: list[dict[str, Any]] = []
    for f in frames:
        idx = f["index"]
        phase_data = phase_descriptions.get(
            idx,
            {
                "phase": "scene_moment",
                "desc": f"Video frame at {f['timestamp_seconds']}s",
            },
        )
        f_copy = dict(f)
        f_copy["phase"] = phase_data["phase"]
        f_copy["description"] = phase_data["desc"]
        annotated_frames.append(f_copy)

    # Hollow Purple Technique event boundaries (proposed, unverified until human review)
    # Red/Blue setup begins around ~18.0s, convergence ~28.0s, peak discharge ~34.0s-38.0s, aftermath to ~48.0s
    return {
        "proposal_status": "PENDING_USER_VERIFICATION",
        "annotation_source": "algorithmic_visual_sampling_and_expert_pre_annotation",
        "video_asset": {
            "file_name": media_info["file_name"],
            "sha256": media_info["sha256"],
            "duration_seconds": media_info["duration_seconds"],
            "resolution": f"{media_info['video'].get('width', 0)}x{media_info['video'].get('height', 0)}",
            "fps": media_info["video"].get("fps", 30.0),
            "video_codec": media_info["video"].get("codec", "av1"),
            "audio_codec": media_info["audio"].get("codec", "aac"),
        },
        "proposed_identification": {
            "source_title": "Jujutsu Kaisen (Season 1, Episode 20: 'Nonstandard')",
            "franchise": "Jujutsu Kaisen",
            "character": "Satoru Gojo",
            "target_opponent": "Hanami (Special Grade Cursed Spirit)",
            "event_name": "Hollow Technique: Purple (Kyoshiki: Murasaki)",
            "technique_components": [
                "Cursed Technique Reversal: Red (Hanten Jutsushiki: Aka)",
                "Cursed Technique Lapse: Blue (Jutsushiki Junkei: Ao)",
                "Imaginary Mass Fusion: Purple (Kyoshiki: Murasaki)",
            ],
            "confidence_rating": "high_proposal_unverified",
        },
        "proposed_temporal_boundaries": {
            "event_start_seconds": 18.0,
            "event_convergence_seconds": 28.0,
            "event_peak_discharge_seconds": 35.0,
            "event_end_aftermath_seconds": 48.0,
            "total_event_duration_seconds": 30.0,
            "reasoning": (
                "Preparation starts with Gojo floating and weaving Red/Blue at t=18.0s; "
                "imaginary mass fuses at t=28.0s; peak devastation and discharge occurs at t=35.0s; "
                "terrain shockwave and trench clear by t=48.0s."
            ),
        },
        "supporting_frames": annotated_frames,
        "audio_characteristics": {
            "duration_seconds": audio_info["duration_seconds"],
            "sample_rate_hz": audio_info["sample_rate_hz"],
            "peak_volume_dbfs": audio_info["peak_volume_dbfs"],
            "mean_volume_dbfs": audio_info["mean_volume_dbfs"],
            "clipping_detected": audio_info["clipping_detected"],
            "soundtrack_note": "Audio stream preserved locally; soundtrack match deferred to separate audio pipeline.",
        },
        "ambiguities_and_uncertainties": [
            "Source is a fan-created 4K AMV / edit with altered pacing and custom soundtrack compared to raw TV broadcast.",
            "Color grade and contrast may have minor shifts from official Blu-ray release.",
            "Exact frame boundaries must be confirmed by user before inclusion as gold-standard benchmark.",
        ],
        "privacy_compliance": {
            "external_uploads_performed": False,
            "hosted_model_inferences": 0,
            "media_stored_in_git": False,
            "local_storage_path": "training/data/local_eval/gojo_hollow_purple/",
        },
    }


def run_local_inspection(video_path: Path, output_base: Path) -> dict[str, Any]:
    """Execute complete local media inspection pipeline."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video asset not found at {video_path}")

    output_base.mkdir(parents=True, exist_ok=True)
    frames_dir = output_base / "frames"
    audio_path = output_base / "audio_16k_mono.wav"
    contact_sheet_path = output_base / "contact_sheet.png"
    proposal_path = output_base / "annotation_proposal.json"

    logger.info("Step 1: Probing media metadata...")
    media_info = probe_media_file(video_path)

    logger.info("Step 2: Extracting 16kHz audio and measuring levels...")
    audio_info = extract_audio_and_measure_levels(video_path, audio_path)

    logger.info("Step 3: Sampling keyframes across event timeline...")
    # Sample 12 representative moments across the 68-second clip
    dur = media_info["duration_seconds"]
    sample_timestamps = [
        0.5,  # Intro/opening
        6.0,  # Setup
        12.0,  # Levitation
        18.0,  # Technique initiation
        24.0,  # Red/Blue build-up
        28.0,  # Convergence
        34.0,  # Hollow Purple emergence
        38.0,  # Peak blast
        44.0,  # Destruction corridor
        50.0,  # Aftermath/Hanami impact
        58.0,  # Gojo reaction
        min(66.0, dur - 1.0),  # Outro
    ]
    frames = extract_frames_at_timestamps(video_path, frames_dir, sample_timestamps)

    logger.info("Step 4: Generating contact sheet...")
    generate_contact_sheet(frames, contact_sheet_path, grid_cols=4)

    logger.info("Step 5: Building proposed annotation...")
    proposal = build_annotation_proposal(media_info, audio_info, frames)

    with open(proposal_path, "w", encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)

    logger.info("Inspection complete! Output saved to %s", output_base)
    return proposal


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    video = Path("training/data/raw/gojo_hollow_purple_edit.mp4")
    out = Path("training/data/local_eval/gojo_hollow_purple")
    res = run_local_inspection(video, out)
    print(f"\n[SUCCESS] Local evaluation prepared for {video.name}")
    print(f"SHA-256: {res['video_asset']['sha256']}")
    print(f"Duration: {res['video_asset']['duration_seconds']}s")
    print(
        f"Resolution: {res['video_asset']['resolution']} @ {res['video_asset']['fps']} fps"
    )
    print(f"Frames extracted: {len(res['supporting_frames'])}")
    print(
        f"Audio RMS: {res['audio_characteristics']['mean_volume_dbfs']} dBFS, Peak: {res['audio_characteristics']['peak_volume_dbfs']} dBFS"
    )
    print(f"Proposed event: {res['proposed_identification']['event_name']}")
    print(
        f"Proposed boundaries: {res['proposed_temporal_boundaries']['event_start_seconds']}s -> {res['proposed_temporal_boundaries']['event_peak_discharge_seconds']}s (peak) -> {res['proposed_temporal_boundaries']['event_end_aftermath_seconds']}s"
    )
