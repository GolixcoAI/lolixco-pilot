"""Modal client adapter service for LolixCopilot media processing.

Connects the FastAPI application to the containerized Modal media worker:
- Asynchronously invokes Modal remote functions for probing and audio extraction.
- Preserves offline/local fallback when Modal workers are unconfigured or unreachable.
- Adheres to BaseMediaProcessingService contract for zero-downtime provider substitution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.media_processing import (
    AudioBeatsResult,
    AudioExtractionResult,
    BaseMediaProcessingService,
    LocalMediaProcessingService,
    MediaProbeResult,
    RenderCutResult,
)

logger = logging.getLogger(__name__)


class ModalMediaProcessingService(BaseMediaProcessingService):
    """Media processing adapter communicating with Modal CPU workers."""

    def __init__(
        self,
        app_name: str = "lolixcopilot-media-worker",
        fallback_service: BaseMediaProcessingService | None = None,
        modal_function_lookup: Any = None,
    ) -> None:
        self.app_name = app_name
        self.fallback = fallback_service or LocalMediaProcessingService()
        self._function_lookup = modal_function_lookup

    def _get_modal_function(self, function_name: str) -> Any | None:
        """Resolve a deployed Modal function by name, returning None if lookup fails."""
        if self._function_lookup is not None:
            return self._function_lookup(self.app_name, function_name)

        try:
            import modal

            return modal.Function.from_name(self.app_name, function_name)
        except Exception as exc:
            logger.debug("Modal function lookup failed for '%s': %s", function_name, exc)
            return None

    async def probe_media(self, file_path_or_url: str) -> MediaProbeResult:
        """Probe media using Modal remote worker with local fallback."""
        probe_fn = self._get_modal_function("probe_video_metadata")
        if probe_fn is not None:
            try:
                # Modal async invocation via .remote.aio()
                loop = asyncio.get_running_loop()
                data: dict[str, Any]
                if hasattr(probe_fn, "remote") and hasattr(probe_fn.remote, "aio"):
                    data = await probe_fn.remote.aio(file_path_or_url)
                else:
                    data = await loop.run_in_executor(None, probe_fn.remote, file_path_or_url)

                return MediaProbeResult(
                    duration_seconds=data.get("duration_seconds"),
                    width=data.get("width"),
                    height=data.get("height"),
                    fps=data.get("fps"),
                    codec_name=data.get("codec_name"),
                    has_audio=bool(data.get("has_audio")),
                    audio_codec=data.get("audio_codec"),
                    sample_rate=data.get("sample_rate"),
                    channels=data.get("channels"),
                )
            except Exception as exc:
                logger.warning(
                    "Modal probe failed, falling back to local processing: %s",
                    exc,
                )

        return await self.fallback.probe_media(file_path_or_url)

    async def extract_audio(
        self,
        video_path: str,
        output_audio_path: str,
        max_duration_seconds: float = 60.0,
    ) -> AudioExtractionResult:
        """Extract audio using Modal worker with local fallback."""
        extract_fn = self._get_modal_function("extract_audio_track")
        if extract_fn is not None:
            try:
                loop = asyncio.get_running_loop()
                res: dict[str, Any]
                if hasattr(extract_fn, "remote") and hasattr(extract_fn.remote, "aio"):
                    res = await extract_fn.remote.aio(
                        video_path,
                        upload_presigned_url=None,
                        max_duration_seconds=max_duration_seconds,
                        output_format="wav",
                    )
                else:
                    res = await loop.run_in_executor(
                        None,
                        extract_fn.remote,
                        video_path,
                        None,
                        max_duration_seconds,
                        "wav",
                    )

                if res.get("success"):
                    return AudioExtractionResult(
                        success=True,
                        output_path=output_audio_path,
                        duration_seconds=res.get("max_duration_seconds"),
                    )
                return AudioExtractionResult(
                    success=False,
                    error_message=res.get("error_message", "Modal extraction reported failure"),
                )
            except Exception as exc:
                logger.warning(
                    "Modal audio extraction failed, falling back to local: %s",
                    exc,
                )

        return await self.fallback.extract_audio(
            video_path=video_path,
            output_audio_path=output_audio_path,
            max_duration_seconds=max_duration_seconds,
        )

    async def extract_timestamped_frames(
        self,
        presigned_video_url: str,
        timestamps: list[float],
        upload_urls: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Extract timestamped frames using Modal remote worker."""
        frames_fn = self._get_modal_function("extract_timestamped_frames")
        if frames_fn is not None:
            try:
                loop = asyncio.get_running_loop()
                if hasattr(frames_fn, "remote") and hasattr(frames_fn.remote, "aio"):
                    return await frames_fn.remote.aio(  # type: ignore[no-any-return]
                        presigned_video_url, timestamps, upload_urls
                    )
                return await loop.run_in_executor(  # type: ignore[no-any-return]
                    None,
                    frames_fn.remote,
                    presigned_video_url,
                    timestamps,
                    upload_urls,
                )
            except Exception as exc:
                logger.warning("Modal frame extraction failed: %s", exc)

        return []

    async def generate_h264_proxy(
        self,
        video_path: str,
        output_proxy_path: str,
        max_width: int = 1280,
    ) -> bool:
        """Generate compatible H.264 preview proxy via local fallback."""
        return await self.fallback.generate_h264_proxy(
            video_path=video_path,
            output_proxy_path=output_proxy_path,
            max_width=max_width,
        )

    async def render_edit_cut(
        self,
        video_path: str,
        segments: list[dict[str, Any]],
        output_cut_path: str,
        target_resolution: str = "1080p",
        include_audio: bool = True,
    ) -> RenderCutResult:
        """Render multi-segment edit cut via local fallback."""
        return await self.fallback.render_edit_cut(
            video_path=video_path,
            segments=segments,
            output_cut_path=output_cut_path,
            target_resolution=target_resolution,
            include_audio=include_audio,
        )

    async def analyze_audio_beats(
        self,
        audio_or_video_path: str,
    ) -> AudioBeatsResult:
        """Analyze audio beats and energy profile via local fallback."""
        return await self.fallback.analyze_audio_beats(audio_or_video_path=audio_or_video_path)
