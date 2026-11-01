"""Unit tests for smoke_test_inference CLI argument parsing and schema compatibility."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from scripts.smoke_test_inference import create_parser, run_smoke_test

from app.schemas.analysis import CreativeBriefContext as SchemaCreativeBriefContext
from app.schemas.analysis import CreativeBriefInput
from app.services.ai_provider import CreativeBriefContext as ServiceCreativeBriefContext


def test_default_cli_arguments() -> None:
    """Default invocation selects baseten provider and no video URL override."""
    parser = create_parser()
    args = parser.parse_args([])
    assert args.provider == "baseten"
    assert args.video_url is None


def test_provider_argument_meta() -> None:
    """Explicit --provider meta is parsed correctly."""
    parser = create_parser()
    args = parser.parse_args(["--provider", "meta"])
    assert args.provider == "meta"


def test_provider_argument_baseten() -> None:
    """Explicit --provider baseten is parsed correctly."""
    parser = create_parser()
    args = parser.parse_args(["--provider", "baseten"])
    assert args.provider == "baseten"


def test_video_url_argument() -> None:
    """Custom video URL argument is preserved."""
    parser = create_parser()
    test_url = "https://cdn.example.com/footage/sample_cut.mp4"
    args = parser.parse_args(["--video-url", test_url])
    assert args.video_url == test_url


def test_invalid_provider_rejected() -> None:
    """Unsupported provider names must be rejected by argparse with SystemExit."""
    parser = create_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--provider", "invalid_provider"])
    assert exc_info.value.code == 2


def test_schema_creative_brief_compatibility() -> None:
    """Verify that CreativeBriefInput and CreativeBriefContext agree on core brief fields."""
    schema_obj = SchemaCreativeBriefContext(
        title="Smoke Test Hook",
        description="High-octane anime fight recap",
        style="Fast & Kinetic",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=15.0,
    )
    assert schema_obj.title == "Smoke Test Hook"
    assert schema_obj.target_duration == 15.0

    pydantic_input = CreativeBriefInput(
        title="Smoke Test Hook",
        description="High-octane anime fight recap",
        style="Fast & Kinetic",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=15.0,
    )
    assert pydantic_input.title == "Smoke Test Hook"

    service_obj = ServiceCreativeBriefContext(
        title="Smoke Test Hook",
        description="High-octane anime fight recap",
        style="Fast & Kinetic",
        pacing="fast",
        aspect_ratio="9:16",
        target_duration=15.0,
    )
    assert service_obj.title == schema_obj.title
    assert service_obj.description == schema_obj.description
    assert service_obj.style == schema_obj.style
    assert service_obj.pacing == schema_obj.pacing
    assert service_obj.aspect_ratio == schema_obj.aspect_ratio
    assert service_obj.target_duration == schema_obj.target_duration


def test_help_flag_subprocess() -> None:
    """CLI --help flag prints usage and exits cleanly with 0 without network activity."""
    result = subprocess.run(
        [sys.executable, "scripts/smoke_test_inference.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "--provider" in result.stdout
    assert "baseten" in result.stdout
    assert "meta" in result.stdout
    assert "--video-url" in result.stdout


@pytest.mark.asyncio
async def test_smoke_test_safeguard_aborts_on_non_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke test must abort without executing inference when user does not enter RUN."""
    monkeypatch.setattr("builtins.input", lambda _: "CANCEL")

    from app.config import Settings

    dummy_settings = Settings(
        APP_ENV="test",
        BASETEN_API_KEY="test_baseten_key",
        MODEL_API_KEY="test_meta_key",
    )

    with (
        patch("scripts.smoke_test_inference.get_settings", return_value=dummy_settings),
        patch("scripts.smoke_test_inference.BasetenProvider") as mock_provider_cls,
    ):
        mock_instance = AsyncMock()
        mock_provider_cls.return_value = mock_instance

        with pytest.raises(SystemExit) as exc_info:
            await run_smoke_test("baseten", None)

        assert exc_info.value.code == 0
        mock_instance.analyze_video_intelligence.assert_not_called()


@pytest.mark.asyncio
async def test_smoke_test_exits_when_api_key_missing() -> None:
    """Smoke test must exit with code 1 if the required provider key is missing."""
    from app.config import Settings

    empty_settings = Settings(
        APP_ENV="test",
        BASETEN_API_KEY="",
        MODEL_API_KEY="",
    )

    with patch("scripts.smoke_test_inference.get_settings", return_value=empty_settings):
        with pytest.raises(SystemExit) as exc_info:
            await run_smoke_test("baseten", None)
        assert exc_info.value.code == 1

        with pytest.raises(SystemExit) as exc_info_meta:
            await run_smoke_test("meta", None)
        assert exc_info_meta.value.code == 1
