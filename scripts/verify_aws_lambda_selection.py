#!/usr/bin/env python3
"""Verification script for AWS Lambda Media Processing service selection and fallback."""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.services.aws_lambda_service import AWSLambdaMediaProcessingService
from app.services.media_processing import (
    LocalMediaProcessingService,
    get_media_processing_service,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_lambda_selection")


async def main() -> None:
    logger.info("=== 1. Testing Dependency Injection Selection ===")
    settings = Settings(
        APP_ENV="development",
        USE_AWS_LAMBDA_MEDIA_WORKER=True,
        AWS_LAMBDA_MEDIA_FUNCTION="lolixcopilot-media-processor",
        AWS_REGION="ap-south-1",
        AWS_S3_BUCKET="lolixcopilot-media-247673029886-ap-south-1",
    )

    service = get_media_processing_service(settings=settings)
    assert isinstance(
        service, AWSLambdaMediaProcessingService
    ), f"Expected AWSLambdaMediaProcessingService, got {type(service)}"
    logger.info("PASS: get_media_processing_service returned AWSLambdaMediaProcessingService")

    logger.info("=== 2. Testing Live Lambda Probe Invocation ===")
    probe_res = await service.probe_media(
        "users/demo-eval/projects/gojo-hollow-purple/media/gojo_hollow_purple_edit.mp4"
    )
    assert probe_res.duration_seconds == 68.08, f"Unexpected duration: {probe_res.duration_seconds}"
    assert probe_res.width == 2560
    assert probe_res.height == 1440
    assert probe_res.codec_name == "av1"
    logger.info(
        "PASS: Live Lambda probe succeeded -> %ss, %sx%s, %s",
        probe_res.duration_seconds,
        probe_res.width,
        probe_res.height,
        probe_res.codec_name,
    )

    logger.info("=== 3. Testing Local Fallback on Lambda Error ===")
    failing_service = AWSLambdaMediaProcessingService(
        function_name="non-existent-lambda-function-xyz",
        region_name="ap-south-1",
        bucket_name="lolixcopilot-media-247673029886-ap-south-1",
        fallback_service=LocalMediaProcessingService(),
    )

    # Calling probe on a non-existent lambda should log a warning and fall back to local service
    fallback_res = await failing_service.probe_media("/tmp/gojo_30s_cinematic_cut.mp4")
    assert fallback_res.duration_seconds is not None
    assert fallback_res.codec_name == "h264"
    logger.info(
        "PASS: Graceful fallback succeeded -> probed local cut: %ss, %s",
        fallback_res.duration_seconds,
        fallback_res.codec_name,
    )

    logger.info("=== ALL SELECTION AND FALLBACK CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
