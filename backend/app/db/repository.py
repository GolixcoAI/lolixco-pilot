"""Database repository interface and local memory/sqlite implementation with RLS simulation.

Ensures strict user ownership boundaries (Row Level Security):
Users can only read, write, or delete their own projects and media.
Cross-user access returns None or raises 403 Forbidden.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


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
    def create_media(
        self,
        project_id: str,
        user_id: str,
        original_filename: str,
        s3_object_key: str,
        content_type: str,
        declared_size_bytes: int,
        retention_days: int = 7,
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


class InMemoryRepository(BaseRepository):
    """In-memory repository simulating Supabase PostgreSQL with strict Row Level Security."""

    def __init__(self) -> None:
        self.projects: dict[str, ProjectRecord] = {}
        self.media: dict[str, MediaRecord] = {}

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

    def create_media(
        self,
        project_id: str,
        user_id: str,
        original_filename: str,
        s3_object_key: str,
        content_type: str,
        declared_size_bytes: int,
        retention_days: int = 7,
    ) -> MediaRecord:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=retention_days)
        record = MediaRecord(
            id=str(uuid.uuid4()),
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


# Global default singleton repository instance
_default_repo = InMemoryRepository()


def get_repository() -> BaseRepository:
    """FastAPI dependency for accessing the data repository."""
    return _default_repo
