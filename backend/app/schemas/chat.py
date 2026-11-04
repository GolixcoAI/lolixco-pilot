"""Pydantic schemas for AI Director conversational chat and moment retrieval."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ChatEvidenceCard(BaseModel):
    """Evidence card with timestamp and description for a retrieved video moment."""

    timestamp_seconds: float = Field(..., description="Timestamp in seconds")
    timecode: str = Field(..., description="Formatted timecode e.g. 00:35:00")
    title: str = Field(..., description="Moment headline")
    description: str = Field(..., description="Evidence / visual explanation")
    confidence: str = Field(default="high", description="high, medium, low, or speculative")
    phase: str | None = Field(default=None, description="Narrative phase or tag")
    thumbnail_url: str | None = Field(default=None, description="Optional frame thumbnail URL")


class SceneBreakdownItem(BaseModel):
    """A detected scene in the video breakdown."""

    id: str = Field(..., description="Unique scene ID")
    start_seconds: float = Field(..., description="Start time in seconds")
    end_seconds: float = Field(..., description="End time in seconds")
    timecode_range: str = Field(..., description="Formatted range e.g. 00:00 - 00:04")
    title: str = Field(..., description="Scene title / phase")
    description: str = Field(..., description="Scene visual action")
    thumbnail_url: str = Field(..., description="Relative or absolute frame thumbnail path")
    editing_direction: str | None = Field(default=None, description="Recommended editing action")


class EditRecommendationItem(BaseModel):
    """An actionable edit suggestion from the AI Director."""

    id: str = Field(..., description="Unique recommendation ID")
    text: str = Field(..., description="Recommendation label")
    checked: bool = Field(default=True, description="Whether selected by default")
    action_type: str = Field(default="cut", description="cut, speed_ramp, effect, audio, transition")
    timestamp_seconds: float | None = Field(default=None, description="Associated timestamp")


class InferenceTraceItem(BaseModel):
    """Execution trace element for an AI model or cloud processing call."""

    provider: str = Field(..., description="modal, meta, baseten, or aws_lambda")
    model: str = Field(..., description="Model identifier or engine name")
    task: str = Field(..., description="Task type: vision, reasoning, edit_plan, render")
    status: str = Field(default="success", description="success, fallback, or error")
    latency_ms: float = Field(..., description="Measured latency in milliseconds")
    prompt_tokens: int | None = Field(default=None, description="Input tokens if applicable")
    completion_tokens: int | None = Field(default=None, description="Output tokens if applicable")
    total_tokens: int | None = Field(default=None, description="Total tokens")
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD")


class ChatMessage(BaseModel):
    """An individual message in the AI Director conversation."""

    id: str = Field(..., description="Unique message ID")
    role: str = Field(
        ..., pattern=r"^(user|assistant|system)$", description="user, assistant, or system"
    )
    content: str = Field(..., description="Message text content")
    timestamp: str = Field(..., description="ISO formatted timestamp")
    timecode_jump: float | None = Field(
        default=None, description="Optional timestamp in seconds for player seeking"
    )
    suggested_action: str | None = Field(
        default=None, description="Suggested next action or command"
    )
    evidence_cards: list[ChatEvidenceCard] = Field(
        default_factory=list, description="Associated moment evidence cards"
    )
    scene_breakdown: list[SceneBreakdownItem] = Field(
        default_factory=list, description="Scene breakdown items"
    )
    edit_recommendations: list[EditRecommendationItem] = Field(
        default_factory=list, description="Actionable edit recommendations"
    )
    inference_trace: list[InferenceTraceItem] = Field(
        default_factory=list, description="Provider execution trace"
    )


class ChatRequest(BaseModel):
    """User prompt to the AI Director with project context."""

    message: str = Field(
        ..., min_length=1, max_length=2000, description="User prompt or instruction"
    )
    media_id: str | None = Field(default=None, description="Optional active media asset ID")
    provider: str = Field(
        default="auto", description="Provider choice: auto, modal, meta, or baseten"
    )
    current_time: float | None = Field(
        default=None, description="Current playhead position in seconds"
    )
    history: list[ChatMessage] = Field(
        default_factory=list, description="Prior conversation history"
    )


class ChatResponse(BaseModel):
    """AI Director response with evidence, trace, and optional blueprint adjustments."""

    message: ChatMessage = Field(..., description="Generated assistant message")
    provider_used: str = Field(default="auto", description="Actual provider used")
    model_used: str = Field(default="muse-spark-1.3", description="Actual model used")
    inference_trace: list[InferenceTraceItem] = Field(
        default_factory=list, description="Detailed provider execution chain"
    )
    scene_breakdown: list[SceneBreakdownItem] = Field(
        default_factory=list, description="Extracted scene breakdown"
    )
    edit_recommendations: list[EditRecommendationItem] = Field(
        default_factory=list, description="Recommended timeline edits"
    )
    updated_blueprint: dict[str, Any] | None = Field(
        default=None, description="Optional updated editing blueprint"
    )
