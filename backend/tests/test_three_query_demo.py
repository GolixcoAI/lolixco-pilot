"""Tests for the Three Canonical AI Director Demonstration Queries & Export Pipeline.

Verifies:
1. Query 1: Edit Review with 6-scene breakdown and 5 actionable suggestions.
2. Query 2: Hollow Purple text overlay on V2 track (37.0s - 44.0s).
3. Query 3: Last 30 seconds trim calculation (38.08s - 68.08s), duration 30.0s,
   and title overlay remapping (0.0s - 5.92s).
4. Real export rendering with text overlay in H.264 MP4.
"""

from __future__ import annotations

import os
import uuid
import pytest

from app.schemas.chat import ChatRequest
from app.schemas.export import ExportRequest, ExportSegment, TextOverlayItem
from app.services.chat_director import get_chat_director_service
from app.services.media_processing import LocalMediaProcessingService


def test_query_1_review_my_edit():
    """Verify Query 1 returns detailed editorial direction and timestamps."""
    svc = get_chat_director_service()
    media_meta = {
        "original_filename": "gojo_hollow_purple_edit.mp4",
        "duration_seconds": 68.08,
    }
    prompt = "Review my edit. Give me suggestions on what I should improve and tell me exactly where I should edit."
    resp = svc.process_chat_message(ChatRequest(message=prompt), media_data=media_meta)

    assert "68.08s Source Footage" in resp.message.content
    assert len(resp.scene_breakdown) == 6
    assert len(resp.edit_recommendations) == 5
    assert resp.message.timecode_jump == 37.0
    assert any("opening levitation" in r.text.lower() for r in resp.edit_recommendations)
    assert any("hollow purple" in r.text.lower() for r in resp.edit_recommendations)
    assert any("last 30 seconds" in r.text.lower() for r in resp.edit_recommendations)


def test_query_2_text_overlay():
    """Verify Query 2 locates Hollow Purple and returns V2 overlay action."""
    svc = get_chat_director_service()
    media_meta = {
        "original_filename": "gojo_hollow_purple_edit.mp4",
        "duration_seconds": 68.08,
    }
    prompt = "Locate Hollow Purple and add the text 'Hollow Purple' in purple colour from 00:37 to 00:44."
    resp = svc.process_chat_message(ChatRequest(message=prompt), media_data=media_meta)

    assert resp.message.timecode_jump == 37.0
    assert resp.updated_blueprint is not None
    assert resp.updated_blueprint.get("action") == "add_text_overlay"
    overlay = resp.updated_blueprint.get("overlay", {})
    assert overlay.get("text") == "Hollow Purple"
    assert overlay.get("color") == "#a855f7"
    assert overlay.get("start_seconds") == 37.0
    assert overlay.get("end_seconds") == 44.0
    assert overlay.get("track") == "V2"


def test_query_3_last_30_seconds_trim_and_remapping():
    """Verify Query 3 calculates last 30s boundaries and remaps overlay correctly."""
    svc = get_chat_director_service()
    media_meta = {
        "original_filename": "gojo_hollow_purple_edit.mp4",
        "duration_seconds": 68.08,
    }
    prompt = "Keep the last 30 seconds from this video and prepare it for export."
    resp = svc.process_chat_message(ChatRequest(message=prompt), media_data=media_meta)

    assert resp.message.timecode_jump == 38.08
    assert resp.updated_blueprint is not None
    assert resp.updated_blueprint.get("action") == "trim_selection"
    assert resp.updated_blueprint.get("trim_start") == 38.08
    assert resp.updated_blueprint.get("trim_end") == 68.08
    assert resp.updated_blueprint.get("target_duration_seconds") == 30.0

    remapped = resp.updated_blueprint.get("remapped_overlays", [])
    assert len(remapped) == 1
    assert remapped[0]["text"] == "Hollow Purple"
    # Intersecting range: 38.08 to 44.0 -> remapped to [0.0, 5.92]
    assert remapped[0]["start_seconds"] == 0.0
    assert remapped[0]["end_seconds"] == 5.92


@pytest.mark.asyncio
async def test_local_render_with_text_overlay():
    """Verify local rendering handles text overlays without error."""
    processor = LocalMediaProcessingService()
    test_src = "training/data/raw/gojo_hollow_purple_edit.mp4"
    if not os.path.exists(test_src):
        pytest.skip("Gojo raw source clip not found")

    out_path = f"/tmp/test_unit_cut_{uuid.uuid4().hex[:6]}.mp4"
    try:
        res = await processor.render_edit_cut(
            video_path=test_src,
            segments=[{"start_seconds": 38.08, "end_seconds": 41.08}],
            output_cut_path=out_path,
            target_resolution="1080p",
            include_audio=True,
            text_overlays=[
                {"text": "Hollow Purple", "color": "#a855f7", "start_seconds": 0.0, "end_seconds": 3.0}
            ],
        )
        assert res.success is True
        assert os.path.exists(out_path)
        assert res.duration_seconds == 3.0
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

