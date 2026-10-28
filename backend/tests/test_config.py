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
