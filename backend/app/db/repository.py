"""Database repository interface and local memory/sqlite implementation with RLS simulation.

Ensures strict user ownership boundaries (Row Level Security):
Users can only read, write, or delete their own projects and media.
Cross-user access returns None or raises 403 Forbidden.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings


@dataclass
class ProjectRecord:
    id: str
    user_id: str
    name: str
    aspect_ratio: str
    created_at: datetime
    updated_at: datetime


@dataclass
class MediaRecord:
    id: str
    project_id: str
    user_id: str
    original_filename: str
    s3_object_key: str
    content_type: str
    declared_size_bytes: int
    verified_size_bytes: int | None
    duration_seconds: float | None
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass
class AnalysisRecord:
    id: str
    project_id: str
    media_id: str
    user_id: str
    status: str
    blueprint: dict[str, Any] | None
    provider: str | None
    model: str | None
    source_identification: dict[str, Any] | None
    audio_intelligence: dict[str, Any] | None
    usage_metadata: dict[str, Any] | None
    user_feedback: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class BaseRepository(ABC):
    @abstractmethod
    def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None: ...

    @abstractmethod
    def list_projects(self, user_id: str) -> list[ProjectRecord]: ...

    @abstractmethod
    def create_project(
        self, user_id: str, name: str = "Untitled Cut", aspect_ratio: str = "9:16"
    ) -> ProjectRecord: ...

    @abstractmethod
    def get_or_create_default_project(self, user_id: str) -> ProjectRecord: ...

    @abstractmethod
    def update_project(
        self,
        project_id: str,
        user_id: str,
        name: str | None = None,
        aspect_ratio: str | None = None,
    ) -> ProjectRecord | None: ...

    @abstractmethod
    def create_media(
        self,
        project_id: str,
        user_id: str,
        original_filename: str,
        s3_object_key: str,
        content_type: str,
        declared_size_bytes: int,
        retention_days: int = 7,
        media_id: str | None = None,
    ) -> MediaRecord: ...

    @abstractmethod
    def get_media(self, media_id: str, user_id: str) -> MediaRecord | None: ...

    @abstractmethod
    def list_media(self, project_id: str, user_id: str) -> list[MediaRecord]: ...

    @abstractmethod
    def update_media_status(
        self,
        media_id: str,
        user_id: str,
        status: str,
        verified_size_bytes: int | None = None,
        duration_seconds: float | None = None,
    ) -> MediaRecord | None: ...

    @abstractmethod
    def delete_media(self, media_id: str, user_id: str) -> bool: ...

    @abstractmethod
    def create_analysis(
        self,
        project_id: str,
        media_id: str,
        user_id: str,
        status: str = "completed",
        blueprint: dict[str, Any] | None = None,
        provider: str | None = None,
        model: str | None = None,
        source_identification: dict[str, Any] | None = None,
        audio_intelligence: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        user_feedback: dict[str, Any] | None = None,
        analysis_id: str | None = None,
    ) -> AnalysisRecord: ...

    @abstractmethod
    def get_analysis(self, analysis_id: str, user_id: str) -> AnalysisRecord | None: ...

    @abstractmethod
    def get_latest_analysis_for_media(
        self, media_id: str, user_id: str
    ) -> AnalysisRecord | None: ...

    @abstractmethod
    def update_analysis_feedback(
        self, analysis_id: str, user_id: str, feedback: dict[str, Any]
    ) -> AnalysisRecord | None: ...


class InMemoryRepository(BaseRepository):
    """In-memory repository simulating Supabase PostgreSQL with strict Row Level Security."""

    def __init__(self) -> None:
        self.projects: dict[str, ProjectRecord] = {}
        self.media: dict[str, MediaRecord] = {}
        self.analyses: dict[str, AnalysisRecord] = {}

    def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None:
        project = self.projects.get(project_id)
        if not project or project.user_id != user_id:
            return None
        return project

    def list_projects(self, user_id: str) -> list[ProjectRecord]:
        return [p for p in self.projects.values() if p.user_id == user_id]

    def create_project(
        self, user_id: str, name: str = "Untitled Cut", aspect_ratio: str = "9:16"
    ) -> ProjectRecord:
        now = datetime.now(UTC)
        record = ProjectRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            aspect_ratio=aspect_ratio,
            created_at=now,
            updated_at=now,
        )
        self.projects[record.id] = record
        return record

    def get_or_create_default_project(self, user_id: str) -> ProjectRecord:
        existing = self.list_projects(user_id)
        if existing:
            return existing[0]
        return self.create_project(user_id=user_id)

    def update_project(
        self,
        project_id: str,
        user_id: str,
        name: str | None = None,
        aspect_ratio: str | None = None,
    ) -> ProjectRecord | None:
        project = self.get_project(project_id, user_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if aspect_ratio is not None:
            project.aspect_ratio = aspect_ratio
        project.updated_at = datetime.now(UTC)
        return project

    def create_media(
        self,
        project_id: str,
        user_id: str,
        original_filename: str,
        s3_object_key: str,
        content_type: str,
        declared_size_bytes: int,
        retention_days: int = 7,
        media_id: str | None = None,
    ) -> MediaRecord:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=retention_days)
        record = MediaRecord(
            id=media_id if media_id is not None else str(uuid.uuid4()),
            project_id=project_id,
            user_id=user_id,
            original_filename=original_filename,
            s3_object_key=s3_object_key,
            content_type=content_type,
            declared_size_bytes=declared_size_bytes,
            verified_size_bytes=None,
            duration_seconds=None,
            status="pending",
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self.media[record.id] = record
        return record

    def get_media(self, media_id: str, user_id: str) -> MediaRecord | None:
        record = self.media.get(media_id)
        if not record or record.user_id != user_id:
            return None
        return record

    def list_media(self, project_id: str, user_id: str) -> list[MediaRecord]:
        # Enforce both project ownership and media ownership
        return [
            m for m in self.media.values() if m.project_id == project_id and m.user_id == user_id
        ]

    def update_media_status(
        self,
        media_id: str,
        user_id: str,
        status: str,
        verified_size_bytes: int | None = None,
        duration_seconds: float | None = None,
    ) -> MediaRecord | None:
        record = self.get_media(media_id, user_id)
        if not record:
            return None
        record.status = status
        record.updated_at = datetime.now(UTC)
        if verified_size_bytes is not None:
            record.verified_size_bytes = verified_size_bytes
        if duration_seconds is not None:
            record.duration_seconds = duration_seconds
        return record

    def delete_media(self, media_id: str, user_id: str) -> bool:
        record = self.get_media(media_id, user_id)
        if not record:
            return False
        del self.media[media_id]
        return True

    def create_analysis(
        self,
        project_id: str,
        media_id: str,
        user_id: str,
        status: str = "completed",
        blueprint: dict[str, Any] | None = None,
        provider: str | None = None,
        model: str | None = None,
        source_identification: dict[str, Any] | None = None,
        audio_intelligence: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        user_feedback: dict[str, Any] | None = None,
        analysis_id: str | None = None,
    ) -> AnalysisRecord:
        now = datetime.now(UTC)
        record = AnalysisRecord(
            id=analysis_id if analysis_id is not None else str(uuid.uuid4()),
            project_id=project_id,
            media_id=media_id,
            user_id=user_id,
            status=status,
            blueprint=blueprint,
            provider=provider,
            model=model,
            source_identification=source_identification,
            audio_intelligence=audio_intelligence,
            usage_metadata=usage_metadata,
            user_feedback=user_feedback,
            created_at=now,
            updated_at=now,
        )
        self.analyses[record.id] = record
        return record

    def get_analysis(self, analysis_id: str, user_id: str) -> AnalysisRecord | None:
        rec = self.analyses.get(analysis_id)
        if not rec or rec.user_id != user_id:
            return None
        return rec

    def get_latest_analysis_for_media(self, media_id: str, user_id: str) -> AnalysisRecord | None:
        matching = [
            a for a in self.analyses.values() if a.media_id == media_id and a.user_id == user_id
        ]
        if not matching:
            return None
        matching.sort(key=lambda x: x.created_at, reverse=True)
        return matching[0]

    def update_analysis_feedback(
        self, analysis_id: str, user_id: str, feedback: dict[str, Any]
    ) -> AnalysisRecord | None:
        rec = self.get_analysis(analysis_id, user_id)
        if not rec:
            return None
        rec.user_feedback = feedback
        rec.updated_at = datetime.now(UTC)
        return rec


# Global default singleton repository instance for isolated tests/memory mode
_default_repo = InMemoryRepository()


def get_repository(
    user: AuthenticatedUser | None = Depends(get_current_user),
    settings: Settings | None = Depends(get_settings),
) -> Generator[BaseRepository, None, None]:
    """FastAPI dependency for accessing the data repository.

    - If DATABASE_PROVIDER=memory: yields the in-memory repository.
    - If DATABASE_PROVIDER=supabase: yields a request-scoped SupabaseRepository
      bound to the current authenticated user's access token and user_id, ensuring
      PostgREST connections are closed when the request completes.
    """
    from app.db.supabase_repo import SupabaseRepository

    active_settings = settings or get_settings()

    if active_settings.DATABASE_PROVIDER == "memory":
        yield _default_repo
        return

    if active_settings.DATABASE_PROVIDER == "supabase":
        if not active_settings.SUPABASE_URL or not active_settings.SUPABASE_PUBLISHABLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Supabase repository configuration error: SUPABASE_URL and "
                    "SUPABASE_PUBLISHABLE_KEY must be configured when "
                    "DATABASE_PROVIDER is 'supabase'"
                ),
            )

        if not user or not user.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for Supabase database operations",
            )

        if not user.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid access token required for Supabase database operations",
            )

        client = httpx.Client(timeout=10.0)
        repo = SupabaseRepository(
            supabase_url=active_settings.SUPABASE_URL,
            publishable_key=active_settings.SUPABASE_PUBLISHABLE_KEY,
            user_id=user.user_id,
            access_token=user.access_token,
            client=client,
        )
        try:
            yield repo
        finally:
            client.close()
        return

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unsupported DATABASE_PROVIDER '{active_settings.DATABASE_PROVIDER}'",
    )
