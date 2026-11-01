"""FastAPI routes for media asset upload, verification, and authorized playback."""

import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.db.repository import BaseRepository, get_repository
from app.schemas.media import (
    ConfirmUploadRequest,
    MediaResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    PreviewUrlResponse,
)
from app.services.s3 import ALLOWED_VIDEO_EXTENSIONS, BaseStorageService, get_storage

router = APIRouter(prefix="/api/projects/{project_id}/media", tags=["media"])


@router.get("", response_model=list[MediaResponse])
async def list_project_media(
    project_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
) -> list[MediaResponse]:
    """List all media assets belonging to a project, verified against ownership."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    now = datetime.now(UTC)
    media_items = repo.list_media(project_id, user.user_id)
    responses: list[MediaResponse] = []

    for item in media_items:
        # Check if expired
        is_expired = now > item.expires_at
        status_val = "expired" if is_expired else item.status
        preview_url: str | None = None

        if status_val == "verified" and not is_expired:
            preview_url = storage.create_presigned_download_url(
                item.s3_object_key,
                filename=item.original_filename,
            )

        responses.append(
            MediaResponse(
                id=item.id,
                project_id=item.project_id,
                user_id=item.user_id,
                original_filename=item.original_filename,
                content_type=item.content_type,
                declared_size_bytes=item.declared_size_bytes,
                verified_size_bytes=item.verified_size_bytes,
                duration_seconds=item.duration_seconds,
                status=status_val,
                expires_at=item.expires_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                preview_url=preview_url,
            )
        )
    return responses


@router.post(
    "/presign-upload",
    response_model=PresignUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_presigned_upload(
    project_id: str,
    payload: PresignUploadRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> PresignUploadResponse:
    """Request a short-lived presigned PUT URL for direct client-to-S3 video upload."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    if payload.size_bytes > settings.MAX_UPLOAD_BYTES:
        max_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload limit of {max_mb} MB",
        )

    ext = os.path.splitext(payload.filename)[1]
    clean_ext = ext.strip().lstrip(".").lower()
    if clean_ext not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media file extension '{ext}'. Allowed extensions: {allowed}",
        )

    media_id = str(uuid.uuid4())
    s3_key = storage.generate_object_key(
        user_id=user.user_id,
        project_id=project_id,
        media_id=media_id,
        extension=ext,
    )
    media_record = repo.create_media(
        project_id=project_id,
        user_id=user.user_id,
        original_filename=payload.filename,
        s3_object_key=s3_key,
        content_type=payload.content_type,
        declared_size_bytes=payload.size_bytes,
        retention_days=settings.VIDEO_RETENTION_DAYS,
        media_id=media_id,
    )

    upload_info = storage.create_presigned_upload_url(
        s3_key=s3_key,
        content_type=payload.content_type,
        expires_in=settings.SIGNED_URL_TTL_SECONDS,
    )

    return PresignUploadResponse(
        media_id=media_record.id,
        project_id=project_id,
        s3_key=s3_key,
        upload_url=upload_info.upload_url,
        expires_in=upload_info.expires_in,
    )


@router.post("/{media_id}/confirm", response_model=MediaResponse)
async def confirm_upload(
    project_id: str,
    media_id: str,
    payload: ConfirmUploadRequest | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> MediaResponse:
    """Verify upload completion directly against storage metadata.

    Performs server-side existence, size, and content-type verification.
    Guarantees idempotency on repeated confirmations.
    """
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    media = repo.get_media(media_id, user.user_id)
    if not media or media.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found or access denied",
        )

    # Verify S3 object exists and retrieve verified size and content type
    obj_meta = storage.verify_object(media.s3_object_key)
    if not obj_meta.exists:
        repo.update_media_status(media_id, user.user_id, status="failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded object was not found in storage. Upload may have timed out or failed.",
        )

    # 1. Enforce verified byte size limit
    if obj_meta.size_bytes > settings.MAX_UPLOAD_BYTES:
        repo.update_media_status(media_id, user.user_id, status="failed")
        max_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Verified object size ({obj_meta.size_bytes} bytes) exceeds {max_mb} MB limit",
        )

    if obj_meta.size_bytes == 0:
        repo.update_media_status(media_id, user.user_id, status="failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded object is empty (0 bytes).",
        )

    # 2. Enforce content-type validity if present
    if obj_meta.content_type:
        raw_ct = obj_meta.content_type.lower().split(";")[0].strip()
        allowed_mime_prefixes = ("video/", "application/octet-stream")
        if not raw_ct.startswith(allowed_mime_prefixes):
            repo.update_media_status(media_id, user.user_id, status="failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded object has invalid MIME type '{raw_ct}'. Must be video.",
            )

    # 3. Enforce maximum video length if duration is supplied
    duration = payload.duration_seconds if payload else None
    if duration is not None and duration > settings.MAX_VIDEO_SECONDS:
        repo.update_media_status(media_id, user.user_id, status="failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Video duration ({duration:.1f}s) exceeds maximum allowed length of "
                f"{settings.MAX_VIDEO_SECONDS}s"
            ),
        )

    # 4. Idempotent update
    updated = repo.update_media_status(
        media_id=media_id,
        user_id=user.user_id,
        status="verified",
        verified_size_bytes=obj_meta.size_bytes,
        duration_seconds=duration if duration is not None else media.duration_seconds,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media record",
        )

    preview_url = storage.create_presigned_download_url(
        updated.s3_object_key,
        filename=updated.original_filename,
    )

    return MediaResponse(
        id=updated.id,
        project_id=updated.project_id,
        user_id=updated.user_id,
        original_filename=updated.original_filename,
        content_type=updated.content_type,
        declared_size_bytes=updated.declared_size_bytes,
        verified_size_bytes=updated.verified_size_bytes,
        duration_seconds=updated.duration_seconds,
        status=updated.status,
        expires_at=updated.expires_at,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        preview_url=preview_url,
    )


@router.get("/{media_id}/preview-url", response_model=PreviewUrlResponse)
async def get_preview_url(
    project_id: str,
    media_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> PreviewUrlResponse:
    """Return an authorized, short-lived presigned URL for playback or download."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

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
            detail=(
                "This media asset has expired under the 7-day retention policy "
                "and is no longer playable"
            ),
        )

    if media.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Media asset is not verified (current status: {media.status})",
        )

    url = storage.create_presigned_download_url(
        media.s3_object_key,
        expires_in=settings.SIGNED_URL_TTL_SECONDS,
        filename=media.original_filename,
    )

    return PreviewUrlResponse(
        preview_url=url,
        expires_in=settings.SIGNED_URL_TTL_SECONDS,
        status=media.status,
    )


@router.delete("/{media_id}")
async def delete_media(
    project_id: str,
    media_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
    storage: BaseStorageService = Depends(get_storage),
) -> dict[str, object]:
    """Delete a media asset and its underlying S3 storage object idempotently."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    media = repo.get_media(media_id, user.user_id)
    if not media or media.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found or access denied",
        )

    # Delete storage object
    storage.delete_object(media.s3_object_key)
    # Delete metadata record
    repo.delete_media(media_id, user.user_id)

    return {"success": True, "media_id": media_id, "detail": "Media asset deleted"}
