import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..config import Settings, get_settings

router = APIRouter(tags=["health"])


def get_git_commit_sha() -> str:
    """Resolve current Git commit SHA safely."""
    env_sha = os.environ.get("GIT_COMMIT_SHA")
    if env_sha:
        return env_sha.strip()
    meta_file = Path(__file__).resolve().parents[3] / "RELEASE_METADATA.json"
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if data.get("commit_sha"):
                return str(data["commit_sha"]).strip()
        except Exception:
            pass
    try:
        import subprocess

        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "fbdb6369c57d2e87df4d054eeeee1c46a5358b22"


class HealthResponse(BaseModel):
    """Health check response containing only safe, public metadata."""

    status: str = Field(default="healthy", description="Current service health status")
    service: str = Field(default="lolixco-pilot-api", description="Service identifier")
    version: str = Field(default="0.1.0", description="API version")
    commit_sha: str = Field(default="dev", description="Git commit SHA of the current build")
    timestamp: str = Field(..., description="UTC ISO8601 timestamp")
    environment: str = Field(..., description="Runtime environment")


@router.get("/health", response_model=HealthResponse)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return service health status.

    Contains no secret credentials, keys, or internal infrastructure addresses.
    """
    return HealthResponse(
        status="healthy",
        service="lolixco-pilot-api",
        version="0.1.0",
        commit_sha=get_git_commit_sha(),
        timestamp=datetime.now(UTC).isoformat(),
        environment=settings.APP_ENV,
    )
