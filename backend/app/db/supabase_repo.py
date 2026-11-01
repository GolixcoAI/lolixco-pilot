"""Supabase PostgREST repository implementation.

Executes user-scoped CRUD operations against Supabase PostgreSQL via PostgREST REST API.
Enforces Row Level Security (RLS) using the authenticated user's access token and user_id.
Never uses SUPABASE_SERVICE_ROLE_KEY for user CRUD operations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.db.repository import (
    AnalysisRecord,
    BaseRepository,
    MediaRecord,
    ProjectRecord,
)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base error for database repository operations."""


class DatabaseConnectionError(DatabaseError):
    """Raised when connecting to the database fails or times out."""


class DatabasePermissionError(DatabaseError):
    """Raised on authentication failure or RLS permission violation."""


class DatabaseRecordNotFoundError(DatabaseError):
    """Raised when an expected record is not found."""


def _parse_timestamp(val: Any) -> datetime:
    """Parse ISO timestamp string from PostgREST to datetime with UTC timezone."""
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=UTC)
    if isinstance(val, str):
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return datetime.now(UTC)


def _row_to_project(row: dict[str, Any]) -> ProjectRecord:
    """Map a PostgREST projects row to ProjectRecord."""
    return ProjectRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        name=str(row.get("name", "Untitled Cut")),
        aspect_ratio=str(row.get("aspect_ratio", "9:16")),
        created_at=_parse_timestamp(row["created_at"]),
        updated_at=_parse_timestamp(row["updated_at"]),
    )


def _row_to_media(row: dict[str, Any]) -> MediaRecord:
    """Map a PostgREST media row to MediaRecord."""
    verified_size = row.get("verified_size_bytes")
    duration = row.get("duration_seconds")
    return MediaRecord(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        user_id=str(row["user_id"]),
        original_filename=str(row["original_filename"]),
        s3_object_key=str(row["s3_object_key"]),
        content_type=str(row["content_type"]),
        declared_size_bytes=int(row["declared_size_bytes"]),
        verified_size_bytes=int(verified_size) if verified_size is not None else None,
        duration_seconds=float(duration) if duration is not None else None,
        status=str(row["status"]),
        expires_at=_parse_timestamp(row["expires_at"]),
        created_at=_parse_timestamp(row["created_at"]),
        updated_at=_parse_timestamp(row["updated_at"]),
    )


def _row_to_analysis(row: dict[str, Any]) -> AnalysisRecord:
    """Map a PostgREST analyses row to AnalysisRecord."""
    return AnalysisRecord(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        media_id=str(row["media_id"]),
        user_id=str(row["user_id"]),
        status=str(row.get("status", "completed")),
        blueprint=row.get("blueprint"),
        provider=row.get("provider"),
        model=row.get("model"),
        source_identification=row.get("source_identification"),
        audio_intelligence=row.get("audio_intelligence"),
        usage_metadata=row.get("usage_metadata"),
        user_feedback=row.get("user_feedback"),
        created_at=_parse_timestamp(row["created_at"]),
        updated_at=_parse_timestamp(row["updated_at"]),
    )


class SupabaseRepository(BaseRepository):
    """PostgREST-backed repository scoped to a single authenticated user session.

    Every request to PostgREST sends:
    - apikey: <SUPABASE_PUBLISHABLE_KEY>
    - Authorization: Bearer <CURRENT_USER_ACCESS_TOKEN>

    All database queries are explicitly filtered by user_id and constrained
    by Supabase Row Level Security (auth.uid() = user_id).
    """

    def __init__(
        self,
        supabase_url: str,
        publishable_key: str,
        user_id: str,
        access_token: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not supabase_url or not supabase_url.strip():
            raise ValueError("supabase_url must be provided for SupabaseRepository")
        if not publishable_key or not publishable_key.strip():
            raise ValueError("publishable_key must be provided for SupabaseRepository")
        if not user_id or not user_id.strip():
            raise ValueError("user_id must be provided for SupabaseRepository")
        if not access_token or not access_token.strip():
            raise ValueError("access_token must be provided for SupabaseRepository")

        # Validate that user_id is a valid UUID
        try:
            self.user_id = str(uuid.UUID(str(user_id)))
        except ValueError as exc:
            raise ValueError(f"user_id must be a valid UUID: {exc}") from exc

        self.supabase_url = supabase_url.rstrip("/")
        self.publishable_key = publishable_key.strip()
        self.access_token = access_token.strip()
        self.base_url = f"{self.supabase_url}/rest/v1"
        self.timeout_seconds = timeout_seconds

        self._headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(timeout=self.timeout_seconds)
            self._owns_client = True

    def close(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> SupabaseRepository:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json_data: Any | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        """Execute a PostgREST HTTP request with error mapping and secret sanitization."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer

        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise DatabaseConnectionError(
                f"Supabase PostgREST request timed out after {self.timeout_seconds}s"
            ) from exc
        except httpx.RequestError as exc:
            raise DatabaseConnectionError(
                f"Supabase PostgREST network connection error: {type(exc).__name__}"
            ) from exc

        # Handle HTTP error status codes
        if response.status_code in (401, 403):
            raise DatabasePermissionError(
                f"Supabase access denied ({response.status_code}): "
                "authentication failure or RLS policy violation"
            )

        if response.status_code >= 400:
            safe_detail: str = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    safe_detail = str(body.get("message") or body.get("error") or "")
            except Exception:
                safe_detail = response.text[:200]
            detail_str = safe_detail or "Request failed"
            raise DatabaseError(f"Supabase database error ({response.status_code}): {detail_str}")

        return response

    # -------------------------------------------------------------------------
    # Project Methods
    # -------------------------------------------------------------------------

    def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None:
        """Retrieve a project by ID, strictly scoped to the authenticated owner."""
        # Enforce caller user_id matches repository session
        if user_id != self.user_id:
            return None

        try:
            clean_proj_id = str(uuid.UUID(str(project_id)))
        except ValueError:
            return None

        params = {
            "id": f"eq.{clean_proj_id}",
            "user_id": f"eq.{self.user_id}",
            "limit": "1",
        }
        res = self._request("GET", "/projects", params=params)
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_project(rows[0])

    def list_projects(self, user_id: str) -> list[ProjectRecord]:
        """List all projects owned by the authenticated user."""
        if user_id != self.user_id:
            return []

        params = {
            "user_id": f"eq.{self.user_id}",
            "order": "created_at.desc",
        }
        res = self._request("GET", "/projects", params=params)
        rows: list[dict[str, Any]] = res.json()
        return [_row_to_project(row) for row in rows]

    def create_project(
        self, user_id: str, name: str = "Untitled Cut", aspect_ratio: str = "9:16"
    ) -> ProjectRecord:
        """Create a new project owned by the authenticated user."""
        if user_id != self.user_id:
            raise DatabasePermissionError("Cannot create project for another user identity")

        now = datetime.now(UTC).isoformat()
        payload = {
            "user_id": self.user_id,
            "name": name,
            "aspect_ratio": aspect_ratio,
            "created_at": now,
            "updated_at": now,
        }
        res = self._request(
            "POST",
            "/projects",
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            raise DatabaseError("Supabase insert succeeded but returned no representation")
        return _row_to_project(rows[0])

    def get_or_create_default_project(self, user_id: str) -> ProjectRecord:
        """Get the user's most recent project or create a default one."""
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
        """Update a project's name or aspect ratio, owner scoped."""
        if user_id != self.user_id:
            return None

        try:
            clean_proj_id = str(uuid.UUID(str(project_id)))
        except ValueError:
            return None

        payload: dict[str, Any] = {
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if name is not None:
            payload["name"] = name
        if aspect_ratio is not None:
            payload["aspect_ratio"] = aspect_ratio

        params = {
            "id": f"eq.{clean_proj_id}",
            "user_id": f"eq.{self.user_id}",
        }
        res = self._request(
            "PATCH",
            "/projects",
            params=params,
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_project(rows[0])

    # -------------------------------------------------------------------------
    # Media Methods
    # -------------------------------------------------------------------------

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
        """Create a new media record under an authenticated project."""
        if user_id != self.user_id:
            raise DatabasePermissionError("Cannot create media for another user identity")

        try:
            clean_proj_id = str(uuid.UUID(str(project_id)))
        except ValueError as exc:
            raise ValueError(f"project_id must be a valid UUID: {exc}") from exc

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=retention_days)

        payload: dict[str, Any] = {
            "project_id": clean_proj_id,
            "user_id": self.user_id,
            "original_filename": original_filename,
            "s3_object_key": s3_object_key,
            "content_type": content_type,
            "declared_size_bytes": declared_size_bytes,
            "status": "pending",
            "expires_at": expires_at.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        if media_id is not None:
            try:
                payload["id"] = str(uuid.UUID(str(media_id)))
            except ValueError as exc:
                raise ValueError(f"media_id must be a valid UUID: {exc}") from exc

        res = self._request(
            "POST",
            "/media",
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            raise DatabaseError("Supabase media insert succeeded but returned no representation")
        return _row_to_media(rows[0])

    def get_media(self, media_id: str, user_id: str) -> MediaRecord | None:
        """Retrieve a single media record by ID, strictly owner scoped."""
        if user_id != self.user_id:
            return None

        try:
            clean_media_id = str(uuid.UUID(str(media_id)))
        except ValueError:
            return None

        params = {
            "id": f"eq.{clean_media_id}",
            "user_id": f"eq.{self.user_id}",
            "limit": "1",
        }
        res = self._request("GET", "/media", params=params)
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_media(rows[0])

    def list_media(self, project_id: str, user_id: str) -> list[MediaRecord]:
        """List all media assets for a project belonging to the authenticated user."""
        if user_id != self.user_id:
            return []

        try:
            clean_proj_id = str(uuid.UUID(str(project_id)))
        except ValueError:
            return []

        params = {
            "project_id": f"eq.{clean_proj_id}",
            "user_id": f"eq.{self.user_id}",
            "order": "created_at.asc",
        }
        res = self._request("GET", "/media", params=params)
        rows: list[dict[str, Any]] = res.json()
        return [_row_to_media(row) for row in rows]

    def update_media_status(
        self,
        media_id: str,
        user_id: str,
        status: str,
        verified_size_bytes: int | None = None,
        duration_seconds: float | None = None,
    ) -> MediaRecord | None:
        """Update media status, size, and duration after S3 verification."""
        if user_id != self.user_id:
            return None

        try:
            clean_media_id = str(uuid.UUID(str(media_id)))
        except ValueError:
            return None

        payload: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if verified_size_bytes is not None:
            payload["verified_size_bytes"] = verified_size_bytes
        if duration_seconds is not None:
            payload["duration_seconds"] = duration_seconds

        params = {
            "id": f"eq.{clean_media_id}",
            "user_id": f"eq.{self.user_id}",
        }
        res = self._request(
            "PATCH",
            "/media",
            params=params,
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_media(rows[0])

    def delete_media(self, media_id: str, user_id: str) -> bool:
        """Delete a media record, strictly owner scoped."""
        if user_id != self.user_id:
            return False

        try:
            clean_media_id = str(uuid.UUID(str(media_id)))
        except ValueError:
            return False

        params = {
            "id": f"eq.{clean_media_id}",
            "user_id": f"eq.{self.user_id}",
        }
        res = self._request(
            "DELETE",
            "/media",
            params=params,
            prefer="return=representation",
        )
        if res.status_code == 204:
            return True
        rows: list[dict[str, Any]] = res.json()
        return len(rows) > 0

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
        """Persist a new analysis record into Supabase PostgreSQL."""
        if user_id != self.user_id:
            raise DatabasePermissionError("Cross-user analysis creation forbidden")

        clean_analysis_id = str(uuid.UUID(str(analysis_id))) if analysis_id else str(uuid.uuid4())
        clean_project_id = str(uuid.UUID(str(project_id)))
        clean_media_id = str(uuid.UUID(str(media_id)))

        payload: dict[str, Any] = {
            "id": clean_analysis_id,
            "project_id": clean_project_id,
            "media_id": clean_media_id,
            "user_id": self.user_id,
            "status": status,
        }
        if blueprint is not None:
            payload["blueprint"] = blueprint
        if provider is not None:
            payload["provider"] = provider
        if model is not None:
            payload["model"] = model
        if source_identification is not None:
            payload["source_identification"] = source_identification
        if audio_intelligence is not None:
            payload["audio_intelligence"] = audio_intelligence
        if usage_metadata is not None:
            payload["usage_metadata"] = usage_metadata
        if user_feedback is not None:
            payload["user_feedback"] = user_feedback

        res = self._request(
            "POST",
            "/analyses",
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            raise DatabaseError("Supabase returned empty response on analysis creation")
        return _row_to_analysis(rows[0])

    def get_analysis(self, analysis_id: str, user_id: str) -> AnalysisRecord | None:
        """Fetch an analysis record by ID, strictly owner scoped."""
        if user_id != self.user_id:
            return None

        try:
            clean_analysis_id = str(uuid.UUID(str(analysis_id)))
        except ValueError:
            return None

        params = {
            "id": f"eq.{clean_analysis_id}",
            "user_id": f"eq.{self.user_id}",
        }
        res = self._request("GET", "/analyses", params=params)
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_analysis(rows[0])

    def get_latest_analysis_for_media(self, media_id: str, user_id: str) -> AnalysisRecord | None:
        """Fetch the most recent analysis record for a media asset."""
        if user_id != self.user_id:
            return None

        try:
            clean_media_id = str(uuid.UUID(str(media_id)))
        except ValueError:
            return None

        params = {
            "media_id": f"eq.{clean_media_id}",
            "user_id": f"eq.{self.user_id}",
            "order": "created_at.desc",
            "limit": "1",
        }
        res = self._request("GET", "/analyses", params=params)
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_analysis(rows[0])

    def update_analysis_feedback(
        self, analysis_id: str, user_id: str, feedback: dict[str, Any]
    ) -> AnalysisRecord | None:
        """Update user confirmation / feedback on an analysis record."""
        if user_id != self.user_id:
            return None

        try:
            clean_analysis_id = str(uuid.UUID(str(analysis_id)))
        except ValueError:
            return None

        params = {
            "id": f"eq.{clean_analysis_id}",
            "user_id": f"eq.{self.user_id}",
        }
        payload = {
            "user_feedback": feedback,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        res = self._request(
            "PATCH",
            "/analyses",
            params=params,
            json_data=payload,
            prefer="return=representation",
        )
        rows: list[dict[str, Any]] = res.json()
        if not rows:
            return None
        return _row_to_analysis(rows[0])
