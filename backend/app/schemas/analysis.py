"""Schemas for video analysis requests, media intelligence, and blueprint responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.schemas.blueprint import EditingBlueprint


class MediaClassificationEnum(StrEnum):
    """Broad category of the recognized video clip."""

    ANIME = "anime"
    MOVIE = "movie"
    TV_SERIES = "tv_series"
    GAME = "game"
    MUSIC_VIDEO = "music_video"
    OTHER = "other"
    UNKNOWN = "unknown"


class ConfidenceLevelEnum(StrEnum):
    """Categorical estimation of model confidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRATED = "unrated"


class MusicMatchStatusEnum(StrEnum):
    """Status of identified music or soundtrack."""

    CONFIRMED_FINGERPRINT = "confirmed_fingerprint"
    STRONG_INFERENCE = "strong_inference"
    POSSIBLE_MATCH = "possible_match"
    UNKNOWN = "unknown"


class SourceIdentification(BaseModel):
    """Structured identification of the footage source, characters, and franchise."""

    media_type: MediaClassificationEnum = Field(
        default=MediaClassificationEnum.UNKNOWN,
        description="Classified medium of footage (anime, movie, tv_series, game, etc.)",
    )
    likely_title: str | None = Field(
        default=None,
        description="Identified title of the anime, movie, or series (null if unknown)",
    )
    franchise: str | None = Field(
        default=None,
        description="Broader franchise or cinematic universe name",
    )
    season_episode: str | None = Field(
        default=None,
        description="Identifiable season and/or episode (null if unconfirmed)",
    )
    characters: list[str] = Field(
        default_factory=list,
        description="Likely recognizable characters present in footage",
    )
    recognizable_scenes: list[str] = Field(
        default_factory=list,
        description="Notable scenes or arc references identified visually",
    )
    visual_evidence: str = Field(
        default="",
        description="Summary of visual hallmarks used to classify the clip",
    )
    confidence: ConfidenceLevelEnum = Field(
        default=ConfidenceLevelEnum.UNRATED,
        description="Categorical model confidence label",
    )
    confidence_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated non-calibrated confidence score 0.0 to 1.0",
    )
    alternative_candidates: list[str] = Field(
        default_factory=list,
        description="Alternative plausible source titles if uncertain",
    )


class AudioIntelligence(BaseModel):
    """Structured intelligence regarding the soundtrack, mood, tempo, and audio."""

    song_title: str | None = Field(
        default=None,
        description="Identified soundtrack or song title (null if unknown)",
    )
    artist: str | None = Field(
        default=None,
        description="Identified musical artist or producer",
    )
    genre: str | None = Field(
        default=None,
        description="Music genre (e.g. Phonk, Orchestral, Rock, Lo-Fi, Hip Hop)",
    )
    lyrics_or_vocal_phrases: list[str] = Field(
        default_factory=list,
        description="Recognized lyrics or vocal samples",
    )
    mood: str | None = Field(
        default=None,
        description="Detected mood (e.g. Aggressive, Melancholic, Euphoric, Tense)",
    )
    tempo: str | None = Field(
        default=None,
        description="Estimated tempo (e.g. '130 BPM', 'Fast', 'Half-time')",
    )
    beat_changes: list[str] = Field(
        default_factory=list,
        description="Notable beat drops, transitions, or rhythm shifts",
    )
    match_status: MusicMatchStatusEnum = Field(
        default=MusicMatchStatusEnum.UNKNOWN,
        description="Confidence distinction (fingerprint, model inference, possible, or unknown)",
    )
    confidence_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated soundtrack confidence score",
    )


class UsageMetadata(BaseModel):
    """Model execution usage, latency, and telemetry."""

    prompt_tokens: int | None = Field(default=None, description="Reported input tokens")
    completion_tokens: int | None = Field(default=None, description="Reported output tokens")
    total_tokens: int | None = Field(default=None, description="Reported total tokens")
    latency_ms: float | None = Field(default=None, description="Measured wall-clock latency in ms")
    request_id: str | None = Field(default=None, description="Provider request identifier")


class UserFeedback(BaseModel):
    """User corrections and validation for model predictions."""

    confirmed_by_user: bool = Field(default=False, description="Whether user validated predictions")
    corrected_source_title: str | None = Field(
        default=None, description="User correction for title"
    )
    corrected_song_title: str | None = Field(
        default=None, description="User correction for soundtrack"
    )
    notes: str | None = Field(default=None, description="Optional user commentary")
    updated_at: datetime | None = Field(
        default=None, description="Timestamp of feedback submission"
    )


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


# Alias CreativeBriefContext to CreativeBriefInput for schema compatibility
CreativeBriefContext = CreativeBriefInput


class CreateAnalysisRequest(BaseModel):
    """Request payload to initiate video understanding analysis."""

    brief: CreativeBriefInput = Field(
        default_factory=CreativeBriefInput,
        description="User creative brief inputs",
    )
    provider: str | None = Field(
        default=None,
        description="Explicit provider selection: 'baseten', 'meta', or 'mock'",
    )
    confirmed_baseten_consent: bool | None = Field(
        default=None,
        description="Explicit user authorization for Baseten model inference",
    )
    confirmed_consent: bool | None = Field(
        default=None,
        description="General explicit user authorization for AI model inference",
    )

    @model_validator(mode="after")
    def validate_consent(self) -> CreateAnalysisRequest:
        # Support either confirmed_consent or confirmed_baseten_consent
        if self.confirmed_consent is None and self.confirmed_baseten_consent is not None:
            self.confirmed_consent = self.confirmed_baseten_consent
        elif self.confirmed_baseten_consent is None and self.confirmed_consent is not None:
            self.confirmed_baseten_consent = self.confirmed_consent
        return self


class UserFeedbackRequest(BaseModel):
    """Payload to record user confirmation or correction of identified metadata."""

    confirmed_by_user: bool = Field(default=True, description="True if verified by user")
    corrected_source_title: str | None = Field(default=None, description="Corrected source title")
    corrected_song_title: str | None = Field(default=None, description="Corrected soundtrack title")
    notes: str | None = Field(default=None, description="Optional user notes")


class AnalysisResponse(BaseModel):
    """Result of the video understanding analysis."""

    id: str = Field(..., description="Unique analysis record identifier")
    project_id: str = Field(..., description="Associated project ID")
    media_id: str = Field(..., description="Associated media asset ID")
    provider: str = Field(..., description="AI provider used (e.g. baseten, meta, mock)")
    model: str = Field(..., description="Model identifier used for inference")
    blueprint: EditingBlueprint = Field(..., description="The structured editing blueprint")
    source_identification: SourceIdentification | None = Field(
        default=None,
        description="Identified anime/movie/series, characters, and scenes",
    )
    audio_intelligence: AudioIntelligence | None = Field(
        default=None,
        description="Soundtrack identification, mood, tempo, and transitions",
    )
    usage_metadata: UsageMetadata | None = Field(
        default=None,
        description="Reported token counts, latency, and provider request ID",
    )
    user_feedback: UserFeedback | None = Field(
        default=None,
        description="User-submitted corrections or verification",
    )
    created_at: datetime = Field(..., description="Timestamp of analysis generation")
