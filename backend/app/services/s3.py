"""Amazon S3 private storage service for video uploads.

Handles unpredictable object key generation, presigned PUT upload URLs,
server-side object verification via head_object, temporary presigned GET URLs,
and idempotent deletions.
Includes a mock storage provider for credential-free testing and offline development.
"""

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import Settings


@dataclass(frozen=True)
class PresignedUploadResponse:
    """Details for a direct client-to-storage upload."""

    upload_url: str
    s3_key: str
    expires_in: int


@dataclass(frozen=True)
class ObjectMetadata:
    """Verified S3 object properties."""

    exists: bool
    size_bytes: int
    content_type: str | None = None


ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset({"mp4", "mov", "webm"})


def generate_opaque_object_key(
    user_id: str,
    project_id: str,
    media_id: str,
    extension: str,
) -> str:
    """Create an unpredictable, scoped S3 object key with validated extension.

    Ensures user_id, project_id, and media_id are valid UUIDs, the extension is
    within ALLOWED_VIDEO_EXTENSIONS, and the object name is a cryptographically
    random token. The user's original filename is never used in the storage key.
    """
    try:
        clean_user_id = str(uuid.UUID(str(user_id)))
        clean_project_id = str(uuid.UUID(str(project_id)))
        clean_media_id = str(uuid.UUID(str(media_id)))
    except ValueError as exc:
        raise ValueError(
            f"Storage key components (user_id, project_id, media_id) must be valid UUIDs: {exc}"
        ) from exc

    clean_ext = extension.strip().lstrip(".").lower()
    if clean_ext not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise ValueError(
            f"Invalid or unsupported video extension '{extension}'. Allowed extensions: {allowed}"
        )

    random_token = uuid.uuid4().hex
    prefix = f"users/{clean_user_id}/projects/{clean_project_id}/media/{clean_media_id}"
    return f"{prefix}/{random_token}.{clean_ext}"


def generate_proxy_object_key(
    user_id: str,
    project_id: str,
    media_id: str,
) -> str:
    """Create a scoped S3 object key for preview proxy."""
    try:
        clean_user_id = str(uuid.UUID(str(user_id)))
        clean_project_id = str(uuid.UUID(str(project_id)))
        clean_media_id = str(uuid.UUID(str(media_id)))
    except ValueError as exc:
        raise ValueError(f"Storage key components must be valid UUIDs: {exc}") from exc
    return (
        f"proxies/users/{clean_user_id}/projects/{clean_project_id}/"
        f"media/{clean_media_id}/preview_h264.mp4"
    )


def generate_export_object_key(
    user_id: str,
    project_id: str,
    export_id: str,
) -> str:
    """Create a scoped S3 object key for rendered exports."""
    try:
        clean_user_id = str(uuid.UUID(str(user_id)))
        clean_project_id = str(uuid.UUID(str(project_id)))
        clean_export_id = str(uuid.UUID(str(export_id)))
    except ValueError as exc:
        raise ValueError(f"Storage key components must be valid UUIDs: {exc}") from exc
    return (
        f"exports/users/{clean_user_id}/projects/{clean_project_id}/exports/{clean_export_id}.mp4"
    )


class BaseStorageService(ABC):
    """Abstract interface for storage operations."""

    def generate_object_key(
        self, user_id: str, project_id: str, media_id: str, extension: str
    ) -> str:
        """Create an unpredictable, scoped object storage key."""
        return generate_opaque_object_key(user_id, project_id, media_id, extension)

    def generate_proxy_key(self, user_id: str, project_id: str, media_id: str) -> str:
        """Create scoped proxy storage key."""
        return generate_proxy_object_key(user_id, project_id, media_id)

    def generate_export_key(self, user_id: str, project_id: str, export_id: str) -> str:
        """Create scoped export storage key."""
        return generate_export_object_key(user_id, project_id, export_id)

    @abstractmethod
    def create_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> PresignedUploadResponse:
        """Generate a short-lived presigned PUT URL."""
        ...

    @abstractmethod
    def verify_object(self, s3_key: str) -> ObjectMetadata:
        """Verify uploaded object existence and byte size."""
        ...

    @abstractmethod
    def create_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int | None = None,
        filename: str | None = None,
    ) -> str:
        """Generate a short-lived authorized download/stream URL."""
        ...

    @abstractmethod
    def upload_file(self, local_path: str, s3_key: str, content_type: str = "video/mp4") -> None:
        """Upload a local file directly to storage."""
        ...

    @abstractmethod
    def download_file(self, s3_key: str, local_path: str) -> None:
        """Download an object to local file."""
        ...

    @abstractmethod
    def delete_object(self, s3_key: str) -> bool:
        """Idempotently delete an object from storage."""
        ...


class S3StorageService(BaseStorageService):
    """Production Amazon S3 private storage service."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if not settings.AWS_S3_BUCKET:
            raise ValueError("AWS_S3_BUCKET must be configured to initialize S3StorageService")

        self.settings = settings
        self.bucket = settings.AWS_S3_BUCKET
        self.region = settings.AWS_REGION
        self.default_ttl = settings.SIGNED_URL_TTL_SECONDS

        self.client: Any
        if client is not None:
            self.client = client
        else:
            session = boto3.session.Session(
                profile_name=settings.AWS_PROFILE or None,
            )
            client_kwargs: dict[str, Any] = {
                "region_name": self.region,
                "config": Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
            }
            if settings.AWS_ACCESS_KEY_ID:
                client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            if settings.AWS_SECRET_ACCESS_KEY:
                client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            self.client = session.client("s3", **client_kwargs)

    def create_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> PresignedUploadResponse:
        ttl = expires_in or self.default_ttl
        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=ttl,
            HttpMethod="PUT",
        )
        return PresignedUploadResponse(
            upload_url=url,
            s3_key=s3_key,
            expires_in=ttl,
        )

    def verify_object(self, s3_key: str) -> ObjectMetadata:
        try:
            res = self.client.head_object(Bucket=self.bucket, Key=s3_key)
            size = int(res.get("ContentLength", 0))
            content_type = res.get("ContentType")
            return ObjectMetadata(exists=True, size_bytes=size, content_type=content_type)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return ObjectMetadata(exists=False, size_bytes=0)
            raise

    def create_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int | None = None,
        filename: str | None = None,
    ) -> str:
        ttl = expires_in or self.default_ttl
        params: dict[str, str] = {"Bucket": self.bucket, "Key": s3_key}
        if filename:
            safe_name = os.path.basename(filename)
            params["ResponseContentDisposition"] = f'inline; filename="{safe_name}"'

        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=ttl,
        )

    def upload_file(self, local_path: str, s3_key: str, content_type: str = "video/mp4") -> None:
        self.client.upload_file(
            Filename=local_path,
            Bucket=self.bucket,
            Key=s3_key,
            ExtraArgs={"ContentType": content_type},
        )

    def download_file(self, s3_key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        self.client.download_file(Bucket=self.bucket, Key=s3_key, Filename=local_path)

    def delete_object(self, s3_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False


class MockStorageService(BaseStorageService):
    """In-memory / mock storage provider for local testing and offline execution."""

    def __init__(self, default_ttl: int = 900) -> None:
        self.default_ttl = default_ttl
        self.objects: dict[str, dict[str, object]] = {}

    def create_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> PresignedUploadResponse:
        ttl = expires_in or self.default_ttl
        # Deterministic mock signed upload URL
        url = f"https://mock-s3.localhost/uploads/{s3_key}?ttl={ttl}"
        # Pre-seed mock metadata
        self.objects[s3_key] = {
            "exists": True,
            "size_bytes": 1024 * 1024,  # default 1MB for mock uploads
            "content_type": content_type,
        }
        return PresignedUploadResponse(upload_url=url, s3_key=s3_key, expires_in=ttl)

    def set_mock_object(self, s3_key: str, size_bytes: int, exists: bool = True) -> None:
        """Helper to simulate upload completion in tests."""
        self.objects[s3_key] = {
            "exists": exists,
            "size_bytes": size_bytes,
            "content_type": "video/mp4",
        }

    def verify_object(self, s3_key: str) -> ObjectMetadata:
        data = self.objects.get(s3_key)
        if not data or not data.get("exists"):
            return ObjectMetadata(exists=False, size_bytes=0)
        size_val = data.get("size_bytes", 0)
        size_int = int(str(size_val)) if isinstance(size_val, (int, str)) else 0
        return ObjectMetadata(
            exists=True,
            size_bytes=size_int,
            content_type=str(data.get("content_type", "video/mp4")),
        )

    def create_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int | None = None,
        filename: str | None = None,
    ) -> str:
        ttl = expires_in or self.default_ttl
        return f"https://mock-s3.localhost/stream/{s3_key}?token=auth_token&expires={ttl}"

    def upload_file(self, local_path: str, s3_key: str, content_type: str = "video/mp4") -> None:
        size = os.path.getsize(local_path) if os.path.exists(local_path) else 1024
        self.objects[s3_key] = {
            "exists": True,
            "size_bytes": size,
            "content_type": content_type,
            "local_copy": local_path,
        }

    def download_file(self, s3_key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        obj = self.objects.get(s3_key)
        if obj and "local_copy" in obj and os.path.exists(str(obj["local_copy"])):
            shutil.copy(str(obj["local_copy"]), local_path)
        else:
            with open(local_path, "wb") as f:
                f.write(b"MOCK_MEDIA_CONTENT")

    def delete_object(self, s3_key: str) -> bool:
        if s3_key in self.objects:
            del self.objects[s3_key]
        return True


def get_storage_service(settings: Settings) -> BaseStorageService:
    """Return active storage service based on environment configuration."""
    if settings.AWS_S3_BUCKET and not settings.USE_MOCK_STORAGE:
        return S3StorageService(settings)
    return MockStorageService(default_ttl=settings.SIGNED_URL_TTL_SECONDS)


def get_storage() -> BaseStorageService:
    """FastAPI dependency for storage service."""
    from app.config import get_settings

    return get_storage_service(get_settings())
