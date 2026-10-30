"""Pydantic schemas for media assets and upload flows."""

import os
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm"}
ALLOWED_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm"}


class PresignUploadRequest(BaseModel):
    """Client request to obtain a presigned S3 upload URL."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename with extension",
    )
    content_type: str = Field(..., description="Declared MIME type of video")
    size_bytes: int = Field(
        ...,
        gt=0,
        le=104857600,
        description="Declared file size in bytes (max 100MB)",
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, val: str) -> str:
        clean_name = os.path.basename(val.strip())
        if not clean_name or clean_name in (".", ".."):
            raise ValueError("Invalid filename")
        ext = os.path.splitext(clean_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"Unsupported file extension '{ext}'. Allowed extensions: {allowed}")
        return clean_name

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, val: str) -> str:
        clean_mime = val.strip().lower()
        if clean_mime not in ALLOWED_MIME_TYPES:
            allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
            raise ValueError(
                f"Unsupported content type '{clean_mime}'. Allowed MIME types: {allowed}"
            )
        return clean_mime


class PresignUploadResponse(BaseModel):
    """Response containing temporary S3 upload URL and asset identifiers."""

    media_id: str
    project_id: str
    s3_key: str
    upload_url: str
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    """Optional client confirmation payload."""

    duration_seconds: float | None = Field(default=None, gt=0, le=300)


class MediaResponse(BaseModel):
    """Persisted media asset representation."""

    id: str
    project_id: str
    user_id: str
    original_filename: str
    content_type: str
    declared_size_bytes: int
    verified_size_bytes: int | None = None
    duration_seconds: float | None = None
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    preview_url: str | None = None


class PreviewUrlResponse(BaseModel):
    """Authorized temporary preview/download URL."""

    preview_url: str
    expires_in: int
    status: str
