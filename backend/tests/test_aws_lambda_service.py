"""Unit tests for AWSLambdaMediaProcessingService with mocked boto3 lambda client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.aws_lambda_service import AWSLambdaMediaProcessingService
from app.services.media_processing import (
    BaseMediaProcessingService,
    get_media_processing_service,
)


class MockLambdaPayload:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode("utf-8")

    def read(self) -> bytes:
        return self._data


@pytest.fixture
def mock_lambda_client():
    client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_probe_media_lambda_success(mock_lambda_client):
    response_payload = {
        "statusCode": 200,
        "body": {
            "duration_seconds": 68.08,
            "width": 2560,
            "height": 1440,
            "fps": 30.0,
            "video_codec": "av1",
            "audio_codec": "aac",
        },
    }
    mock_lambda_client.invoke.return_value = {"Payload": MockLambdaPayload(response_payload)}

    service = AWSLambdaMediaProcessingService(
        function_name="test-function",
        lambda_client=mock_lambda_client,
    )

    result = await service.probe_media("users/demo/test.mp4")

    assert result.duration_seconds == 68.08
    assert result.width == 2560
    assert result.height == 1440
    assert result.codec_name == "av1"
    assert result.has_audio is True
    assert result.audio_codec == "aac"


@pytest.mark.asyncio
async def test_probe_media_lambda_failure_fallback(mock_lambda_client):
    mock_lambda_client.invoke.side_effect = RuntimeError("AWS Connection Timeout")

    mock_fallback = MagicMock(spec=BaseMediaProcessingService)
    service = AWSLambdaMediaProcessingService(
        function_name="test-function",
        fallback_service=mock_fallback,
        lambda_client=mock_lambda_client,
    )

    await service.probe_media("users/demo/test.mp4")
    mock_fallback.probe_media.assert_called_once_with("users/demo/test.mp4")


@pytest.mark.asyncio
async def test_generate_h264_proxy_success(mock_lambda_client):
    response_payload = {
        "statusCode": 200,
        "body": {
            "status": "created",
            "target_key": "proxies/test_h264.mp4",
            "size_bytes": 1024 * 1024,
        },
    }
    mock_lambda_client.invoke.return_value = {"Payload": MockLambdaPayload(response_payload)}

    service = AWSLambdaMediaProcessingService(
        function_name="test-function",
        lambda_client=mock_lambda_client,
    )

    success = await service.generate_h264_proxy(
        video_path="users/demo/test.mp4",
        output_proxy_path="/tmp/proxy.mp4",
    )
    assert success is True


@pytest.mark.asyncio
async def test_render_edit_cut_success(mock_lambda_client):
    response_payload = {
        "statusCode": 200,
        "body": {
            "status": "success",
            "target_key": "exports/test_cut.mp4",
            "size_bytes": 15000000,
        },
    }
    mock_lambda_client.invoke.return_value = {"Payload": MockLambdaPayload(response_payload)}

    service = AWSLambdaMediaProcessingService(
        function_name="test-function",
        lambda_client=mock_lambda_client,
    )

    segments = [
        {"start_seconds": 12.0, "end_seconds": 18.0},
        {"start_seconds": 22.0, "end_seconds": 30.0},
    ]
    result = await service.render_edit_cut(
        video_path="users/demo/test.mp4",
        segments=segments,
        output_cut_path="/tmp/cut.mp4",
    )
    assert result.success is True
    assert result.duration_seconds == 14.0
    assert result.segment_count == 2
    assert result.file_size_bytes == 15000000


@pytest.mark.asyncio
async def test_analyze_audio_beats_success(mock_lambda_client):
    response_payload = {
        "statusCode": 200,
        "body": {
            "mean_volume_db": -21.0,
            "max_volume_db": -0.4,
            "estimated_tempo_bpm": 128,
            "beat_timestamps": [12.8, 19.6, 28.0],
        },
    }
    mock_lambda_client.invoke.return_value = {"Payload": MockLambdaPayload(response_payload)}

    service = AWSLambdaMediaProcessingService(
        function_name="test-function",
        lambda_client=mock_lambda_client,
    )

    result = await service.analyze_audio_beats("users/demo/test.mp4")
    assert result.success is True
    assert result.estimated_bpm == 128.0
    assert result.peak_dbfs == -0.4
    assert result.mean_dbfs == -21.0
    assert result.beat_timestamps == [12.8, 19.6, 28.0]


def test_factory_resolves_aws_lambda_service():
    settings = Settings(
        APP_ENV="production",
        USE_AWS_LAMBDA_MEDIA_WORKER=True,
        AWS_LAMBDA_MEDIA_FUNCTION="custom-processor",
    )
    service = get_media_processing_service(settings=settings)
    assert isinstance(service, AWSLambdaMediaProcessingService)
    assert service.function_name == "custom-processor"
