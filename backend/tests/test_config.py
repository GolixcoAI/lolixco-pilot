import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_settings() -> None:
    """Verify default settings initialization."""
    settings = Settings()
    assert settings.APP_ENV in ("development", "test", "production")
    assert settings.MAX_UPLOAD_BYTES == 104857600
    assert settings.MAX_VIDEO_SECONDS == 60
    assert settings.SIGNED_URL_TTL_SECONDS == 900
    assert settings.VIDEO_RETENTION_DAYS == 7
    assert settings.DAILY_ANALYSIS_LIMIT == 5
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS


def test_cors_origin_parsing_comma_separated() -> None:
    """Verify comma-separated origins string parses into list."""
    settings = Settings(ALLOWED_ORIGINS="http://localhost:3000, https://editor.lolixco.com")  # type: ignore[arg-type]
    assert settings.ALLOWED_ORIGINS == ["http://localhost:3000", "https://editor.lolixco.com"]


def test_invalid_max_upload_bytes() -> None:
    """Verify validation triggers when upload size is non-positive or exceeds max."""
    with pytest.raises(ValidationError):
        Settings(MAX_UPLOAD_BYTES=0)

    with pytest.raises(ValidationError):
        Settings(MAX_UPLOAD_BYTES=-500)


def test_invalid_max_video_seconds() -> None:
    """Verify validation triggers on non-positive video duration."""
    with pytest.raises(ValidationError):
        Settings(MAX_VIDEO_SECONDS=0)


def test_aws_configuration_settings() -> None:
    """Verify AWS configuration defaults and overrides."""
    default_settings = Settings()
    assert default_settings.AWS_REGION == "ap-south-1"
    assert default_settings.AWS_S3_BUCKET == ""
    assert default_settings.AWS_PROFILE == ""
    assert default_settings.USE_MOCK_STORAGE is False

    custom_settings = Settings(
        AWS_REGION="us-east-1",
        AWS_S3_BUCKET="my-test-bucket",
        AWS_PROFILE="dev-profile",
        USE_MOCK_STORAGE=True,
    )
    assert custom_settings.AWS_REGION == "us-east-1"
    assert custom_settings.AWS_S3_BUCKET == "my-test-bucket"
    assert custom_settings.AWS_PROFILE == "dev-profile"
    assert custom_settings.USE_MOCK_STORAGE is True


def test_baseten_configuration_settings() -> None:
    """Verify Baseten AI provider settings defaults and overrides."""
    default_settings = Settings()
    assert default_settings.AI_PROVIDER == "mock"
    assert default_settings.BASETEN_API_KEY == ""
    assert default_settings.BASETEN_BASE_URL == "https://inference.baseten.co/v1"
    assert default_settings.BASETEN_MODEL == "meta-models/muse-spark-open-1026"
    assert default_settings.AI_REQUEST_TIMEOUT_SECONDS == 120
    assert default_settings.AI_MAX_RETRIES == 2

    custom_settings = Settings(
        AI_PROVIDER="baseten",
        BASETEN_API_KEY="test_baseten_key_secret",
        BASETEN_BASE_URL="https://custom.baseten.co/v1",
        BASETEN_MODEL="meta-models/muse-spark-open-1026-custom",
        AI_REQUEST_TIMEOUT_SECONDS=60,
        AI_MAX_RETRIES=1,
    )
    assert custom_settings.AI_PROVIDER == "baseten"
    assert custom_settings.BASETEN_API_KEY == "test_baseten_key_secret"
    assert custom_settings.BASETEN_BASE_URL == "https://custom.baseten.co/v1"
    assert custom_settings.BASETEN_MODEL == "meta-models/muse-spark-open-1026-custom"
    assert custom_settings.AI_REQUEST_TIMEOUT_SECONDS == 60
    assert custom_settings.AI_MAX_RETRIES == 1
