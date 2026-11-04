"""Pydantic schemas for audio analysis, beat detection, and energy timeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnergySample(BaseModel):
    """Normalized audio energy at a specific timestamp."""

    timestamp: float = Field(..., ge=0.0, description="Timestamp in seconds")
    normalized_energy: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized RMS energy [0.0, 1.0]"
    )


class AudioAnalysisResponse(BaseModel):
    """Audio intelligence and beat analysis data."""

    media_id: str = Field(..., description="Media asset ID")
    duration_seconds: float = Field(..., ge=0.0, description="Audio track duration in seconds")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    peak_dbfs: float = Field(..., description="Peak volume in dBFS")
    mean_dbfs: float = Field(..., description="Mean/RMS volume in dBFS")
    estimated_bpm: float | None = Field(default=None, description="Estimated music tempo in BPM")
    beat_timestamps: list[float] = Field(
        default_factory=list,
        description="List of detected musical onsets / beat timestamps in seconds",
    )
    energy_timeline: list[EnergySample] = Field(
        default_factory=list, description="Downsampled timeline of normalized RMS energy"
    )
    has_speech: bool = Field(default=False, description="Whether speech was detected")
