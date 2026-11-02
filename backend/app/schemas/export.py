"""Pydantic schemas for video export and trimming operations."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator, model_validator


class ExportSegment(BaseModel):
    """An individual video segment to be trimmed and concatenated."""

    start_seconds: float = Field(..., ge=0.0, description="Segment start timestamp in seconds")
    end_seconds: float = Field(..., gt=0.0, description="Segment end timestamp in seconds")
    title: str | None = Field(default=None, description="Optional scene or moment title")
    pacing: str | None = Field(default=None, description="Pacing style: slow, medium, fast")
    speed_multiplier: float = Field(
        default=1.0,
        gt=0.25,
        le=4.0,
        description="Speed multiplier for velocity ramps (default 1.0)",
    )

    @field_validator("start_seconds", "end_seconds", mode="after")
    @classmethod
    def validate_finite(cls, val: float) -> float:
        if not math.isfinite(val):
            raise ValueError("Timestamps must be finite numbers")
        return round(val, 3)

    @model_validator(mode="after")
    def validate_bounds(self) -> ExportSegment:
        if self.end_seconds <= self.start_seconds:
            raise ValueError(
                f"end_seconds ({self.end_seconds}s) must be strictly greater than "
                f"start_seconds ({self.start_seconds}s)"
            )
        return self


class ExportRequest(BaseModel):
    """Request payload to render an edited video cut."""

    media_id: str = Field(..., description="ID of the source media asset")
    segments: list[ExportSegment] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of ordered segments to trim and concatenate",
    )
    resolution: str = Field(
        default="1080p",
        pattern=r"^(1080p|720p|source)$",
        description="Target output resolution: 1080p, 720p, or source",
    )
    include_audio: bool = Field(default=True, description="Whether to preserve and mix audio track")
    apply_fades: bool = Field(
        default=False, description="Apply subtle video fade transitions between cuts"
    )
    preset_name: str = Field(
        default="cinematic_cut", description="Editing preset: cinematic_cut, fast_paced, teaser"
    )


class ExportResponse(BaseModel):
    """Response payload with authenticated download URL for the exported MP4 cut."""

    export_id: str = Field(..., description="Unique UUID for this export job")
    project_id: str = Field(..., description="Project ID")
    media_id: str = Field(..., description="Source media ID")
    status: str = Field(..., description="Export status: completed, processing, failed")
    download_url: str = Field(..., description="Short-lived authenticated S3 download URL")
    s3_key: str = Field(..., description="S3 storage key under exports/ prefix")
    duration_seconds: float = Field(
        ..., description="Total duration of the rendered cut in seconds"
    )
    file_size_bytes: int = Field(..., description="Rendered MP4 file size in bytes")
    segment_count: int = Field(..., description="Number of scenes/segments included in the cut")
    message: str = Field(default="Cut rendered successfully", description="Status message")
