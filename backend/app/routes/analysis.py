"""FastAPI routes for video understanding analysis, media intelligence, and blueprint generation."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.db.repository import BaseRepository, get_repository
from app.schemas.analysis import (
    AnalysisResponse,
    AudioIntelligence,
    CreateAnalysisRequest,
    MediaClassificationEnum,
    MusicMatchStatusEnum,
    SourceIdentification,
    UsageMetadata,
    UserFeedback,
    UserFeedbackRequest,
)
from app.schemas.blueprint import EditingBlueprint
from app.services.ai_provider import (
    AIAuthenticationError,
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    AIValidationError,
    BaseAIProvider,
    CreativeBriefContext,
    create_ai_provider,
    get_ai_provider,
)
from app.services.media_processing import (
    BaseMediaProcessingService,
    get_media_processing_service,
)
from app.services.s3 import BaseStorageService, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/media/{media_id}/analyze", tags=["analysis"])

ALLOWED_AI_PROVIDERS = frozenset({"baseten", "meta", "mock"})


@router.post("", response_model=AnalysisResponse)
async def analyze_media(
    project_id: str,
    media_id: str,
    payload: CreateAnalysisRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
    default_ai_provider: BaseAIProvider = Depends(get_ai_provider),
    media_processing: BaseMediaProcessingService = Depends(get_media_processing_service),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    """Analyze uploaded video footage against the user's creative brief.

    Requires explicit user authorization before video footage is sent for analysis.
    Supports allowlisted provider selection ('baseten', 'meta', 'mock').
    Uses short-lived presigned private S3 URLs. Never logs raw URLs or secrets.
    Persists structured media intelligence, blueprint, and usage telemetry.
    """
    # 1. Require explicit user consent
    has_consent = bool(payload.confirmed_consent or payload.confirmed_baseten_consent)
    if not has_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "User authorization required: you must explicitly consent to AI inference "
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

    # 4. Resolve active provider (allowlisted explicit selection or default setting)
    active_provider = default_ai_provider
    provider_name = settings.AI_PROVIDER.lower()

    if payload.provider:
        clean_provider = payload.provider.strip().lower()
        if clean_provider not in ALLOWED_AI_PROVIDERS:
            allowed = ", ".join(sorted(ALLOWED_AI_PROVIDERS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider '{payload.provider}'. Must be one of: {allowed}",
            )
        provider_name = clean_provider
        try:
            active_provider = create_ai_provider(clean_provider, settings)
        except AIAuthenticationError as exc:
            logger.error("Provider '%s' configuration error: %s", clean_provider, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    # Determine model identifier for persistence and response
    if provider_name == "baseten":
        model_name = settings.BASETEN_MODEL
    elif provider_name == "meta":
        model_name = settings.META_MODEL
    else:
        model_name = "mock-director-1.0"

    # 5. Cost Protection: Return cached analysis if identical brief already completed
    existing_analysis = repo.get_latest_analysis_for_media(media_id, user.user_id)
    if (
        existing_analysis
        and existing_analysis.status == "completed"
        and existing_analysis.blueprint
        and existing_analysis.blueprint.get("title") == payload.brief.title
        and existing_analysis.blueprint.get("creative_intent") == payload.brief.description
        and existing_analysis.provider == provider_name
    ):
        logger.info(
            "Returning cached analysis %s for media %s to prevent duplicate spend",
            existing_analysis.id,
            media_id,
        )
        return AnalysisResponse(
            id=existing_analysis.id,
            project_id=project_id,
            media_id=media_id,
            provider=existing_analysis.provider or provider_name,
            model=existing_analysis.model or model_name,
            blueprint=EditingBlueprint.model_validate(existing_analysis.blueprint),
            source_identification=(
                SourceIdentification.model_validate(existing_analysis.source_identification)
                if existing_analysis.source_identification
                else None
            ),
            audio_intelligence=(
                AudioIntelligence.model_validate(existing_analysis.audio_intelligence)
                if existing_analysis.audio_intelligence
                else None
            ),
            usage_metadata=(
                UsageMetadata.model_validate(existing_analysis.usage_metadata)
                if existing_analysis.usage_metadata
                else None
            ),
            user_feedback=(
                UserFeedback.model_validate(existing_analysis.user_feedback)
                if existing_analysis.user_feedback
                else None
            ),
            created_at=existing_analysis.created_at,
        )

    # 6. Generate short-lived presigned GET URL for inference access
    presigned_video_url = storage.create_presigned_download_url(
        media.s3_object_key,
        expires_in=settings.SIGNED_URL_TTL_SECONDS,
        filename=media.original_filename,
    )

    # 7. Build CreativeBriefContext
    brief_ctx = CreativeBriefContext(
        title=payload.brief.title,
        description=payload.brief.description,
        style=payload.brief.style,
        pacing=payload.brief.pacing,
        aspect_ratio=payload.brief.aspect_ratio,
        target_duration=payload.brief.target_duration,
    )

    # 8. Execute model inference with clean domain error mapping
    try:
        try:
            res = await active_provider.analyze_video_intelligence(
                video_url=presigned_video_url,
                brief=brief_ctx,
                duration_seconds=media.duration_seconds,
            )
            if isinstance(res, tuple) and len(res) == 4 and isinstance(res[0], EditingBlueprint):
                blueprint, source_id, audio_intel, usage_meta = res
            else:
                blueprint = await active_provider.generate_blueprint(
                    video_url=presigned_video_url,
                    brief=brief_ctx,
                    duration_seconds=media.duration_seconds,
                )
                source_id = SourceIdentification(media_type=MediaClassificationEnum.UNKNOWN)
                audio_intel = AudioIntelligence(match_status=MusicMatchStatusEnum.UNKNOWN)
                usage_meta = UsageMetadata()
        except (ValueError, TypeError):
            blueprint = await active_provider.generate_blueprint(
                video_url=presigned_video_url,
                brief=brief_ctx,
                duration_seconds=media.duration_seconds,
            )
            source_id = SourceIdentification(media_type=MediaClassificationEnum.UNKNOWN)
            audio_intel = AudioIntelligence(match_status=MusicMatchStatusEnum.UNKNOWN)
            usage_meta = UsageMetadata()
    except AIAuthenticationError as exc:
        logger.error("AI provider authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"AI inference provider '{provider_name}' authentication failed. "
                "Please check server configuration."
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
            detail="AI model generated an invalid editing blueprint schema or intelligence format.",
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

    # 9. Persist analysis record in database
    analysis_id = str(uuid.uuid4())
    try:
        saved_record = repo.create_analysis(
            analysis_id=analysis_id,
            project_id=project_id,
            media_id=media_id,
            user_id=user.user_id,
            status="completed",
            blueprint=blueprint.model_dump(),
            provider=provider_name,
            model=model_name,
            source_identification=source_id.model_dump(),
            audio_intelligence=audio_intel.model_dump(),
            usage_metadata=usage_meta.model_dump(),
            user_feedback=None,
        )
        created_time = saved_record.created_at
    except Exception as exc:
        logger.warning("Failed to persist analysis record to repository: %s", exc)
        created_time = datetime.now(UTC)

    return AnalysisResponse(
        id=analysis_id,
        project_id=project_id,
        media_id=media_id,
        provider=provider_name,
        model=model_name,
        blueprint=blueprint,
        source_identification=source_id,
        audio_intelligence=audio_intel,
        usage_metadata=usage_meta,
        user_feedback=None,
        created_at=created_time,
    )


@router.get("/latest", response_model=AnalysisResponse)
async def get_latest_media_analysis(
    project_id: str,
    media_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> AnalysisResponse:
    """Retrieve the most recent analysis record for a media asset."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    analysis = repo.get_latest_analysis_for_media(media_id, user.user_id)
    if not analysis or not analysis.blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed analysis found for this media asset",
        )

    return AnalysisResponse(
        id=analysis.id,
        project_id=project_id,
        media_id=media_id,
        provider=analysis.provider or "mock",
        model=analysis.model or "mock-director-1.0",
        blueprint=EditingBlueprint.model_validate(analysis.blueprint),
        source_identification=(
            SourceIdentification.model_validate(analysis.source_identification)
            if analysis.source_identification
            else None
        ),
        audio_intelligence=(
            AudioIntelligence.model_validate(analysis.audio_intelligence)
            if analysis.audio_intelligence
            else None
        ),
        usage_metadata=(
            UsageMetadata.model_validate(analysis.usage_metadata)
            if analysis.usage_metadata
            else None
        ),
        user_feedback=(
            UserFeedback.model_validate(analysis.user_feedback) if analysis.user_feedback else None
        ),
        created_at=analysis.created_at,
    )


@router.post("/feedback", response_model=AnalysisResponse)
async def submit_analysis_feedback(
    project_id: str,
    media_id: str,
    payload: UserFeedbackRequest,
    analysis_id: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> AnalysisResponse:
    """Submit user confirmation or correction for source and soundtrack predictions."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    # If analysis_id not provided, resolve latest
    target_analysis = None
    if analysis_id:
        target_analysis = repo.get_analysis(analysis_id, user.user_id)
    if not target_analysis:
        target_analysis = repo.get_latest_analysis_for_media(media_id, user.user_id)

    if not target_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found to attach feedback",
        )

    feedback_data = {
        "confirmed_by_user": payload.confirmed_by_user,
        "corrected_source_title": payload.corrected_source_title,
        "corrected_song_title": payload.corrected_song_title,
        "notes": payload.notes,
        "updated_at": datetime.now(UTC).isoformat(),
    }

    updated = repo.update_analysis_feedback(target_analysis.id, user.user_id, feedback_data)
    if not updated or not updated.blueprint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update analysis feedback",
        )

    return AnalysisResponse(
        id=updated.id,
        project_id=project_id,
        media_id=media_id,
        provider=updated.provider or "mock",
        model=updated.model or "mock-director-1.0",
        blueprint=EditingBlueprint.model_validate(updated.blueprint),
        source_identification=(
            SourceIdentification.model_validate(updated.source_identification)
            if updated.source_identification
            else None
        ),
        audio_intelligence=(
            AudioIntelligence.model_validate(updated.audio_intelligence)
            if updated.audio_intelligence
            else None
        ),
        usage_metadata=(
            UsageMetadata.model_validate(updated.usage_metadata) if updated.usage_metadata else None
        ),
        user_feedback=(
            UserFeedback.model_validate(updated.user_feedback) if updated.user_feedback else None
        ),
        created_at=updated.created_at,
    )
