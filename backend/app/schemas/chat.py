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


class ChatRequest(BaseModel):
    """User prompt to the AI Director with project context."""

    message: str = Field(
        ..., min_length=1, max_length=2000, description="User prompt or instruction"
    )
    media_id: str | None = Field(default=None, description="Optional active media asset ID")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Prior conversation history"
    )


class ChatResponse(BaseModel):
    """AI Director response with evidence and optional blueprint adjustments."""

    message: ChatMessage = Field(..., description="Generated assistant message")
    updated_blueprint: dict[str, Any] | None = Field(
        default=None, description="Optional updated editing blueprint"
    )
