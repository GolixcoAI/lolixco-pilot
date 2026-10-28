import math
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class PacingEnum(StrEnum):
    """Pacing suggestion for a scene."""

    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class SceneRecommendation(BaseModel):
    """A timestamped moment recommendation within the video."""

    id: str = Field(..., description="Unique scene identifier, e.g. scene-01")
    start_seconds: float = Field(..., ge=0.0, description="Approximate start timecode in seconds")
    end_seconds: float = Field(..., gt=0.0, description="Approximate end timecode in seconds")
    moment: str = Field(..., min_length=2, description="What visibly happens in the footage")
    why_it_works: str = Field(
        ..., min_length=2, description="Why this moment supports the creative brief"
    )
    editing_direction: str = Field(
        ..., min_length=2, description="Suggested cut, pacing, zoom, or transition emphasis"
    )
    pacing: PacingEnum = Field(default=PacingEnum.MEDIUM, description="Suggested pacing")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence score if provided by model; null if uncalibrated",
    )
    thumbnail_key: str | None = Field(
        default=None,
        description="Private object storage key for generated preview frame",
    )

    @model_validator(mode="after")
    def validate_scene_timestamps(self) -> "SceneRecommendation":
        if not math.isfinite(self.start_seconds) or not math.isfinite(self.end_seconds):
            raise ValueError("Timestamps must be finite numbers")
        if self.start_seconds >= self.end_seconds:
            msg = (
                f"start_seconds ({self.start_seconds}s) must be strictly less "
                f"than end_seconds ({self.end_seconds}s)"
            )
            raise ValueError(msg)
        return self


class EditingBlueprint(BaseModel):
    """The structured editing blueprint data contract.

    Produced from video understanding and creative brief alignment.
    """

    title: str = Field(..., min_length=1, description="Working title or hook name for the edit")
    creative_intent: str = Field(
        ..., min_length=1, description="Normalized intent derived from user brief"
    )
    summary: str = Field(..., min_length=1, description="Overview of the suggested cut")
    target_duration_seconds: float = Field(
        ..., gt=0.0, le=300.0, description="Target duration of the cut in seconds"
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="Recommended delivery aspect ratio (e.g. 9:16, 16:9)",
    )
    hook: str = Field(
        ..., min_length=1, description="Opening recommendation to capture viewer attention"
    )
    scenes: list[SceneRecommendation] = Field(
        default_factory=list,
        description="Ordered list of timestamped moment recommendations",
    )
    sequence_rationale: str = Field(
        ..., min_length=1, description="Explanation of how the sequence builds narrative or energy"
    )
    ending_suggestion: str = Field(
        ..., min_length=1, description="Recommended closing transition or call to action"
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Caveats or notes regarding lighting, audio, or boundary precision",
    )

    @model_validator(mode="after")
    def validate_duration_and_scenes(self) -> "EditingBlueprint":
        if not math.isfinite(self.target_duration_seconds):
            raise ValueError("target_duration_seconds must be a finite number")
        return self
