"""Telemetry API routes for LolixCopilot."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from app.services.telemetry_service import (
    TelemetryService,
    TelemetrySummary,
    get_telemetry_service,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/usage", response_model=TelemetrySummary)
async def get_usage_telemetry(
    telemetry: TelemetryService = Depends(get_telemetry_service),
) -> TelemetrySummary:
    """Return live, genuine AI and cloud resource usage metrics."""
    return telemetry.get_summary()


@router.get("/events")
async def get_telemetry_events(
    limit: int = 50,
    telemetry: TelemetryService = Depends(get_telemetry_service),
) -> list[dict[str, Any]]:
    """Return recent telemetry execution events."""
    return telemetry.get_recent_events(limit=limit)

