"""FastAPI routes for video understanding analysis and editing blueprint generation."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.db.repository import BaseRepository, get_repository
from app.schemas.analysis import AnalysisResponse, CreateAnalysisRequest
from app.services.ai_provider import (
    AIAuthenticationError,
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    AIValidationError,
    BaseAIProvider,
    CreativeBriefContext,
    get_ai_provider,
)
from app.services.s3 import BaseStorageService, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/media/{media_id}/analyze", tags=["analysis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_media(
    project_id: str,
    media_id: str,
    payload: CreateAnalysisRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
    ai_provider: BaseAIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    """Analyze uploaded video footage against the user's creative brief.

    Requires explicit user authorization before video footage is sent for analysis.
    Uses short-lived presigned private S3 URLs. Never logs raw URLs or secrets.
    """
    # 1. Require explicit user consent
    if not payload.confirmed_baseten_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "User authorization required: you must explicitly consent to Baseten AI inference "
                "before footage can be processed."
            ),
        )

    # 2. Verify project ownership
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    # 3. Verify media asset ownership and status
    media = repo.get_media(media_id, user.user_id)
    if not media or media.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found or access denied",
        )

    now = datetime.now(UTC)
    if now > media.expires_at:
        repo.update_media_status(media_id, user.user_id, status="expired")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Media asset has expired under the retention policy and cannot be analyzed.",
        )

    if media.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Media asset must be verified before analysis (current status: {media.status})",
        )

    # 4. Generate short-lived presigned GET URL for inference access
    presigned_video_url = storage.create_presigned_download_url(
        media.s3_object_key,
        expires_in=settings.SIGNED_URL_TTL_SECONDS,
        filename=media.original_filename,
    )

    # 5. Build CreativeBriefContext
    brief_ctx = CreativeBriefContext(
        title=payload.brief.title,
        description=payload.brief.description,
        style=payload.brief.style,
        pacing=payload.brief.pacing,
        aspect_ratio=payload.brief.aspect_ratio,
        target_duration=payload.brief.target_duration,
    )

    # 6. Execute model inference with clean domain error mapping
    try:
        blueprint = await ai_provider.generate_blueprint(
            video_url=presigned_video_url,
            brief=brief_ctx,
            duration_seconds=media.duration_seconds,
        )
    except AIAuthenticationError as exc:
        logger.error("AI provider authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "AI inference provider authentication failed. Please check server configuration."
            ),
        ) from exc
    except AIRateLimitError as exc:
        logger.warning("AI provider rate limit hit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI inference rate limit or quota exceeded. Please wait before retrying.",
        ) from exc
    except AITimeoutError as exc:
        logger.error("AI provider timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI inference timed out while analyzing footage.",
        ) from exc
    except AIValidationError as exc:
        logger.error("AI provider validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model generated an invalid editing blueprint schema.",
        ) from exc
    except AIProviderUnavailableError as exc:
        logger.error("AI provider unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI inference service is currently unavailable. Please retry in a few moments.",
        ) from exc
    except AIProviderError as exc:
        logger.error("AI provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model inference failed during footage analysis.",
        ) from exc

    provider_name = settings.AI_PROVIDER.lower()
    model_name = settings.BASETEN_MODEL if provider_name == "baseten" else "mock-director-1.0"

    return AnalysisResponse(
        id=str(uuid.uuid4()),
        project_id=project_id,
        media_id=media_id,
        provider=provider_name,
        model=model_name,
        blueprint=blueprint,
        created_at=datetime.now(UTC),
    )
