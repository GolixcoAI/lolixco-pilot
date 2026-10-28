from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response containing only safe, public metadata."""

    status: str = Field(default="healthy", description="Current service health status")
    service: str = Field(default="lolixco-pilot-api", description="Service identifier")
    version: str = Field(default="0.1.0", description="API version")
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
        timestamp=datetime.now(UTC).isoformat(),
        environment=settings.APP_ENV,
    )
