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


class TextOverlayItem(BaseModel):
    """Text title overlay burned onto exported video frames."""

    text: str = Field(..., description="Overlay text string")
    color: str = Field(default="#a855f7", description="Hex color e.g. #a855f7")
    start_seconds: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end_seconds: float = Field(..., gt=0.0, description="End timestamp in seconds")
    font_size: int = Field(default=60, description="Font size in points")
    position: str = Field(default="bottom_center", description="Position: bottom_center or center")


class ExportRequest(BaseModel):
    """Request payload to render an edited video cut."""

    media_id: str = Field(..., description="ID of the source media asset")
    segments: list[ExportSegment] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of ordered segments to trim and concatenate",
    )
    text_overlays: list[TextOverlayItem] = Field(
        default_factory=list, description="Optional text title overlays burned onto video"
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
    progress: int = Field(default=100, ge=0, le=100, description="Progress percentage 0-100")


class ExportStatusResponse(BaseModel):
    """Status polling response for asynchronous or long-running export render jobs."""

    export_id: str = Field(..., description="Unique UUID for this export job")
    project_id: str = Field(..., description="Project ID")
    media_id: str = Field(..., description="Source media ID")
    status: str = Field(default="processing", description="Job status: processing, completed, failed")
    progress: int = Field(default=0, ge=0, le=100, description="Current progress percentage (0-100)")
    message: str = Field(default="", description="Current status message or stage description")
    download_url: str = Field(default="", description="Download URL if completed")
    s3_key: str = Field(default="", description="Storage key if completed")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds if completed")
    file_size_bytes: int = Field(default=0, description="File size in bytes if completed")
    segment_count: int = Field(default=0, description="Number of segments")
    error_message: str | None = Field(default=None, description="Error detail if failed")
