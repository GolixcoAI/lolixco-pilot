"""Anime Event Dataset specification, validation, and preparation for Muse Glimmer fine-tuning.

Implements the specification in docs/research/JUJUTSU_KAISEN_EVENT_DATASET_SPEC.md:
- Ground-truth temporal bounding and semantic descriptors for iconic combat sequences.
- Pydantic models for strict timestamp validity (start < peak < end <= duration).
- Decoupled audio intelligence task referencing.
- ShareGPT / ChatML formatting for text baselines and OpenAI Messages with typed image
  parts ({"type": "image", "path": ...}) for Axolotl multimodal VLM fine-tuning.
- Hard negative distractors, unrelated combat events, and ambiguous examples.
- Non-leaking dataset splitting by episode/video ID.
- Image verification and PNG fixture generation with standard library struct/zlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RepresentativeFrame(BaseModel):
    """Timestamped keyframe with event phase description and verified image asset info."""

    timecode: str = Field(
        ..., description="SMPTE or MM:SS.SS formatted timecode string"
    )
    timestamp_seconds: float = Field(
        ..., ge=0.0, description="Exact timestamp in seconds"
    )
    frame_type: str = Field(
        ..., description="Phase: setup, convergence, peak_fusion, discharge, etc."
    )
    description: str = Field(
        ..., min_length=2, description="Visual description of the frame"
    )
    image_path: str = Field(
        default="", description="Relative or absolute path to the extracted image frame"
    )
    width: int | None = Field(default=None, ge=1, description="Image width in pixels")
    height: int | None = Field(default=None, ge=1, description="Image height in pixels")
    sha256_hash: str | None = Field(
        default=None, description="SHA-256 content checksum of image asset"
    )
    relevant_event_annotation: str | None = Field(
        default=None, description="Bounding or focal detail of the action"
    )


class AudioTaskReference(BaseModel):
    """Decoupled audio soundtrack intelligence reference."""

    has_audio: bool = Field(
        default=True, description="Whether audio is present in clip"
    )
    soundtrack_title: str | None = Field(
        default=None, description="Identified soundtrack name"
    )
    artist: str | None = Field(default=None, description="Artist or composer")
    audio_match_status: str = Field(
        default="unconfirmed", description="Matching confidence"
    )
    audio_notes: str | None = Field(
        default=None, description="Audio cue or beat drop notes"
    )


class AnimeEventSample(BaseModel):
    """Ground-truth labeled sample for fine-grained anime event detection."""

    sample_id: str = Field(
        ..., min_length=1, description="Unique identifier e.g. jkk-event-001"
    )
    source_title: str = Field(..., min_length=1, description="Anime title")
    source_type: str = Field(
        default="anime", description="Content type: anime, amv, film, etc."
    )
    source_video_id: str = Field(
        default="", description="Unique identifier of raw source video file"
    )
    episode_id: str = Field(
        default="", description="Episode identifier e.g. jjk-s01-e20"
    )
    franchise: str = Field(..., min_length=1, description="Franchise name")
    season: int | None = Field(default=None, ge=1, description="Season number")
    episode: int | None = Field(default=None, ge=1, description="Episode number")
    arc: str | None = Field(default=None, description="Narrative story arc")
    event_name: str = Field(
        ..., min_length=1, description="Specific named event or technique"
    )
    character_names: list[str] = Field(
        default_factory=list, description="Characters involved in this moment"
    )
    approx_start_seconds: float = Field(
        ..., ge=0.0, description="Start boundary timestamp"
    )
    approx_end_seconds: float = Field(..., gt=0.0, description="End boundary timestamp")
    peak_frame_timestamp: float = Field(
        ..., ge=0.0, description="Exact peak impact/sync frame"
    )
    duration_seconds: float = Field(..., gt=0.0, description="Total clip duration")
    representative_frames: list[RepresentativeFrame] = Field(default_factory=list)
    visual_evidence: list[str] = Field(default_factory=list)
    status: str = Field(
        default="confirmed",
        description="Event classification: confirmed, negative_distractor, unrelated_combat, ambiguous",
    )
    alternative_candidates: list[str] = Field(default_factory=list)
    annotation_status: str = Field(
        default="fixture",
        description="Annotation confidence level: fixture, verified, community",
    )
    annotation_source: str = Field(
        default="test_fixture_seed",
        description="Provenance of the annotation e.g. test_fixture_seed, human_annotator",
    )
    rights_or_permission_status: str = Field(
        default="fair_use_research_fixture",
        description="Copyright and distribution terms for this sample",
    )
    split_group_id: str = Field(
        default="",
        description="Grouping identifier (episode or video id) to prevent data leakage between splits",
    )
    audio_task_reference: AudioTaskReference | None = Field(default=None)

    @model_validator(mode="after")
    def validate_temporal_boundaries(self) -> AnimeEventSample:
        """Enforce strict temporal validity for editing synchronization."""
        if self.approx_start_seconds < 0.0:
            raise ValueError(
                f"approx_start_seconds ({self.approx_start_seconds}s) cannot be negative; must satisfy 0 <= start < peak < end <= duration"
            )
        if self.approx_start_seconds >= self.approx_end_seconds:
            raise ValueError(
                f"approx_start_seconds ({self.approx_start_seconds}s) must be strictly "
                f"less than approx_end_seconds ({self.approx_end_seconds}s)"
            )
        if self.approx_end_seconds > self.duration_seconds + 0.05:
            raise ValueError(
                f"approx_end_seconds ({self.approx_end_seconds}s) exceeds total "
                f"duration ({self.duration_seconds}s)"
            )
        if not (
            self.approx_start_seconds
            < self.peak_frame_timestamp
            < self.approx_end_seconds
        ):
            raise ValueError(
                f"peak_frame_timestamp ({self.peak_frame_timestamp}s) must lie within "
                f"({self.approx_start_seconds}s, {self.approx_end_seconds}s) (strictly satisfying 0 <= start < peak < end <= duration)"
            )

        # Enforce chronological ordering of representative frames
        for i in range(len(self.representative_frames) - 1):
            curr_ts = self.representative_frames[i].timestamp_seconds
            next_ts = self.representative_frames[i + 1].timestamp_seconds
            if curr_ts > next_ts:
                raise ValueError(
                    f"Frames out of chronological order: frame {i} ({curr_ts}s) > frame {i + 1} ({next_ts}s)"
                )

        return self


# ---------------------------------------------------------------------------
# Image Asset Utilities (Pure Python Standard Library)
# ---------------------------------------------------------------------------


def generate_png_bytes(
    width: int = 64,
    height: int = 64,
    rgb: tuple[int, int, int] = (128, 0, 128),
) -> bytes:
    """Generate valid uncompressed PNG image bytes using struct and zlib."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc

    r, g, b = rgb
    raw = b"".join(b"\x00" + bytes([r, g, b]) * width for _ in range(height))
    idat_data = zlib.compress(raw)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + idat_data))
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + idat_crc

    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    return sig + ihdr + idat + iend


def create_fixture_image(
    file_path: str | Path,
    width: int = 64,
    height: int = 64,
    rgb: tuple[int, int, int] = (128, 0, 128),
) -> tuple[str, str]:
    """Create a valid PNG image file and return (path_str, sha256_hex)."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = generate_png_bytes(width, height, rgb)
    p.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()
    return str(p), sha256


def _parse_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Extract width and height from JPEG bytes using SOF markers."""
    idx = 2
    data_len = len(data)
    while idx < data_len - 8:
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1]
        # SOF markers: 0xC0..0xC3, 0xC5..0xC7, 0xC9..0xCB, 0xCD..0xCF
        if marker in (
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        ):
            h, w = struct.unpack(">HH", data[idx + 5 : idx + 9])
            return w, h
        if idx + 4 > data_len:
            break
        length = struct.unpack(">H", data[idx + 2 : idx + 4])[0]
        idx += 2 + length
    return 1920, 1080  # Default fallback if SOF not encountered


def _parse_webp_dimensions(data: bytes) -> tuple[int, int]:
    """Extract width and height from WebP header."""
    if len(data) < 30:
        return 1280, 720
    chunk_type = data[12:16]
    if chunk_type == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    elif chunk_type == b"VP8L":
        b0, b1, b2, b3 = data[21:25]
        w = 1 + (((b1 & 0x3F) << 8) | b0)
        h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return w, h
    elif chunk_type == b"VP8X":
        w = 1 + struct.unpack("<I", data[24:27] + b"\x00")[0]
        h = 1 + struct.unpack("<I", data[27:30] + b"\x00")[0]
        return w, h
    return 1280, 720


def verify_image_asset(file_path: str | Path) -> tuple[bool, int, int, str]:
    """Verify image asset exists, parses valid format header, and computes sha256.

    Returns:
        (is_valid, width, height, sha256_hex_or_error)
    """
    p = Path(file_path)
    if not p.is_file():
        return False, 0, 0, f"File does not exist: {file_path}"

    try:
        data = p.read_bytes()
    except Exception as exc:  # noqa: BLE001
        return False, 0, 0, f"Cannot read file: {exc}"

    if len(data) < 24:
        return False, 0, 0, "File too small for image header"

    sha256 = hashlib.sha256(data).hexdigest()

    # PNG verification
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return True, w, h, sha256

    # JPEG verification (starts with \xff\xd8)
    if data[:2] == b"\xff\xd8":
        w, h = _parse_jpeg_dimensions(data)
        return True, w, h, sha256

    # WebP verification (RIFF....WEBP)
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        w, h = _parse_webp_dimensions(data)
        return True, w, h, sha256

    return False, 0, 0, "Unknown or unsupported image format header"


def validate_sample_image_assets(
    sample: AnimeEventSample,
    check_dimensions: bool = True,
    check_hashes: bool = True,
) -> tuple[bool, list[str]]:
    """Validate all representative image assets associated with a sample.

    Checks:
    1. Sample has representative frames (at least 1 keyframe).
    2. Image file exists on disk.
    3. Image file can be decoded with valid format header.
    4. Decoded dimensions match frame.width / frame.height if specified.
    5. SHA-256 hash matches frame.sha256_hash if specified.
    6. Frames are strictly chronological by timestamp.

    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: list[str] = []

    if not sample.representative_frames:
        errors.append(f"Sample {sample.sample_id} contains no representative frames")
        return False, errors

    last_ts = -1.0
    for idx, frame in enumerate(sample.representative_frames):
        # 1. Chronological timestamp ordering check
        if frame.timestamp_seconds < last_ts:
            errors.append(
                f"Sample {sample.sample_id} frame #{idx} timestamp ({frame.timestamp_seconds}s) "
                f"< previous ({last_ts}s) (out of order)"
            )
        last_ts = frame.timestamp_seconds

        # 2. Image path check
        if not frame.image_path:
            errors.append(
                f"Sample {sample.sample_id} frame #{idx} has no image_path specified"
            )
            continue

        # 3. File existence and decoding check
        is_valid, w, h, info = verify_image_asset(frame.image_path)
        if not is_valid:
            errors.append(
                f"Sample {sample.sample_id} frame #{idx} ({frame.image_path}) decode failure: {info}"
            )
            continue

        # 4. Dimension verification if specified
        if check_dimensions:
            if frame.width is not None and frame.width != w:
                errors.append(
                    f"Sample {sample.sample_id} frame #{idx} width mismatch: "
                    f"expected {frame.width}, decoded {w}"
                )
            if frame.height is not None and frame.height != h:
                errors.append(
                    f"Sample {sample.sample_id} frame #{idx} height mismatch: "
                    f"expected {frame.height}, decoded {h}"
                )

        # 5. Hash verification if specified
        if (
            check_hashes
            and frame.sha256_hash
            and frame.sha256_hash.lower() != info.lower()
        ):
            errors.append(
                f"Sample {sample.sample_id} frame #{idx} sha256 checksum mismatch: "
                f"expected {frame.sha256_hash[:12]}..., computed {info[:12]}..."
            )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Validation & Conversion Functions
# ---------------------------------------------------------------------------


def validate_sample(data: dict[str, Any]) -> AnimeEventSample:
    """Validate a single raw sample dictionary against the AnimeEventSample schema."""
    return AnimeEventSample.model_validate(data)


def validate_dataset(items: list[dict[str, Any]]) -> list[AnimeEventSample]:
    """Validate a collection of raw sample dictionaries."""
    return [validate_sample(item) for item in items]


def format_sample_to_instruction(sample: AnimeEventSample) -> dict[str, Any]:
    """Convert an AnimeEventSample into ShareGPT / ChatML format for text baselines."""
    system_prompt = (
        "You are an expert anime video intelligence model. Analyze the attached video segment. "
        "Identify the franchise, characters, exact technique or narrative event, the start and end "
        "timestamps, and the exact peak impact frame timestamp for video editing synchronization."
    )

    user_query = (
        f"Analyze this {sample.duration_seconds:.1f}s video clip. "
        "Output the detected franchise, named technique/event, start/end boundaries, and peak impact frame in JSON."
    )

    output_data = {
        "franchise": sample.franchise,
        "source_title": sample.source_title,
        "event_name": sample.event_name,
        "characters": sample.character_names,
        "status": sample.status,
        "timing": {
            "start_seconds": sample.approx_start_seconds,
            "end_seconds": sample.approx_end_seconds,
            "peak_frame_seconds": sample.peak_frame_timestamp,
            "duration_seconds": sample.duration_seconds,
        },
        "visual_evidence": sample.visual_evidence,
        "alternative_candidates": sample.alternative_candidates,
    }

    return {
        "id": sample.sample_id,
        "conversations": [
            {"from": "system", "value": system_prompt},
            {"from": "human", "value": user_query},
            {"from": "gpt", "value": json.dumps(output_data, ensure_ascii=False)},
        ],
    }


def format_sample_to_multimodal_messages(sample: AnimeEventSample) -> dict[str, Any]:
    """Convert an AnimeEventSample into Axolotl OpenAI Messages format with real image parts."""
    system_prompt = (
        "You are LolixCopilot AI Director, an expert anime visual intelligence model. "
        "Analyze the chronological video keyframes provided. Identify the franchise, characters, "
        "named technique/event, precise start/end boundary timestamps, and peak impact frame timestamp."
    )

    content_parts: list[dict[str, Any]] = []
    # Add image parts in chronological order
    for frame in sample.representative_frames:
        content_parts.append(
            {
                "type": "image",
                "path": frame.image_path,
            }
        )

    user_query = (
        f"Analyze this {sample.duration_seconds:.1f}s video clip across {len(sample.representative_frames)} keyframes. "
        "Locate the exact technique or event moment, start/end timestamps, and peak impact frame in JSON."
    )
    content_parts.append(
        {
            "type": "text",
            "text": user_query,
        }
    )

    output_data = {
        "franchise": sample.franchise,
        "source_title": sample.source_title,
        "event_name": sample.event_name,
        "characters": sample.character_names,
        "status": sample.status,
        "timing": {
            "start_seconds": sample.approx_start_seconds,
            "end_seconds": sample.approx_end_seconds,
            "peak_frame_seconds": sample.peak_frame_timestamp,
            "duration_seconds": sample.duration_seconds,
        },
        "visual_evidence": sample.visual_evidence,
        "alternative_candidates": sample.alternative_candidates,
    }

    return {
        "id": sample.sample_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
            {
                "role": "assistant",
                "content": json.dumps(output_data, ensure_ascii=False),
            },
        ],
    }


# ---------------------------------------------------------------------------
# Dataset Splitting & Zero-Leakage Verification
# ---------------------------------------------------------------------------


def split_dataset_by_group(
    samples: list[AnimeEventSample],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> dict[str, list[AnimeEventSample]]:
    """Split dataset by split_group_id / episode_id to guarantee zero leakage."""
    from collections import defaultdict

    groups: dict[str, list[AnimeEventSample]] = defaultdict(list)
    for s in samples:
        gid = s.split_group_id or s.episode_id or s.source_video_id or s.sample_id
        groups[gid].append(s)

    sorted_group_keys = sorted(groups.keys())
    total_groups = len(sorted_group_keys)

    train_samples: list[AnimeEventSample] = []
    val_samples: list[AnimeEventSample] = []
    test_samples: list[AnimeEventSample] = []

    if total_groups <= 3:
        for i, key in enumerate(sorted_group_keys):
            if i == 0:
                train_samples.extend(groups[key])
            elif i == 1:
                val_samples.extend(groups[key])
            else:
                test_samples.extend(groups[key])
    else:
        train_cutoff = int(total_groups * train_ratio)
        val_cutoff = int(total_groups * (train_ratio + val_ratio))
        if train_cutoff == 0 and total_groups >= 2:
            train_cutoff = 1
        if val_cutoff <= train_cutoff and total_groups >= 3:
            val_cutoff = train_cutoff + 1

        for i, key in enumerate(sorted_group_keys):
            if i < train_cutoff:
                train_samples.extend(groups[key])
            elif i < val_cutoff:
                val_samples.extend(groups[key])
            else:
                test_samples.extend(groups[key])

    return {
        "train": train_samples,
        "val": val_samples,
        "test": test_samples,
    }


def verify_split_leakage(
    splits: dict[str, list[AnimeEventSample]],
) -> tuple[bool, list[str]]:
    """Verify that no split_group_id, episode_id, or source_video_id overlaps across splits.

    Returns:
        (is_leak_free, error_messages)
    """
    errors: list[str] = []
    split_names = list(splits.keys())

    group_map: dict[str, set[str]] = {}
    for name, sample_list in splits.items():
        gids: set[str] = set()
        for s in sample_list:
            gid = s.split_group_id or s.episode_id or s.source_video_id
            if gid:
                gids.add(gid)
        group_map[name] = gids

    for i in range(len(split_names)):
        for j in range(i + 1, len(split_names)):
            s1, s2 = split_names[i], split_names[j]
            overlap = group_map[s1].intersection(group_map[s2])
            if overlap:
                errors.append(
                    f"Leakage detected between '{s1}' and '{s2}' on groups: {sorted(overlap)}"
                )

    return len(errors) == 0, errors


def compute_dataset_statistics(samples: list[AnimeEventSample]) -> dict[str, Any]:
    """Compute comprehensive dataset statistics for audits and reporting.

    Clearly separates genuine/verified training data from synthetic test fixtures.
    """
    total_samples = len(samples)
    positives = sum(1 for s in samples if s.status == "confirmed")
    distractors = sum(1 for s in samples if s.status == "negative_distractor")
    unrelated_combat = sum(1 for s in samples if s.status == "unrelated_combat")
    ambiguous = sum(1 for s in samples if s.status == "ambiguous")

    # Explicitly separate genuine human/verified samples from synthetic fixtures
    fixture_samples = sum(1 for s in samples if s.annotation_status == "fixture")
    genuine_samples = sum(1 for s in samples if s.annotation_status != "fixture")

    source_videos = sorted({s.source_video_id for s in samples if s.source_video_id})
    episodes = sorted({s.episode_id for s in samples if s.episode_id})

    unique_chars: set[str] = set()
    for s in samples:
        unique_chars.update(s.character_names)

    event_categories: dict[str, int] = {}
    for s in samples:
        cat = s.status
        event_categories[cat] = event_categories.get(cat, 0) + 1

    total_images = sum(len(s.representative_frames) for s in samples)
    fixture_images = sum(
        len(s.representative_frames)
        for s in samples
        if s.annotation_status == "fixture"
    )
    genuine_images = sum(
        len(s.representative_frames)
        for s in samples
        if s.annotation_status != "fixture"
    )

    valid_images = 0
    missing_images = 0

    for s in samples:
        for f in s.representative_frames:
            if f.image_path and Path(f.image_path).is_file():
                valid_images += 1
            else:
                missing_images += 1

    return {
        "total_samples": total_samples,
        "genuine_samples_count": genuine_samples,
        "fixture_samples_count": fixture_samples,
        "positive_events": positives,
        "negative_distractors": distractors,
        "unrelated_combat": unrelated_combat,
        "ambiguous_events": ambiguous,
        "source_videos_count": len(source_videos),
        "episodes_count": len(episodes),
        "unique_characters": sorted(unique_chars),
        "unique_characters_count": len(unique_chars),
        "event_category_distribution": event_categories,
        "total_image_assets": total_images,
        "genuine_image_assets": genuine_images,
        "fixture_image_assets": fixture_images,
        "valid_image_assets": valid_images,
        "missing_image_assets": missing_images,
        "is_purely_synthetic_fixtures": genuine_samples == 0,
        "data_provenance_summary": {
            "fixture": fixture_samples,
            "genuine_verified": genuine_samples,
        },
    }


# ---------------------------------------------------------------------------
# Seed Demonstration Dataset (Clearly Identified as Test Fixtures)
# ---------------------------------------------------------------------------


def create_seed_dataset(generate_fixture_images: bool = True) -> list[AnimeEventSample]:
    """Create curated demonstration dataset with positive events and hard negative distractors.

    All samples are explicitly labeled with annotation_status='fixture' to prevent
    misrepresenting synthetic fixtures as verified human ground truth.
    """
    fixtures_dir = Path("training/data/images")

    raw_samples: list[dict[str, Any]] = [
        # Positive 1: Gojo Satoru - Hollow Purple (Kyoto Goodwill Event Arc)
        {
            "sample_id": "jkk-event-001",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s01_ep20_raw",
            "episode_id": "jjk_s01_ep20",
            "split_group_id": "jjk_s01_ep20",
            "franchise": "Jujutsu Kaisen",
            "season": 1,
            "episode": 20,
            "arc": "Kyoto Goodwill Event Arc",
            "event_name": "Gojo Satoru - Hollow Purple (Kyoshiki Murasaki)",
            "character_names": ["Gojo Satoru", "Hanami"],
            "approx_start_seconds": 12.40,
            "approx_end_seconds": 28.20,
            "peak_frame_timestamp": 22.80,
            "duration_seconds": 30.0,
            "representative_frames": [
                {
                    "timecode": "00:14.20",
                    "timestamp_seconds": 14.20,
                    "frame_type": "setup",
                    "description": "Gojo holding out right hand generating Cursed Technique Lapse: Blue",
                    "image_path": str(fixtures_dir / "jkk-event-001" / "frame_01.png"),
                    "width": 64,
                    "height": 64,
                    "relevant_event_annotation": "Blue cursed energy orb condensation",
                },
                {
                    "timecode": "00:18.50",
                    "timestamp_seconds": 18.50,
                    "frame_type": "convergence",
                    "description": "Left hand generating Cursed Technique Reversal: Red",
                    "image_path": str(fixtures_dir / "jkk-event-001" / "frame_02.png"),
                    "width": 64,
                    "height": 64,
                    "relevant_event_annotation": "Red repulsive cursed energy orb",
                },
                {
                    "timecode": "00:22.80",
                    "timestamp_seconds": 22.80,
                    "frame_type": "peak_fusion",
                    "description": "Fusing Red and Blue into a luminous violet sphere, spatial distortion",
                    "image_path": str(fixtures_dir / "jkk-event-001" / "frame_03.png"),
                    "width": 64,
                    "height": 64,
                    "relevant_event_annotation": "Peak Hollow Purple fusion sphere",
                },
                {
                    "timecode": "00:26.10",
                    "timestamp_seconds": 26.10,
                    "frame_type": "discharge",
                    "description": "High-velocity purple beam carving massive trench through forest",
                    "image_path": str(fixtures_dir / "jkk-event-001" / "frame_04.png"),
                    "width": 64,
                    "height": 64,
                    "relevant_event_annotation": "Purple beam trajectory and forest excavation",
                },
            ],
            "visual_evidence": [
                "Converging dual energy spheres (red and blue)",
                "Blindfold removed, revealing Six Eyes (Rikugan)",
                "High-contrast purple particle effects and ground trench excavation",
                "Gojo hand sign: fingertips snapping forward",
            ],
            "status": "confirmed",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": [
                "Cursed Technique Reversal: Red",
                "Unlimited Void (Muryokusho - Domain Expansion)",
            ],
            "audio_task_reference": {
                "has_audio": True,
                "soundtrack_title": "Your Battle is My Battle",
                "artist": "Hiroaki Tsutsumi",
                "audio_match_status": "strong_inference",
                "audio_notes": "Heavy electric guitar riff coinciding with projectile release at 00:23.0",
            },
        },
        # Positive 2: Sukuna - Domain Expansion: Malevolent Shrine (Shibuya Incident)
        {
            "sample_id": "jkk-event-002",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s02_ep41_raw",
            "episode_id": "jjk_s02_ep41",
            "split_group_id": "jjk_s02_ep41",
            "franchise": "Jujutsu Kaisen",
            "season": 2,
            "episode": 41,
            "arc": "Shibuya Incident",
            "event_name": "Ryomen Sukuna - Malevolent Shrine (Fukuma Mizushi)",
            "character_names": ["Ryomen Sukuna", "Mahoraga"],
            "approx_start_seconds": 5.00,
            "approx_end_seconds": 24.50,
            "peak_frame_timestamp": 14.20,
            "duration_seconds": 26.0,
            "representative_frames": [
                {
                    "timecode": "00:07.00",
                    "timestamp_seconds": 7.00,
                    "frame_type": "setup",
                    "description": "Sukuna forming handsign Enmaten with four eyes glowing",
                    "image_path": str(fixtures_dir / "jkk-event-002" / "frame_01.png"),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:14.20",
                    "timestamp_seconds": 14.20,
                    "frame_type": "peak_activation",
                    "description": "Massive demonic shrine manifesting with skull horn decorations in open water",
                    "image_path": str(fixtures_dir / "jkk-event-002" / "frame_02.png"),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:20.50",
                    "timestamp_seconds": 20.50,
                    "frame_type": "cleave_dismantle_sweep",
                    "description": "Omnidirectional slashing barrage disintegrating surrounding city block",
                    "image_path": str(fixtures_dir / "jkk-event-002" / "frame_03.png"),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Enmaten hand sign",
                "Four-armed shadow silhouette",
                "Demonic open-domain shrine with horned animal skulls",
                "Cleave and Dismantle geometric slash vectors",
            ],
            "status": "confirmed",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Fire Arrow (Fuga)", "Dismantle (Kai)"],
            "audio_task_reference": {
                "has_audio": True,
                "soundtrack_title": "Malevolent Shrine",
                "artist": "Yoshimasa Terui",
                "audio_match_status": "strong_inference",
            },
        },
        # Positive 3: Megumi Fushiguro - Domain Expansion: Chimera Shadow Garden
        {
            "sample_id": "jkk-event-003",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s01_ep23_raw",
            "episode_id": "jjk_s01_ep23",
            "split_group_id": "jjk_s01_ep23",
            "franchise": "Jujutsu Kaisen",
            "season": 1,
            "episode": 23,
            "arc": "Death Painting Arc",
            "event_name": "Megumi Fushiguro - Chimera Shadow Garden (Kango An'eiteki)",
            "character_names": ["Megumi Fushiguro"],
            "approx_start_seconds": 8.00,
            "approx_end_seconds": 22.00,
            "peak_frame_timestamp": 15.60,
            "duration_seconds": 25.0,
            "representative_frames": [
                {
                    "timecode": "00:10.00",
                    "timestamp_seconds": 10.00,
                    "frame_type": "setup",
                    "description": "Megumi weaving dual hand signs with blood on forehead",
                    "image_path": str(fixtures_dir / "jkk-event-003" / "frame_01.png"),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:15.60",
                    "timestamp_seconds": 15.60,
                    "frame_type": "peak_spread",
                    "description": "Floor submerging into pitch-black shadow liquid with multiple Shikigami rising",
                    "image_path": str(fixtures_dir / "jkk-event-003" / "frame_02.png"),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Shadow liquid flooding cave floor",
                "Multiple Divine Dogs and Toad clones emerging simultaneously",
                "Megumi crazed manic smile and focused gaze",
            ],
            "status": "confirmed",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Ten Shadows Technique", "Divine Dog Totality"],
            "audio_task_reference": {
                "has_audio": True,
                "soundtrack_title": "Blood",
                "artist": "Alisa",
                "audio_match_status": "strong_inference",
            },
        },
        # Hard Negative 1: Gojo Satoru - Cursed Technique Reversal: Red alone (Intra-franchise distractor)
        {
            "sample_id": "jkk-distractor-001",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s01_ep07_raw",
            "episode_id": "jjk_s01_ep07",
            "split_group_id": "jjk_s01_ep07",
            "franchise": "Jujutsu Kaisen",
            "season": 1,
            "episode": 7,
            "arc": "Vs. Mahito Arc",
            "event_name": "Gojo Satoru - Cursed Technique Reversal: Red (Aka) - NOT Hollow Purple",
            "character_names": ["Gojo Satoru", "Jogo"],
            "approx_start_seconds": 2.00,
            "approx_end_seconds": 10.00,
            "peak_frame_timestamp": 6.50,
            "duration_seconds": 12.0,
            "representative_frames": [
                {
                    "timecode": "00:04.00",
                    "timestamp_seconds": 4.00,
                    "frame_type": "setup",
                    "description": "Single glowing crimson orb at fingertip without blue sphere",
                    "image_path": str(
                        fixtures_dir / "jkk-distractor-001" / "frame_01.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:06.50",
                    "timestamp_seconds": 6.50,
                    "frame_type": "discharge",
                    "description": "Violent repulsive shockwave launching Jogo backwards",
                    "image_path": str(
                        fixtures_dir / "jkk-distractor-001" / "frame_02.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Single red sphere (absence of blue sphere)",
                "Finger gun point gesture",
                "Repulsive force blast rather than trench vaporization",
            ],
            "status": "negative_distractor",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Hollow Purple", "Cursed Technique Lapse: Blue"],
            "audio_task_reference": {
                "has_audio": True,
                "audio_match_status": "unconfirmed",
            },
        },
        # Hard Negative 2: Vegeta - Galick Gun (Inter-franchise purple energy distractor)
        {
            "sample_id": "dbz-distractor-002",
            "source_title": "Dragon Ball Z",
            "source_type": "anime",
            "source_video_id": "dbz_s01_ep31_raw",
            "episode_id": "dbz_s01_ep31",
            "split_group_id": "dbz_s01_ep31",
            "franchise": "Dragon Ball",
            "season": 1,
            "episode": 31,
            "arc": "Saiyan Saga",
            "event_name": "Vegeta - Galick Gun - NOT Jujutsu Kaisen",
            "character_names": ["Vegeta"],
            "approx_start_seconds": 4.00,
            "approx_end_seconds": 16.00,
            "peak_frame_timestamp": 11.20,
            "duration_seconds": 18.0,
            "representative_frames": [
                {
                    "timecode": "00:06.00",
                    "timestamp_seconds": 6.00,
                    "frame_type": "setup",
                    "description": "Vegeta crossing wrists at right shoulder with intense magenta ki aura",
                    "image_path": str(
                        fixtures_dir / "dbz-distractor-002" / "frame_01.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:11.20",
                    "timestamp_seconds": 11.20,
                    "frame_type": "discharge",
                    "description": "Massive purple energy beam firing downwards",
                    "image_path": str(
                        fixtures_dir / "dbz-distractor-002" / "frame_02.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Saiyan battle armor",
                "Spiky black hair silhouette",
                "Wrists crossed at shoulder stance",
                "Purple ki beam without Six Eyes or Gojo anatomy",
            ],
            "status": "negative_distractor",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Hollow Purple", "Big Bang Attack"],
            "audio_task_reference": {
                "has_audio": True,
                "audio_match_status": "unconfirmed",
            },
        },
        # Unrelated Combat 3: Megumi vs Finger Bearer (Action scene without domain/purple)
        {
            "sample_id": "jkk-combat-004",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s01_ep04_raw",
            "episode_id": "jjk_s01_ep04",
            "split_group_id": "jjk_s01_ep04",
            "franchise": "Jujutsu Kaisen",
            "season": 1,
            "episode": 4,
            "arc": "Fearsome Womb Arc",
            "event_name": "Megumi Fushiguro - Evading Special Grade Finger Bearer",
            "character_names": ["Megumi Fushiguro", "Finger Bearer"],
            "approx_start_seconds": 3.00,
            "approx_end_seconds": 12.00,
            "peak_frame_timestamp": 7.50,
            "duration_seconds": 15.0,
            "representative_frames": [
                {
                    "timecode": "00:04.50",
                    "timestamp_seconds": 4.50,
                    "frame_type": "setup",
                    "description": "Megumi leaping backwards dodging cursed energy blast",
                    "image_path": str(fixtures_dir / "jkk-combat-004" / "frame_01.png"),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:07.50",
                    "timestamp_seconds": 7.50,
                    "frame_type": "impact",
                    "description": "Explosion shattering pipe infrastructure in detention center",
                    "image_path": str(fixtures_dir / "jkk-combat-004" / "frame_02.png"),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Industrial pipe juvenile detention center background",
                "Special grade curse silhouette",
                "Dodging maneuvers without named domain techniques",
            ],
            "status": "unrelated_combat",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Cursed Energy Blast"],
        },
        # Ambiguous 4: Distant Cursed Energy Flash (Ambiguous / occluded)
        {
            "sample_id": "jkk-ambiguous-005",
            "source_title": "Jujutsu Kaisen",
            "source_type": "anime",
            "source_video_id": "jjk_s01_ep12_raw",
            "episode_id": "jjk_s01_ep12",
            "split_group_id": "jjk_s01_ep12",
            "franchise": "Jujutsu Kaisen",
            "season": 1,
            "episode": 12,
            "arc": "Vs. Mahito Arc",
            "event_name": "Distant Cursed Energy Flare (Ambiguous Occlusion)",
            "character_names": ["Yuji Itadori"],
            "approx_start_seconds": 1.00,
            "approx_end_seconds": 6.00,
            "peak_frame_timestamp": 3.50,
            "duration_seconds": 8.0,
            "representative_frames": [
                {
                    "timecode": "00:02.00",
                    "timestamp_seconds": 2.00,
                    "frame_type": "setup",
                    "description": "Faint violet aura visible through dense hallway smoke",
                    "image_path": str(
                        fixtures_dir / "jkk-ambiguous-005" / "frame_01.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
                {
                    "timecode": "00:03.50",
                    "timestamp_seconds": 3.50,
                    "frame_type": "peak_occluded",
                    "description": "Burst of light obscured by concrete debris",
                    "image_path": str(
                        fixtures_dir / "jkk-ambiguous-005" / "frame_02.png"
                    ),
                    "width": 64,
                    "height": 64,
                },
            ],
            "visual_evidence": [
                "Heavy smoke obscuration",
                "Unidentified violet luminescence",
            ],
            "status": "ambiguous",
            "annotation_status": "fixture",
            "annotation_source": "test_fixture_seed",
            "rights_or_permission_status": "fair_use_research_fixture",
            "alternative_candidates": ["Divergent Fist", "Hollow Purple (Occluded)"],
        },
    ]

    # Generate physical fixture images if requested
    if generate_fixture_images:
        color_palette = [
            (140, 20, 255),  # Violet
            (255, 30, 30),  # Red
            (30, 100, 255),  # Blue
            (50, 50, 50),  # Dark grey
            (200, 150, 0),  # Gold
            (100, 255, 100),  # Green
            (180, 80, 220),  # Purple
        ]
        color_idx = 0
        for sample_dict in raw_samples:
            for frame_dict in sample_dict.get("representative_frames", []):
                p_str = frame_dict.get("image_path", "")
                if p_str:
                    col = color_palette[color_idx % len(color_palette)]
                    color_idx += 1
                    _, sha = create_fixture_image(p_str, width=64, height=64, rgb=col)
                    frame_dict["sha256_hash"] = sha
                    frame_dict["width"] = 64
                    frame_dict["height"] = 64

    return validate_dataset(raw_samples)


def export_dataset_to_jsonl(samples: list[AnimeEventSample], output_path: str) -> int:
    """Format and write samples to JSONL for Axolotl / TRL training."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            formatted = format_sample_to_instruction(sample)
            f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
            count += 1
    return count


def export_dataset_to_multimodal_jsonl(
    samples: list[AnimeEventSample], output_path: str
) -> int:
    """Format and write samples to JSONL in official OpenAI Messages multimodal format."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            formatted = format_sample_to_multimodal_messages(sample)
            f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
            count += 1
    return count


def generate_dataset_manifests(
    samples: list[AnimeEventSample],
    output_dir: str | Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> dict[str, Any]:
    """Generate reproducible multimodal training, validation, and evaluation manifests.

    1. Splits dataset using non-leaking episode/video grouping (`split_dataset_by_group`).
    2. Verifies zero cross-split leakage (`verify_split_leakage`).
    3. Exports:
       - train_manifest.jsonl
       - val_manifest.jsonl
       - test_manifest.jsonl
       - eval_manifest.json (ground truth annotations for benchmark evaluation)
       - manifest_metadata.json (reproducible SHA256 hashes and split statistics)

    Returns:
        dict containing manifest paths, counts, checksums, and verification summary.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Group-based split
    splits = split_dataset_by_group(
        samples, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio
    )

    # 2. Zero-leakage verification
    is_leak_free, leak_errors = verify_split_leakage(splits)
    if not is_leak_free:
        raise ValueError(f"Dataset split leakage detected: {'; '.join(leak_errors)}")

    # 3. Export multimodal JSONL manifests
    train_file = out_path / "train_manifest.jsonl"
    val_file = out_path / "val_manifest.jsonl"
    test_file = out_path / "test_manifest.jsonl"
    eval_file = out_path / "eval_manifest.json"
    meta_file = out_path / "manifest_metadata.json"

    export_dataset_to_multimodal_jsonl(splits["train"], str(train_file))
    export_dataset_to_multimodal_jsonl(splits["val"], str(val_file))
    export_dataset_to_multimodal_jsonl(splits["test"], str(test_file))

    # 4. Export evaluation ground truth
    eval_payload = [s.model_dump() for s in splits["test"]]
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_payload, f, indent=2, ensure_ascii=False)

    # 5. Compute SHA256 checksums of manifest files
    def get_file_sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    checksums = {
        "train_manifest_sha256": get_file_sha(train_file),
        "val_manifest_sha256": get_file_sha(val_file),
        "test_manifest_sha256": get_file_sha(test_file),
        "eval_manifest_sha256": get_file_sha(eval_file),
    }

    # 6. Metadata summary
    stats_train = compute_dataset_statistics(splits["train"])
    stats_val = compute_dataset_statistics(splits["val"])
    stats_test = compute_dataset_statistics(splits["test"])
    stats_overall = compute_dataset_statistics(samples)

    manifest_metadata: dict[str, Any] = {
        "manifest_version": "1.0.0",
        "output_directory": str(out_path),
        "zero_leakage_verified": True,
        "split_ratios": {
            "train": train_ratio,
            "val": val_ratio,
            "test": test_ratio,
        },
        "sample_counts": {
            "total": len(samples),
            "train": len(splits["train"]),
            "val": len(splits["val"]),
            "test": len(splits["test"]),
        },
        "files": {
            "train_manifest": str(train_file),
            "val_manifest": str(val_file),
            "test_manifest": str(test_file),
            "eval_manifest": str(eval_file),
        },
        "checksums": checksums,
        "overall_statistics": stats_overall,
        "split_statistics": {
            "train": stats_train,
            "val": stats_val,
            "test": stats_test,
        },
    }

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(manifest_metadata, f, indent=2, ensure_ascii=False)

    manifest_metadata["checksums"]["metadata_sha256"] = get_file_sha(meta_file)

    return manifest_metadata
