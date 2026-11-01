"""Mocked HTTPX unit tests for SupabaseRepository and PostgREST interaction.

Verifies:
- Project creation, retrieval, listing, and updates.
- Media creation, retrieval, listing, status updates, and deletion.
- Correct API key and user JWT Bearer headers on all requests.
- Strict user ID scoping and RLS ownership enforcement.
- Safe error handling on HTTP failures, timeouts, and permission denials.
- Fail-closed behavior (no silent fallback to memory).
- Repository isolation between distinct authenticated users.
- Resource cleanup on request completion.

All tests use in-memory MockTransport with zero cloud network calls or credit consumption.
"""

import json
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from app.auth import AuthenticatedUser
from app.config import Settings
from app.db.repository import (
    InMemoryRepository,
    MediaRecord,
    ProjectRecord,
    get_repository,
)
from app.db.supabase_repo import (
    DatabaseConnectionError,
    DatabaseError,
    DatabasePermissionError,
    SupabaseRepository,
)

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())
USER_A_TOKEN = "jwt.userA.signature"
USER_B_TOKEN = "jwt.userB.signature"
MOCK_SUPABASE_URL = "https://mockproject.supabase.co"
MOCK_PUB_KEY = "sb_publishable_key_test_12345"


class PostgrestMockDatabase:
    """In-memory stateful store simulating PostgREST table behavior."""

    def __init__(self) -> None:
        self.projects: dict[str, dict[str, Any]] = {}
        self.media: dict[str, dict[str, Any]] = {}
        self.analyses: dict[str, dict[str, Any]] = {}
        self.recorded_requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.recorded_requests.append(request)

        # Enforce header presence on all requests
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("apikey", "")

        if not auth_header.startswith("Bearer "):
            return httpx.Response(401, json={"message": "Missing Bearer token"})
        if not api_key:
            return httpx.Response(401, json={"message": "No API key found in request"})

        token = auth_header.replace("Bearer ", "").strip()
        parsed_url = urlparse(str(request.url))
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # Extract table from path (/rest/v1/projects, /rest/v1/media, /rest/v1/analyses)
        table = path.replace("/rest/v1/", "").strip("/")

        if table == "projects":
            return self._handle_projects(request, token, query)
        elif table == "media":
            return self._handle_media(request, token, query)
        elif table == "analyses":
            return self._handle_analyses(request, token, query)

        return httpx.Response(404, json={"message": f"Table '{table}' not found"})

    def _handle_projects(
        self, request: httpx.Request, token: str, query: dict[str, list[str]]
    ) -> httpx.Response:
        method = request.method

        if method == "GET":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]

            results = list(self.projects.values())
            if user_id_filter:
                uid = user_id_filter.replace("eq.", "")
                results = [r for r in results if r["user_id"] == uid]
            if id_filter:
                pid = id_filter.replace("eq.", "")
                results = [r for r in results if r["id"] == pid]

            return httpx.Response(200, json=results)

        elif method == "POST":
            data = json.loads(request.read().decode("utf-8"))
            proj_id = data.get("id") or str(uuid.uuid4())
            record = {
                "id": proj_id,
                "user_id": data["user_id"],
                "name": data.get("name", "Untitled Cut"),
                "aspect_ratio": data.get("aspect_ratio", "9:16"),
                "created_at": data.get("created_at", "2026-10-31T20:00:00+00:00"),
                "updated_at": data.get("updated_at", "2026-10-31T20:00:00+00:00"),
            }
            self.projects[proj_id] = record
            return httpx.Response(201, json=[record])

        elif method == "PATCH":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]
            if not id_filter:
                return httpx.Response(400, json={"message": "Missing id filter"})

            pid = id_filter.replace("eq.", "")
            patch_uid = user_id_filter.replace("eq.", "") if user_id_filter else None

            target_record = self.projects.get(pid)
            if not target_record or (patch_uid and target_record["user_id"] != patch_uid):
                return httpx.Response(200, json=[])

            updates = json.loads(request.read().decode("utf-8"))
            target_record.update(updates)
            return httpx.Response(200, json=[target_record])

        return httpx.Response(405)

    def _handle_media(
        self, request: httpx.Request, token: str, query: dict[str, list[str]]
    ) -> httpx.Response:
        method = request.method

        if method == "GET":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]
            project_id_filter = query.get("project_id", [None])[0]

            results = list(self.media.values())
            if user_id_filter:
                uid = user_id_filter.replace("eq.", "")
                results = [r for r in results if r["user_id"] == uid]
            if id_filter:
                mid = id_filter.replace("eq.", "")
                results = [r for r in results if r["id"] == mid]
            if project_id_filter:
                pid = project_id_filter.replace("eq.", "")
                results = [r for r in results if r["project_id"] == pid]

            return httpx.Response(200, json=results)

        elif method == "POST":
            data = json.loads(request.read().decode("utf-8"))
            mid = data.get("id") or str(uuid.uuid4())
            record = {
                "id": mid,
                "project_id": data["project_id"],
                "user_id": data["user_id"],
                "original_filename": data["original_filename"],
                "s3_object_key": data["s3_object_key"],
                "content_type": data["content_type"],
                "declared_size_bytes": data["declared_size_bytes"],
                "verified_size_bytes": data.get("verified_size_bytes"),
                "duration_seconds": data.get("duration_seconds"),
                "status": data.get("status", "pending"),
                "expires_at": data.get("expires_at", "2026-11-07T20:00:00+00:00"),
                "created_at": data.get("created_at", "2026-10-31T20:00:00+00:00"),
                "updated_at": data.get("updated_at", "2026-10-31T20:00:00+00:00"),
            }
            self.media[mid] = record
            return httpx.Response(201, json=[record])

        elif method == "PATCH":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]
            if not id_filter:
                return httpx.Response(400, json={"message": "Missing id filter"})

            mid = id_filter.replace("eq.", "")
            patch_uid = user_id_filter.replace("eq.", "") if user_id_filter else None

            patch_record = self.media.get(mid)
            if not patch_record or (patch_uid and patch_record["user_id"] != patch_uid):
                return httpx.Response(200, json=[])

            updates = json.loads(request.read().decode("utf-8"))
            patch_record.update(updates)
            return httpx.Response(200, json=[patch_record])

        elif method == "DELETE":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]
            if not id_filter:
                return httpx.Response(400, json={"message": "Missing id filter"})

            mid = id_filter.replace("eq.", "")
            del_uid = user_id_filter.replace("eq.", "") if user_id_filter else None

            del_record = self.media.get(mid)
            if not del_record or (del_uid and del_record["user_id"] != del_uid):
                return httpx.Response(200, json=[])

            del self.media[mid]
            return httpx.Response(200, json=[del_record])

        return httpx.Response(405)

    def _handle_analyses(
        self, request: httpx.Request, token: str, query: dict[str, list[str]]
    ) -> httpx.Response:
        method = request.method

        if method == "GET":
            id_filter = query.get("id", [None])[0]
            media_id_filter = query.get("media_id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]

            results = list(self.analyses.values())
            if user_id_filter:
                uid = user_id_filter.replace("eq.", "")
                results = [r for r in results if r["user_id"] == uid]
            if media_id_filter:
                mid = media_id_filter.replace("eq.", "")
                results = [r for r in results if r["media_id"] == mid]
            if id_filter:
                aid = id_filter.replace("eq.", "")
                results = [r for r in results if r["id"] == aid]

            # If order=created_at.desc was queried, sort descending
            order_param = query.get("order", [""])[0]
            if "desc" in order_param:
                results = sorted(results, key=lambda x: str(x.get("created_at", "")), reverse=True)

            limit_param = query.get("limit", [None])[0]
            if limit_param:
                results = results[: int(limit_param)]

            return httpx.Response(200, json=results)

        elif method == "POST":
            data = json.loads(request.read().decode("utf-8"))
            analysis_id = data.get("id") or str(uuid.uuid4())
            record = {
                "id": analysis_id,
                "project_id": data["project_id"],
                "media_id": data["media_id"],
                "user_id": data["user_id"],
                "provider": data.get("provider", "mock"),
                "model": data.get("model", "mock-model"),
                "blueprint": data.get("blueprint", {}),
                "source_identification": data.get("source_identification"),
                "audio_intelligence": data.get("audio_intelligence"),
                "usage_metadata": data.get("usage_metadata"),
                "user_feedback": data.get("user_feedback"),
                "created_at": data.get("created_at", "2026-10-31T20:00:00+00:00"),
                "updated_at": data.get("updated_at", "2026-10-31T20:00:00+00:00"),
            }
            self.analyses[analysis_id] = record
            return httpx.Response(201, json=[record])

        elif method == "PATCH":
            id_filter = query.get("id", [None])[0]
            user_id_filter = query.get("user_id", [None])[0]
            if not id_filter:
                return httpx.Response(400, json={"message": "Missing id filter"})

            aid = id_filter.replace("eq.", "")
            patch_uid = user_id_filter.replace("eq.", "") if user_id_filter else None

            target = self.analyses.get(aid)
            if not target or (patch_uid and target["user_id"] != patch_uid):
                return httpx.Response(200, json=[])

            updates = json.loads(request.read().decode("utf-8"))
            target.update(updates)
            return httpx.Response(200, json=[target])

        return httpx.Response(405)


@pytest.fixture
def mock_db() -> PostgrestMockDatabase:
    return PostgrestMockDatabase()


@pytest.fixture
def client_a(mock_db: PostgrestMockDatabase) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(mock_db.handle_request))


@pytest.fixture
def repo_a(client_a: httpx.Client) -> SupabaseRepository:
    return SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client_a,
    )


# =============================================================================
# 1. Project Tests
# =============================================================================


def test_project_creation_and_retrieval(
    repo_a: SupabaseRepository, mock_db: PostgrestMockDatabase
) -> None:
    # 1. Create project
    proj = repo_a.create_project(user_id=USER_A_ID, name="Cinematic Teaser", aspect_ratio="16:9")
    assert isinstance(proj, ProjectRecord)
    assert proj.name == "Cinematic Teaser"
    assert proj.aspect_ratio == "16:9"
    assert proj.user_id == USER_A_ID
    assert proj.id in mock_db.projects

    # 2. Retrieve project
    fetched = repo_a.get_project(proj.id, USER_A_ID)
    assert fetched is not None
    assert fetched.id == proj.id
    assert fetched.name == "Cinematic Teaser"
    assert fetched.created_at.tzinfo is not None

    # Verify headers sent
    assert len(mock_db.recorded_requests) >= 2
    for req in mock_db.recorded_requests:
        assert req.headers["apikey"] == MOCK_PUB_KEY
        assert req.headers["Authorization"] == f"Bearer {USER_A_TOKEN}"


def test_project_listing(repo_a: SupabaseRepository) -> None:
    # Initially empty
    assert repo_a.list_projects(USER_A_ID) == []

    # Create 2 projects
    p1 = repo_a.create_project(user_id=USER_A_ID, name="Cut 1")
    p2 = repo_a.create_project(user_id=USER_A_ID, name="Cut 2")

    projects = repo_a.list_projects(USER_A_ID)
    assert len(projects) == 2
    ids = [p.id for p in projects]
    assert p1.id in ids
    assert p2.id in ids


def test_project_updates(repo_a: SupabaseRepository) -> None:
    proj = repo_a.create_project(user_id=USER_A_ID, name="Old Name", aspect_ratio="9:16")

    # Update name and aspect ratio
    updated = repo_a.update_project(
        project_id=proj.id,
        user_id=USER_A_ID,
        name="New Name",
        aspect_ratio="1:1",
    )
    assert updated is not None
    assert updated.id == proj.id
    assert updated.name == "New Name"
    assert updated.aspect_ratio == "1:1"

    # Verify persisted in subsequent get
    fetched = repo_a.get_project(proj.id, USER_A_ID)
    assert fetched is not None
    assert fetched.name == "New Name"


def test_project_get_or_create_default(repo_a: SupabaseRepository) -> None:
    # First call creates default project
    default_p = repo_a.get_or_create_default_project(USER_A_ID)
    assert default_p is not None
    assert default_p.name == "Untitled Cut"

    # Subsequent call returns the existing project
    second = repo_a.get_or_create_default_project(USER_A_ID)
    assert second.id == default_p.id


# =============================================================================
# 2. Media Tests
# =============================================================================


def test_media_creation_and_retrieval(
    repo_a: SupabaseRepository, mock_db: PostgrestMockDatabase
) -> None:
    proj = repo_a.create_project(user_id=USER_A_ID, name="Reel")
    custom_media_id = str(uuid.uuid4())
    s3_key = f"users/{USER_A_ID}/projects/{proj.id}/media/{custom_media_id}/token.mp4"

    media = repo_a.create_media(
        project_id=proj.id,
        user_id=USER_A_ID,
        original_filename="raw_clip.mp4",
        s3_object_key=s3_key,
        content_type="video/mp4",
        declared_size_bytes=1048576,
        retention_days=7,
        media_id=custom_media_id,
    )
    assert isinstance(media, MediaRecord)
    assert media.id == custom_media_id
    assert media.project_id == proj.id
    assert media.user_id == USER_A_ID
    assert media.s3_object_key == s3_key
    assert media.status == "pending"

    # Retrieve media
    fetched = repo_a.get_media(custom_media_id, USER_A_ID)
    assert fetched is not None
    assert fetched.id == custom_media_id
    assert fetched.original_filename == "raw_clip.mp4"


def test_media_listing_and_status_updates(repo_a: SupabaseRepository) -> None:
    proj = repo_a.create_project(user_id=USER_A_ID)
    m1 = repo_a.create_media(
        project_id=proj.id,
        user_id=USER_A_ID,
        original_filename="clip1.mp4",
        s3_object_key="key1.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )
    m2 = repo_a.create_media(
        project_id=proj.id,
        user_id=USER_A_ID,
        original_filename="clip2.mp4",
        s3_object_key="key2.mp4",
        content_type="video/mp4",
        declared_size_bytes=2000,
    )

    media_list = repo_a.list_media(proj.id, USER_A_ID)
    assert len(media_list) == 2
    assert {m.id for m in media_list} == {m1.id, m2.id}

    # Status update
    updated = repo_a.update_media_status(
        media_id=m1.id,
        user_id=USER_A_ID,
        status="verified",
        verified_size_bytes=1024,
        duration_seconds=14.5,
    )
    assert updated is not None
    assert updated.status == "verified"
    assert updated.verified_size_bytes == 1024
    assert updated.duration_seconds == 14.5


def test_media_deletion(repo_a: SupabaseRepository) -> None:
    proj = repo_a.create_project(user_id=USER_A_ID)
    media = repo_a.create_media(
        project_id=proj.id,
        user_id=USER_A_ID,
        original_filename="to_delete.mp4",
        s3_object_key="key.mp4",
        content_type="video/mp4",
        declared_size_bytes=500,
    )

    # First delete succeeds
    assert repo_a.delete_media(media.id, USER_A_ID) is True

    # Record is gone
    assert repo_a.get_media(media.id, USER_A_ID) is None

    # Second delete returns False (not found)
    assert repo_a.delete_media(media.id, USER_A_ID) is False


# =============================================================================
# 3. Security, Scoping & RLS Tests
# =============================================================================


def test_correct_api_key_and_user_jwt_headers(mock_db: PostgrestMockDatabase) -> None:
    client = httpx.Client(transport=httpx.MockTransport(mock_db.handle_request))
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client,
    )

    repo.create_project(user_id=USER_A_ID, name="Header Test")

    # Verify last request
    last_req = mock_db.recorded_requests[-1]
    assert last_req.headers["apikey"] == MOCK_PUB_KEY
    assert last_req.headers["Authorization"] == f"Bearer {USER_A_TOKEN}"
    # Verify SERVICE ROLE KEY is NEVER sent
    assert "service_role" not in last_req.headers.get("apikey", "").lower()
    assert "service_role" not in last_req.headers.get("Authorization", "").lower()


def test_correct_user_id_scoping_in_queries(
    repo_a: SupabaseRepository, mock_db: PostgrestMockDatabase
) -> None:
    proj = repo_a.create_project(user_id=USER_A_ID, name="Scoped Project")
    repo_a.get_project(proj.id, USER_A_ID)

    # Inspect the GET request query parameters
    get_req = mock_db.recorded_requests[-1]
    query = parse_qs(urlparse(str(get_req.url)).query)
    assert query["user_id"][0] == f"eq.{USER_A_ID}"
    assert query["id"][0] == f"eq.{proj.id}"


def test_cross_user_isolation(mock_db: PostgrestMockDatabase, client_a: httpx.Client) -> None:
    # User A creates a project
    repo_a = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client_a,
    )
    proj_a = repo_a.create_project(user_id=USER_A_ID, name="User A Secret Project")

    # User B setup with their own separate token and client
    client_b = httpx.Client(transport=httpx.MockTransport(mock_db.handle_request))
    repo_b = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_B_ID,
        access_token=USER_B_TOKEN,
        client=client_b,
    )

    # 1. User B cannot get User A's project
    assert repo_b.get_project(proj_a.id, USER_B_ID) is None

    # 2. Passing User A's user_id to repo_b returns None (boundary enforcement)
    assert repo_b.get_project(proj_a.id, USER_A_ID) is None

    # 3. User B's list does not show User A's project
    assert repo_b.list_projects(USER_B_ID) == []

    # 4. User B cannot update or delete User A's project
    assert (
        repo_b.update_project(project_id=proj_a.id, user_id=USER_B_ID, name="Hacked Name") is None
    )

    # 5. User A's project remains untouched
    proj = repo_a.get_project(proj_a.id, USER_A_ID)
    assert proj is not None
    assert proj.name == "User A Secret Project"


def test_cannot_create_entity_for_different_user(repo_a: SupabaseRepository) -> None:
    # Attempt to create project for User B using User A's repo
    with pytest.raises(DatabasePermissionError):
        repo_a.create_project(user_id=USER_B_ID, name="Impersonated Project")

    # Attempt to create media for User B using User A's repo
    with pytest.raises(DatabasePermissionError):
        repo_a.create_media(
            project_id=str(uuid.uuid4()),
            user_id=USER_B_ID,
            original_filename="clip.mp4",
            s3_object_key="key.mp4",
            content_type="video/mp4",
            declared_size_bytes=100,
        )


# =============================================================================
# 4. Error Handling & Timeout Tests
# =============================================================================


def test_http_network_timeout_handling() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out after 10s")

    client = httpx.Client(transport=httpx.MockTransport(timeout_handler))
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client,
    )

    with pytest.raises(DatabaseConnectionError) as exc:
        repo.list_projects(USER_A_ID)
    assert "timed out" in str(exc.value).lower()


def test_http_network_connection_error_handling() -> None:
    def connect_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to resolve host")

    client = httpx.Client(transport=httpx.MockTransport(connect_error_handler))
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client,
    )

    with pytest.raises(DatabaseConnectionError) as exc:
        repo.create_project(user_id=USER_A_ID)
    assert "connection error" in str(exc.value).lower()


def test_http_401_403_permission_errors() -> None:
    def forbidden_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "new row violates row-level security policy"})

    client = httpx.Client(transport=httpx.MockTransport(forbidden_handler))
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client,
    )

    with pytest.raises(DatabasePermissionError) as exc:
        repo.create_project(user_id=USER_A_ID)
    assert "access denied" in str(exc.value).lower()


def test_http_500_database_error() -> None:
    def internal_error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "Internal PostgreSQL error"})

    client = httpx.Client(transport=httpx.MockTransport(internal_error_handler))
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
        client=client,
    )

    with pytest.raises(DatabaseError) as exc:
        repo.list_projects(USER_A_ID)
    assert "database error" in str(exc.value).lower()


# =============================================================================
# 5. Configuration & Fail-Closed Tests
# =============================================================================


def test_missing_supabase_repo_configuration_raises() -> None:
    with pytest.raises(ValueError) as exc:
        SupabaseRepository(
            supabase_url="",
            publishable_key=MOCK_PUB_KEY,
            user_id=USER_A_ID,
            access_token=USER_A_TOKEN,
        )
    assert "supabase_url" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        SupabaseRepository(
            supabase_url=MOCK_SUPABASE_URL,
            publishable_key="",
            user_id=USER_A_ID,
            access_token=USER_A_TOKEN,
        )
    assert "publishable_key" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        SupabaseRepository(
            supabase_url=MOCK_SUPABASE_URL,
            publishable_key=MOCK_PUB_KEY,
            user_id="invalid-not-a-uuid",
            access_token=USER_A_TOKEN,
        )
    assert "uuid" in str(exc.value).lower()


def test_get_repository_in_memory_default() -> None:
    settings = Settings(DATABASE_PROVIDER="memory")
    repo_gen = get_repository(user=None, settings=settings)
    repo = next(repo_gen)
    assert isinstance(repo, InMemoryRepository)


def test_get_repository_supabase_fails_closed_without_silent_fallback() -> None:
    # When DATABASE_PROVIDER=supabase but user is missing, it must FAIL (never fall back to memory)
    settings = Settings(
        DATABASE_PROVIDER="supabase",
        SUPABASE_URL=MOCK_SUPABASE_URL,
        SUPABASE_PUBLISHABLE_KEY=MOCK_PUB_KEY,
    )

    # 1. Unauthenticated user
    repo_gen = get_repository(user=None, settings=settings)
    with pytest.raises(HTTPException) as exc:
        next(repo_gen)
    assert exc.value.status_code == 401
    assert "authentication required" in exc.value.detail.lower()

    # 2. User without access token
    user_no_token = AuthenticatedUser(user_id=USER_A_ID, access_token="")
    repo_gen2 = get_repository(user=user_no_token, settings=settings)
    with pytest.raises(HTTPException) as exc:
        next(repo_gen2)
    assert exc.value.status_code == 401
    assert "valid access token required" in exc.value.detail.lower()

    # 3. Authenticated user gets request-scoped SupabaseRepository
    user_valid = AuthenticatedUser(user_id=USER_A_ID, access_token=USER_A_TOKEN)
    repo_gen3 = get_repository(user=user_valid, settings=settings)
    repo = next(repo_gen3)
    assert isinstance(repo, SupabaseRepository)
    assert repo.user_id == USER_A_ID
    assert repo.access_token == USER_A_TOKEN

    # Verify resource cleanup closes client
    try:
        next(repo_gen3)
    except StopIteration:
        pass


def test_context_manager_resource_cleanup() -> None:
    repo = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_A_ID,
        access_token=USER_A_TOKEN,
    )
    with repo:
        assert not repo._client.is_closed
    assert repo._client.is_closed


def test_supabase_repo_create_and_get_analysis(repo_a: SupabaseRepository) -> None:
    """Verify SupabaseRepository creates and retrieves analyses with intelligence and blueprint."""
    project = repo_a.create_project(user_id=USER_A_ID, name="Analysis Project")
    media = repo_a.create_media(
        project_id=project.id,
        user_id=USER_A_ID,
        original_filename="sample.mp4",
        s3_object_key=f"users/{USER_A_ID}/{project.id}/m1/sample.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )

    blueprint = {"title": "Cut Title", "timeline": []}
    source_id = {"classification": "anime", "title": "Demon Slayer", "confidence": "high"}
    audio_id = {"track_title": "Gurenge", "artist": "LiSA", "match_status": "model_inference"}
    usage = {"provider": "baseten", "model": "meta-models/muse-spark-open-1026", "latency_ms": 2500}

    analysis = repo_a.create_analysis(
        project_id=project.id,
        media_id=media.id,
        user_id=USER_A_ID,
        provider="baseten",
        model="meta-models/muse-spark-open-1026",
        blueprint=blueprint,
        source_identification=source_id,
        audio_intelligence=audio_id,
        usage_metadata=usage,
    )

    assert analysis.id is not None
    assert analysis.project_id == project.id
    assert analysis.media_id == media.id
    assert analysis.provider == "baseten"
    assert analysis.source_identification == source_id
    assert analysis.audio_intelligence == audio_id
    assert analysis.usage_metadata == usage

    fetched = repo_a.get_analysis(analysis.id, user_id=USER_A_ID)
    assert fetched is not None
    assert fetched.id == analysis.id
    assert fetched.blueprint == blueprint


def test_supabase_repo_get_latest_analysis_and_update_feedback(
    repo_a: SupabaseRepository,
    mock_db: PostgrestMockDatabase,
) -> None:
    """Verify retrieving latest analysis, updating feedback, and multi-user isolation."""
    project = repo_a.create_project(user_id=USER_A_ID)
    media = repo_a.create_media(
        project_id=project.id,
        user_id=USER_A_ID,
        original_filename="clip.mp4",
        s3_object_key=f"users/{USER_A_ID}/{project.id}/m1/clip.mp4",
        content_type="video/mp4",
        declared_size_bytes=1000,
    )

    client_b = httpx.Client(transport=httpx.MockTransport(mock_db.handle_request))
    repo_b = SupabaseRepository(
        supabase_url=MOCK_SUPABASE_URL,
        publishable_key=MOCK_PUB_KEY,
        user_id=USER_B_ID,
        access_token=USER_B_TOKEN,
        client=client_b,
    )

    # Initial analysis
    a1 = repo_a.create_analysis(
        project_id=project.id,
        media_id=media.id,
        user_id=USER_A_ID,
        provider="mock",
        model="mock-v1",
        blueprint={"title": "Blueprint 1"},
    )

    latest = repo_a.get_latest_analysis_for_media(media.id, user_id=USER_A_ID)
    assert latest is not None
    assert latest.id == a1.id

    # User A updates feedback
    feedback = {"is_source_correct": True, "corrected_title": None, "notes": "Spot on."}
    updated = repo_a.update_analysis_feedback(a1.id, user_id=USER_A_ID, feedback=feedback)
    assert updated is not None
    assert updated.user_feedback == feedback

    # User B cannot access or update User A's analysis
    assert repo_b.get_analysis(a1.id, user_id=USER_B_ID) is None
    assert repo_b.get_latest_analysis_for_media(media.id, user_id=USER_B_ID) is None
    assert (
        repo_b.update_analysis_feedback(a1.id, user_id=USER_B_ID, feedback={"notes": "Hacked"})
        is None
    )
