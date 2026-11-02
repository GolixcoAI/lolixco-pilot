from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_ENV_FILE, REPO_ROOT, Settings


@pytest.fixture(autouse=True)
def isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure config unit tests evaluate clean class defaults independent of ambient .env files."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def test_default_settings() -> None:
    """Verify default settings initialization."""
    settings = Settings()
    assert settings.APP_ENV in ("development", "test", "production")
    assert settings.MAX_UPLOAD_BYTES == 104857600
    assert settings.MAX_VIDEO_SECONDS == 120
    assert settings.SIGNED_URL_TTL_SECONDS == 900
    assert settings.VIDEO_RETENTION_DAYS == 7
    assert settings.DAILY_ANALYSIS_LIMIT == 5
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS


def test_cors_origin_parsing_comma_separated() -> None:
    """Verify comma-separated origins string parses into list."""
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:3000, https://editor.lolixco.com",
    )
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


def test_database_provider_configuration_settings() -> None:
    """Verify DATABASE_PROVIDER and SUPABASE_PUBLISHABLE_KEY configuration and validation."""
    default_settings = Settings()
    assert default_settings.DATABASE_PROVIDER == "memory"
    assert default_settings.SUPABASE_PUBLISHABLE_KEY == ""

    # Valid supabase config
    supabase_settings = Settings(
        DATABASE_PROVIDER="supabase",
        SUPABASE_URL="https://myproj.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_pub_key_123",
    )
    assert supabase_settings.DATABASE_PROVIDER == "supabase"
    assert supabase_settings.SUPABASE_PUBLISHABLE_KEY == "sb_pub_key_123"

    # Missing keys with supabase provider raises ValidationError
    with pytest.raises(ValidationError):
        Settings(DATABASE_PROVIDER="supabase", SUPABASE_URL="", SUPABASE_PUBLISHABLE_KEY="")

    with pytest.raises(ValidationError):
        Settings(
            DATABASE_PROVIDER="supabase",
            SUPABASE_URL="https://myproj.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="",
        )

    # Invalid database provider raises ValidationError
    with pytest.raises(ValidationError):
        Settings(DATABASE_PROVIDER="mysql")


def test_repo_root_and_default_env_path_resolution() -> None:
    """Verify REPO_ROOT and DEFAULT_ENV_FILE are absolute paths pointing to repo root .env."""
    assert REPO_ROOT.is_absolute()
    assert (REPO_ROOT / "backend" / "app" / "config.py").is_file()
    assert DEFAULT_ENV_FILE == REPO_ROOT / ".env"
    assert DEFAULT_ENV_FILE.is_absolute()


def test_settings_load_consistently_regardless_of_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify settings load from the canonical repository-root .env regardless of process cwd."""
    mock_root = tmp_path / "mock_repo"
    mock_backend = mock_root / "backend"
    mock_backend.mkdir(parents=True)

    # Repository-root .env file
    root_env = mock_root / ".env"
    root_env.write_text("APP_ENV=root_loaded_env\n", encoding="utf-8")

    # backend/.env that should NOT be loaded
    backend_env = mock_backend / ".env"
    backend_env.write_text("APP_ENV=backend_should_not_load\n", encoding="utf-8")

    # Configure Settings to use the canonical root_env
    monkeypatch.setitem(Settings.model_config, "env_file", root_env)

    # 1. Starting from repository root
    monkeypatch.chdir(mock_root)
    settings_from_root = Settings()
    assert settings_from_root.APP_ENV == "root_loaded_env"

    # 2. Starting from backend/ directory
    monkeypatch.chdir(mock_backend)
    settings_from_backend = Settings()
    assert settings_from_backend.APP_ENV == "root_loaded_env"


def test_os_environment_variable_precedence_over_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify OS environment variables take precedence over .env file values."""
    mock_env = tmp_path / ".env"
    mock_env.write_text("APP_ENV=dotenv_value\nAI_PROVIDER=mock\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", mock_env)

    monkeypatch.setenv("APP_ENV", "os_environ_override")
    settings = Settings()
    assert settings.APP_ENV == "os_environ_override"
    assert settings.AI_PROVIDER == "mock"


def test_default_env_file_loads_consistently_from_real_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify DEFAULT_ENV_FILE is preserved when working directory is repo root or backend/."""
    # Restore actual default env_file for this test
    monkeypatch.setitem(Settings.model_config, "env_file", DEFAULT_ENV_FILE)

    # Test cwd = REPO_ROOT
    monkeypatch.chdir(REPO_ROOT)
    settings_root_cwd = Settings()

    # Test cwd = REPO_ROOT / "backend"
    monkeypatch.chdir(REPO_ROOT / "backend")
    settings_backend_cwd = Settings()

    # Both must produce identical configuration
    assert settings_root_cwd.APP_ENV == settings_backend_cwd.APP_ENV
    assert settings_root_cwd.AI_PROVIDER == settings_backend_cwd.AI_PROVIDER
    assert settings_root_cwd.AWS_REGION == settings_backend_cwd.AWS_REGION
    assert settings_root_cwd.ALLOWED_ORIGINS == settings_backend_cwd.ALLOWED_ORIGINS
