"""AI Director chat API routes for LolixCopilot."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.db.repository import BaseRepository, get_repository
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_director import ChatDirectorService, get_chat_director_service
from app.services.media_processing import (
    BaseMediaProcessingService,
    get_media_processing_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_with_director(
    project_id: str,
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    chat_service: ChatDirectorService = Depends(get_chat_director_service),
    media_processor: BaseMediaProcessingService = Depends(get_media_processing_service),
) -> ChatResponse:
    """Chat with the AI Director with real project, media, and analysis context."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        user_projects = repo.list_projects(user.user_id)
        if user_projects:
            project = user_projects[0]
        else:
            project = repo.create_project(name="Untitled Cut", user_id=user.user_id)

    project_data = {
        "id": project.id,
        "name": project.name,
        "aspect_ratio": project.aspect_ratio,
    }

    media_data: dict[str, object] | None = None
    latest_analysis: dict[str, object] | None = None
    audio_analysis: dict[str, object] | None = None

    if payload.media_id:
        media = repo.get_media(payload.media_id, user.user_id)
        if media and media.project_id == project_id:
            media_data = {
                "id": media.id,
                "original_filename": media.original_filename,
                "duration_seconds": media.duration_seconds,
                "status": media.status,
            }
            # Fetch latest analysis for this media
            analysis = repo.get_latest_analysis_for_media(media.id, user.user_id)
            if analysis:
                latest_analysis = {
                    "id": analysis.id,
                    "blueprint": analysis.blueprint,
                    "source_identification": analysis.source_identification,
                    "audio_intelligence": analysis.audio_intelligence,
                }
            # If audio intelligence is present or beats can be analyzed
            if latest_analysis and latest_analysis.get("audio_intelligence"):
                audio_analysis = latest_analysis["audio_intelligence"]  # type: ignore[assignment]
    else:
        # Check if project has any media
        media_items = repo.list_media(project_id, user.user_id)
        if media_items:
            first_media = media_items[0]
            media_data = {
                "id": first_media.id,
                "original_filename": first_media.original_filename,
                "duration_seconds": first_media.duration_seconds,
                "status": first_media.status,
            }
            analysis = repo.get_latest_analysis_for_media(first_media.id, user.user_id)
            if analysis:
                latest_analysis = {
                    "id": analysis.id,
                    "blueprint": analysis.blueprint,
                    "source_identification": analysis.source_identification,
                    "audio_intelligence": analysis.audio_intelligence,
                }

    return chat_service.process_chat_message(
        request=payload,
        project_data=project_data,
        media_data=media_data,
        latest_analysis=latest_analysis,
        audio_analysis=audio_analysis,
    )
