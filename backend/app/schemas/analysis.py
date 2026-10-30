"""Schemas for video analysis requests and blueprint responses."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.blueprint import EditingBlueprint


class CreativeBriefInput(BaseModel):
    """Creative brief options submitted for AI analysis."""

    title: str = Field(
        default="Untitled Cut",
        min_length=1,
        max_length=120,
        description="Working hook title or theme of the edit",
    )
    description: str = Field(
        default="Punchy hook for social media",
        min_length=1,
        max_length=1000,
        description="Creative intent or target narrative",
    )
    style: str = Field(
        default="Punchy & Fast",
        max_length=60,
        description="Editing style description (e.g. Punchy & Fast, Cinematic Flow)",
    )
    pacing: str = Field(
        default="fast",
        max_length=30,
        description="Target pacing speed: slow, medium, fast",
    )
    aspect_ratio: str = Field(
        default="9:16",
        max_length=10,
        description="Target delivery aspect ratio (e.g. 9:16, 16:9, 1:1)",
    )
    target_duration: float = Field(
        default=30.0,
        gt=0.0,
        le=300.0,
        description="Target cut duration in seconds",
    )


class CreateAnalysisRequest(BaseModel):
    """Request payload to initiate video understanding analysis."""

    brief: CreativeBriefInput = Field(
        default_factory=CreativeBriefInput,
        description="User creative brief inputs",
    )
    confirmed_baseten_consent: bool = Field(
        ...,
        description="Explicit user authorization to process this video via Baseten inference",
    )


class AnalysisResponse(BaseModel):
    """Result of the video understanding analysis."""

    id: str = Field(..., description="Unique analysis record identifier")
    project_id: str = Field(..., description="Associated project ID")
    media_id: str = Field(..., description="Associated media asset ID")
    provider: str = Field(..., description="AI provider used (e.g. baseten, mock)")
    model: str = Field(..., description="Model identifier used for inference")
    blueprint: EditingBlueprint = Field(..., description="The structured editing blueprint")
    created_at: datetime = Field(..., description="Timestamp of analysis generation")
