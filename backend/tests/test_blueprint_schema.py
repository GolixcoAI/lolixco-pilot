import pytest
from pydantic import ValidationError

from app.schemas.blueprint import EditingBlueprint, PacingEnum, SceneRecommendation


def test_valid_scene_recommendation() -> None:
    """Verify valid scene recommendation model."""
    scene = SceneRecommendation(
        id="scene-01",
        start_seconds=2.4,
        end_seconds=6.8,
        moment="Close-up of runner tying shoes with focus",
        why_it_works="Establishes determination before the action starts",
        editing_direction="Slow push in, cut on shoe lace snap",
        pacing=PacingEnum.MEDIUM,
        confidence=0.92,
        thumbnail_key="users/123/analyses/abc/previews/scene-01.jpg",
    )
    assert scene.id == "scene-01"
    assert scene.start_seconds == 2.4
    assert scene.end_seconds == 6.8
    assert scene.pacing == PacingEnum.MEDIUM


def test_invalid_scene_timestamps_inverted() -> None:
    """Verify validation error when start_seconds >= end_seconds."""
    with pytest.raises(ValidationError) as exc_info:
        SceneRecommendation(
            id="scene-bad",
            start_seconds=8.0,
            end_seconds=4.0,
            moment="Athlete sprint",
            why_it_works="High energy",
            editing_direction="Quick jump cut",
            pacing=PacingEnum.FAST,
        )
    assert "strictly less than end_seconds" in str(exc_info.value)


def test_invalid_scene_timestamps_equal() -> None:
    """Verify validation error when start_seconds == end_seconds."""
    with pytest.raises(ValidationError):
        SceneRecommendation(
            id="scene-zero",
            start_seconds=5.0,
            end_seconds=5.0,
            moment="Still shot",
            why_it_works="Pause",
            editing_direction="Hold",
        )


def test_valid_editing_blueprint() -> None:
    """Verify complete editing blueprint contract validation."""
    summary_text = (
        "A compact 3-act structure focusing on athlete prep, "
        "acceleration, and the finish line reaction."
    )
    sequence_rationale = (
        "Contrasting rapid breathing with slow-motion stride creates dynamic rhythm."
    )
    blueprint = EditingBlueprint(
        title="High Voltage Sprint Teaser",
        creative_intent="Build tension and deliver explosive kinetic energy in 30 seconds",
        summary=summary_text,
        target_duration_seconds=30.0,
        aspect_ratio="9:16",
        hook="Open with the breathing sound and rapid macro cut at 0.5s",
        scenes=[
            SceneRecommendation(
                id="scene-01",
                start_seconds=0.5,
                end_seconds=3.2,
                moment="Eyes locked onto the track",
                why_it_works="Hooks the viewer immediately with raw emotion",
                editing_direction="Hard cut on the gun sound",
                pacing=PacingEnum.FAST,
            ),
            SceneRecommendation(
                id="scene-02",
                start_seconds=4.0,
                end_seconds=12.5,
                moment="High speed tracking shot of stride",
                why_it_works="Visualizes momentum and speed",
                editing_direction="Speed ramp into slow motion at peak stride",
                pacing=PacingEnum.SLOW,
            ),
        ],
        sequence_rationale=sequence_rationale,
        ending_suggestion="Freeze on the winning step with high contrast title overlay.",
        caveats=["Lighting drops slightly between 5.0s and 7.0s."],
    )
    assert blueprint.title == "High Voltage Sprint Teaser"
    assert len(blueprint.scenes) == 2
    assert blueprint.aspect_ratio == "9:16"


def test_uncalibrated_confidence_allowed_as_none() -> None:
    """Ensure confidence can remain null/None without fabricated values."""
    scene = SceneRecommendation(
        id="scene-unrated",
        start_seconds=1.0,
        end_seconds=3.0,
        moment="Actor turns head",
        why_it_works="Transitions focus",
        editing_direction="Cut on whip pan",
        confidence=None,
    )
    assert scene.confidence is None
