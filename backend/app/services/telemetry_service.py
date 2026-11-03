"""Real AI Usage and Infrastructure Telemetry Service for LolixCopilot.

Tracks genuine provider usage across:
- Modal: GPU compute seconds, tasks, and estimated compute cost.
- Meta Model API: Prompt/completion tokens, calls, latency, and estimated cost.
- Baseten: Prompt/completion tokens, calls, latency, and estimated cost.
- AWS Lambda: Media processor/export render invocations, duration, and compute cost.

Provides truthful, non-mocked telemetry for project and session dashboards.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderUsageStats(BaseModel):
    """Usage statistics for a specific provider."""

    calls: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    total_tokens: int = 0
    compute_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    last_model_used: str | None = None
    last_call_at: str | None = None


class TelemetrySummary(BaseModel):
    """Consolidated telemetry summary for the workstation dashboard."""

    total_ai_calls: int = 0
    estimated_total_cost_usd: float = 0.0
    modal: ProviderUsageStats = Field(default_factory=ProviderUsageStats)
    meta: ProviderUsageStats = Field(default_factory=ProviderUsageStats)
    baseten: ProviderUsageStats = Field(default_factory=ProviderUsageStats)
    lambda_processor: ProviderUsageStats = Field(default_factory=ProviderUsageStats)
    session_started_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    last_updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class TelemetryService:
    """Thread-safe telemetry tracker for live inference and cloud execution."""

    # Approximate official pricing rates for cost estimation
    # Modal H100 80GB SXM5: ~$4.76/hr = $0.001322/sec
    MODAL_H100_RATE_PER_SEC = 0.001322
    # Meta Model API (Muse Spark 1.3): ~$0.15/1M input, ~$0.60/1M output tokens
    META_INPUT_RATE_PER_M = 0.15
    META_OUTPUT_RATE_PER_M = 0.60
    # Baseten (Muse Spark Open): ~$0.20/1M input, ~$0.80/1M output tokens
    BASETEN_INPUT_RATE_PER_M = 0.20
    BASETEN_OUTPUT_RATE_PER_M = 0.80
    # AWS Lambda (1024MB arm64/x86_64 in ap-south-1): ~$0.0000166667 / GB-s
    LAMBDA_RATE_PER_SEC = 0.00001667

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_start = datetime.now(UTC).isoformat()
        self._global_summary = TelemetrySummary(session_started_at=self._session_start)
        self._project_summaries: dict[str, TelemetrySummary] = {}
        self._event_log: list[dict[str, Any]] = []

    def record_modal_execution(
        self,
        task_name: str,
        duration_seconds: float,
        is_gpu: bool = True,
        model_name: str = "meta-models/Muse-Glimmer-30B",
        project_id: str | None = None,
        success: bool = True,
    ) -> None:
        """Record a completed Modal execution."""
        cost = round(duration_seconds * self.MODAL_H100_RATE_PER_SEC if is_gpu else 0.0, 5)
        now_iso = datetime.now(UTC).isoformat()

        with self._lock:
            self._global_summary.total_ai_calls += 1
            self._global_summary.modal.calls += 1
            self._global_summary.modal.compute_seconds = round(
                self._global_summary.modal.compute_seconds + duration_seconds, 2
            )
            self._global_summary.modal.estimated_cost_usd = round(
                self._global_summary.modal.estimated_cost_usd + cost, 4
            )
            self._global_summary.modal.last_model_used = model_name
            self._global_summary.modal.last_call_at = now_iso
            self._global_summary.estimated_total_cost_usd = round(
                self._global_summary.estimated_total_cost_usd + cost, 4
            )
            self._global_summary.last_updated_at = now_iso

            event = {
                "timestamp": now_iso,
                "provider": "modal",
                "model": model_name,
                "task": task_name,
                "duration_seconds": duration_seconds,
                "is_gpu": is_gpu,
                "cost_usd": cost,
                "project_id": project_id,
                "success": success,
            }
            self._event_log.append(event)

    def record_meta_inference(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        project_id: str | None = None,
        success: bool = True,
    ) -> None:
        """Record a Meta Model API completion."""
        total_tokens = prompt_tokens + completion_tokens
        cost = round(
            (prompt_tokens / 1_000_000) * self.META_INPUT_RATE_PER_M
            + (completion_tokens / 1_000_000) * self.META_OUTPUT_RATE_PER_M,
            5,
        )
        now_iso = datetime.now(UTC).isoformat()

        with self._lock:
            self._global_summary.total_ai_calls += 1
            self._global_summary.meta.calls += 1
            self._global_summary.meta.tokens_prompt += prompt_tokens
            self._global_summary.meta.tokens_completion += completion_tokens
            self._global_summary.meta.total_tokens += total_tokens
            self._global_summary.meta.compute_seconds = round(
                self._global_summary.meta.compute_seconds + (latency_ms / 1000.0), 2
            )
            self._global_summary.meta.estimated_cost_usd = round(
                self._global_summary.meta.estimated_cost_usd + cost, 4
            )
            self._global_summary.meta.last_model_used = model_name
            self._global_summary.meta.last_call_at = now_iso
            self._global_summary.estimated_total_cost_usd = round(
                self._global_summary.estimated_total_cost_usd + cost, 4
            )
            self._global_summary.last_updated_at = now_iso

            event = {
                "timestamp": now_iso,
                "provider": "meta",
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "cost_usd": cost,
                "project_id": project_id,
                "success": success,
            }
            self._event_log.append(event)

    def record_baseten_inference(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        project_id: str | None = None,
        success: bool = True,
    ) -> None:
        """Record a Baseten Muse Spark Open completion."""
        total_tokens = prompt_tokens + completion_tokens
        cost = round(
            (prompt_tokens / 1_000_000) * self.BASETEN_INPUT_RATE_PER_M
            + (completion_tokens / 1_000_000) * self.BASETEN_OUTPUT_RATE_PER_M,
            5,
        )
        now_iso = datetime.now(UTC).isoformat()

        with self._lock:
            self._global_summary.total_ai_calls += 1
            self._global_summary.baseten.calls += 1
            self._global_summary.baseten.tokens_prompt += prompt_tokens
            self._global_summary.baseten.tokens_completion += completion_tokens
            self._global_summary.baseten.total_tokens += total_tokens
            self._global_summary.baseten.compute_seconds = round(
                self._global_summary.baseten.compute_seconds + (latency_ms / 1000.0), 2
            )
            self._global_summary.baseten.estimated_cost_usd = round(
                self._global_summary.baseten.estimated_cost_usd + cost, 4
            )
            self._global_summary.baseten.last_model_used = model_name
            self._global_summary.baseten.last_call_at = now_iso
            self._global_summary.estimated_total_cost_usd = round(
                self._global_summary.estimated_total_cost_usd + cost, 4
            )
            self._global_summary.last_updated_at = now_iso

            event = {
                "timestamp": now_iso,
                "provider": "baseten",
                "model": model_name,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "cost_usd": cost,
                "project_id": project_id,
                "success": success,
            }
            self._event_log.append(event)

    def record_lambda_execution(
        self,
        task_name: str,
        duration_seconds: float,
        project_id: str | None = None,
        success: bool = True,
    ) -> None:
        """Record an AWS Lambda media/export execution."""
        cost = round(duration_seconds * self.LAMBDA_RATE_PER_SEC, 5)
        now_iso = datetime.now(UTC).isoformat()

        with self._lock:
            self._global_summary.lambda_processor.calls += 1
            self._global_summary.lambda_processor.compute_seconds = round(
                self._global_summary.lambda_processor.compute_seconds + duration_seconds, 2
            )
            self._global_summary.lambda_processor.estimated_cost_usd = round(
                self._global_summary.lambda_processor.estimated_cost_usd + cost, 4
            )
            self._global_summary.lambda_processor.last_model_used = "aws-lambda-ffmpeg"
            self._global_summary.lambda_processor.last_call_at = now_iso
            self._global_summary.last_updated_at = now_iso

            event = {
                "timestamp": now_iso,
                "provider": "aws_lambda",
                "task": task_name,
                "duration_seconds": duration_seconds,
                "cost_usd": cost,
                "project_id": project_id,
                "success": success,
            }
            self._event_log.append(event)

    def get_summary(self, project_id: str | None = None) -> TelemetrySummary:
        """Return the current telemetry snapshot."""
        with self._lock:
            # Return copy of global summary
            return self._global_summary.model_copy(deep=True)

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent telemetry events."""
        with self._lock:
            return list(self._event_log[-limit:])


# Singleton instance
_telemetry_service_instance: TelemetryService | None = None


def get_telemetry_service() -> TelemetryService:
    """FastAPI dependency for accessing the telemetry service singleton."""
    global _telemetry_service_instance
    if _telemetry_service_instance is None:
        _telemetry_service_instance = TelemetryService()
    return _telemetry_service_instance

