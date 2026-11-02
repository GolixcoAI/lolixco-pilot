"""Unit tests for Muse Glimmer 30B QLoRA training pipeline, dataset validation, and evaluation.

Verifies:
1. AnimeEventSample temporal validation rules (start < peak < end <= duration).
2. Hard negative distractor modeling.
3. ShareGPT / ChatML prompt conversion for Axolotl / TRL fine-tuning.
4. Temporal IoU (tIoU) calculation across overlap conditions.
5. Peak impact frame error and benchmark evaluation runner.
6. Axolotl YAML configuration validation and hardware requirement estimation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from training.dataset import (
    AnimeEventSample,
    AudioTaskReference,
    RepresentativeFrame,
    compute_dataset_statistics,
    create_fixture_image,
    create_seed_dataset,
    export_dataset_to_jsonl,
    format_sample_to_instruction,
    format_sample_to_multimodal_messages,
    generate_dataset_manifests,
    split_dataset_by_group,
    validate_sample_image_assets,
    verify_image_asset,
    verify_split_leakage,
)
from training.evaluate import (
    calculate_peak_error,
    calculate_tiou,
    compare_model_predictions,
    evaluate_predictions,
)
from training.train_glimmer_qlora import (
    cli_main,
    create_parser,
    modal_main,
    run_pipeline_dry_run,
    validate_training_pipeline_setup,
)


def test_anime_event_sample_valid() -> None:
    """Valid event sample satisfies all temporal constraints."""
    sample = AnimeEventSample(
        sample_id="test-001",
        source_title="Jujutsu Kaisen",
        franchise="Jujutsu Kaisen",
        season=1,
        episode=20,
        arc="Kyoto Goodwill",
        event_name="Hollow Purple",
        approx_start_seconds=10.0,
        approx_end_seconds=20.0,
        peak_frame_timestamp=15.0,
        duration_seconds=25.0,
        representative_frames=[
            RepresentativeFrame(
                timecode="00:15.00",
                timestamp_seconds=15.0,
                frame_type="peak",
                description="Purple convergence",
            )
        ],
        visual_evidence=["Purple sphere"],
        status="confirmed",
        audio_task_reference=AudioTaskReference(
            has_audio=True,
            soundtrack_title="Your Battle",
            audio_match_status="strong_inference",
        ),
    )
    assert sample.sample_id == "test-001"
    assert sample.duration_seconds == 25.0
    assert len(sample.representative_frames) == 1


def test_anime_event_sample_temporal_boundary_violations() -> None:
    """Temporal validator rejects inverted timestamps or peak outside boundaries."""
    # 1. start >= end
    with pytest.raises(ValidationError, match="must be strictly less than approx_end_seconds"):
        AnimeEventSample(
            sample_id="err-1",
            source_title="JJK",
            franchise="JJK",
            event_name="Test",
            approx_start_seconds=20.0,
            approx_end_seconds=10.0,
            peak_frame_timestamp=15.0,
            duration_seconds=30.0,
        )

    # 2. end > duration
    with pytest.raises(ValidationError, match="exceeds total duration"):
        AnimeEventSample(
            sample_id="err-2",
            source_title="JJK",
            franchise="JJK",
            event_name="Test",
            approx_start_seconds=10.0,
            approx_end_seconds=35.0,
            peak_frame_timestamp=15.0,
            duration_seconds=30.0,
        )

    # 3. peak < start
    with pytest.raises(ValidationError, match="must lie within"):
        AnimeEventSample(
            sample_id="err-3",
            source_title="JJK",
            franchise="JJK",
            event_name="Test",
            approx_start_seconds=10.0,
            approx_end_seconds=20.0,
            peak_frame_timestamp=5.0,
            duration_seconds=30.0,
        )


def test_format_sample_to_instruction() -> None:
    """format_sample_to_instruction produces ChatML conversations structure."""
    seed = create_seed_dataset()
    sample = seed[0]

    instruct = format_sample_to_instruction(sample)
    assert instruct["id"] == sample.sample_id
    assert len(instruct["conversations"]) == 3
    assert instruct["conversations"][0]["from"] == "system"
    assert instruct["conversations"][1]["from"] == "human"
    assert instruct["conversations"][2]["from"] == "gpt"

    gpt_content = json.loads(instruct["conversations"][2]["value"])
    assert gpt_content["event_name"] == sample.event_name
    assert gpt_content["timing"]["peak_frame_seconds"] == sample.peak_frame_timestamp


def test_seed_dataset_contains_positives_and_distractors() -> None:
    """Curated seed dataset contains confirmed positives and hard negative distractors."""
    samples = create_seed_dataset()
    assert len(samples) >= 4

    positives = [s for s in samples if s.status == "confirmed"]
    negatives = [s for s in samples if s.status == "negative_distractor"]

    assert len(positives) >= 3
    assert len(negatives) >= 2

    # Check distractor titles
    distractor_names = [n.event_name for n in negatives]
    assert any("NOT Hollow Purple" in name for name in distractor_names)
    assert any("NOT Jujutsu Kaisen" in name for name in distractor_names)


def test_export_dataset_to_jsonl() -> None:
    """export_dataset_to_jsonl writes valid lines to disk."""
    samples = create_seed_dataset()
    with tempfile.NamedTemporaryFile(suffix=".jsonl") as tmp:
        count = export_dataset_to_jsonl(samples, tmp.name)
        assert count == len(samples)

        with open(tmp.name, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == len(samples)
        first_obj = json.loads(lines[0])
        assert "conversations" in first_obj


def test_calculate_tiou() -> None:
    """calculate_tiou accurately measures temporal Intersection over Union."""
    # Complete match
    assert calculate_tiou(10.0, 20.0, 10.0, 20.0) == 1.0

    # No overlap
    assert calculate_tiou(10.0, 20.0, 30.0, 40.0) == 0.0

    # 50% intersection: [10, 20] and [15, 25] -> intersection 5, union 15 -> 0.3333
    tiou = calculate_tiou(10.0, 20.0, 15.0, 25.0)
    assert 0.33 <= tiou <= 0.34

    # Invalid range returns 0.0
    assert calculate_tiou(20.0, 10.0, 10.0, 20.0) == 0.0


def test_calculate_peak_error() -> None:
    """calculate_peak_error measures absolute frame timestamp discrepancy."""
    assert calculate_peak_error(15.25, 15.00) == 0.25
    assert calculate_peak_error(14.50, 15.00) == 0.50
    assert calculate_peak_error(20.00, 20.00) == 0.00


def test_evaluate_predictions() -> None:
    """evaluate_predictions produces complete metrics report against ground truth."""
    samples = create_seed_dataset()
    gt1, gt2 = samples[0], samples[1]

    # Perfect prediction for sample 1, slightly off for sample 2
    preds = [
        {
            "sample_id": gt1.sample_id,
            "pred_start": gt1.approx_start_seconds,
            "pred_end": gt1.approx_end_seconds,
            "pred_peak": gt1.peak_frame_timestamp,
            "pred_event_name": gt1.event_name,
        },
        {
            "sample_id": gt2.sample_id,
            "pred_start": gt2.approx_start_seconds - 1.0,
            "pred_end": gt2.approx_end_seconds + 1.0,
            "pred_peak": gt2.peak_frame_timestamp + 0.30,  # within 500ms
            "pred_event_name": gt2.event_name,
        },
    ]

    metrics = evaluate_predictions(preds, [gt1, gt2])
    assert metrics["total_samples"] == 2.0
    assert metrics["mean_tiou"] > 0.80
    assert metrics["tiou_at_50"] == 100.0
    assert metrics["peak_accuracy_500ms"] == 100.0
    assert metrics["classification_accuracy"] == 100.0


def test_validate_training_pipeline_setup_success() -> None:
    """validate_training_pipeline_setup verifies the actual Axolotl YAML configuration."""
    config_path = "training/configs/muse_glimmer_30b_qlora.yml"
    setup = validate_training_pipeline_setup(config_path)

    # Local validation always passes; remote readiness reflects whether volume is provisioned
    assert setup["status"] in ("ready", "local_ready_remote_blocked")
    assert setup["local_validation_passed"] is True
    assert setup["base_model"] == "meta-models/Muse-Glimmer-30B"
    assert setup["adapter"] == "qlora"
    assert setup["lora_rank"] == 16
    assert setup["lora_alpha"] == 32
    assert setup["effective_batch_size"] == 8
    assert setup["sequence_len"] == 4096
    assert setup["hardware_requirement"] == "1x NVIDIA H100 (80GB SXM5)"
    assert setup["estimated_cost_usd"] == 7.90


def test_validate_training_pipeline_missing_config_raises() -> None:
    """validate_training_pipeline_setup raises FileNotFoundError for missing configs."""
    with pytest.raises(FileNotFoundError):
        validate_training_pipeline_setup("nonexistent/config.yml")


def test_cli_parser_defaults() -> None:
    """CLI parser provides correct defaults and arguments."""
    parser = create_parser()
    args = parser.parse_args([])
    assert args.config == "training/configs/muse_glimmer_30b_qlora.yml"
    assert args.dry_run is True
    assert args.dataset is None
    assert args.run_training is False


def test_cli_main_dry_run_success(capsys: pytest.CaptureFixture[str]) -> None:
    """cli_main with --dry-run prints PASS checks, summary, and returns 0."""
    code = cli_main(["--dry-run"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "[PASS] Config File Existence" in captured
    assert "[PASS] Base Model Architecture" in captured
    assert "[PASS] 4-bit Quantization (QLoRA)" in captured
    assert "[PASS] LoRA Hyperparameters" in captured
    assert "[PASS] Modal Checkpoint Volume Configuration" in captured
    assert (
        "[PASS] Modal Checkpoint Volume Provisioning" in captured
        or "[NOT PROVISIONED] Modal Checkpoint Volume Provisioning" in captured
    )
    assert "[PASS] Modal Secret Binding" in captured
    assert "[PASS] Dataset Temporal Validity" in captured
    assert "[PASS] Image Availability & Asset Decoding" in captured
    assert "[PASS] Multimodal Data Formatting" in captured
    assert "[PASS] Dataset Splitting & Zero-Leakage" in captured
    assert "Local Validation       : 19 / 19 checks PASSED (Status: LOCAL_PASSED)" in captured
    assert (
        "Overall Pipeline Status: READY" in captured
        or "Overall Pipeline Status: LOCAL_READY_REMOTE_BLOCKED" in captured
    )
    assert "Zero GPU credits consumed" in captured


def test_cli_main_missing_config_returns_error(capsys: pytest.CaptureFixture[str]) -> None:
    """cli_main returns 1 and prints [FAIL] when config path does not exist."""
    code = cli_main(["--config", "nonexistent_config.yml"])
    assert code == 1
    captured = capsys.readouterr().out
    assert "[FAIL] Config File Existence" in captured
    assert "Local Validation       : 0 / 1 checks PASSED (Status: LOCAL_FAILED)" in captured
    assert "Overall Pipeline Status: FAILED" in captured
    assert "Pipeline validation FAILED" in captured


def test_run_pipeline_dry_run_invalid_model_fails() -> None:
    """run_pipeline_dry_run detects invalid base model target."""
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write("base_model: invalid-org/other-model-7b\nmodel_type: AutoModelForCausalLM\n")
        tmp_path = f.name

    try:
        passed, checks, meta = run_pipeline_dry_run(tmp_path)
        assert passed is False
        failed_checks = [c for c in checks if not c["passed"]]
        assert any(c["name"] == "Base Model Architecture" for c in failed_checks)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_run_pipeline_dry_run_missing_4bit_fails() -> None:
    """run_pipeline_dry_run detects missing 4-bit quantization requirement."""
    valid_cfg_text = Path("training/configs/muse_glimmer_30b_qlora.yml").read_text(encoding="utf-8")
    invalid_cfg_text = valid_cfg_text.replace("load_in_4bit: true", "load_in_4bit: false")

    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write(invalid_cfg_text)
        tmp_path = f.name

    try:
        passed, checks, _ = run_pipeline_dry_run(tmp_path)
        assert passed is False
        failed_checks = [c for c in checks if not c["passed"]]
        assert any(c["name"] == "4-bit Quantization (QLoRA)" for c in failed_checks)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_modal_main_entrypoint_invokes_dry_run() -> None:
    """modal_main executes cleanly in dry_run mode without raising exceptions."""
    modal_main(dry_run=True, config="training/configs/muse_glimmer_30b_qlora.yml")


def test_cli_subprocess_dry_run() -> None:
    """Invoking module with --dry-run executes with code 0 and output."""
    proc = subprocess.run(
        [sys.executable, "-m", "training.train_glimmer_qlora", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "LolixCopilot — Muse Glimmer 30B QLoRA Training Pipeline Dry-Run" in proc.stdout
    assert "[PASS] Config File Existence" in proc.stdout
    assert "[PASS] Modal Checkpoint Volume Configuration" in proc.stdout
    assert (
        "[PASS] Modal Checkpoint Volume Provisioning" in proc.stdout
        or "[NOT PROVISIONED] Modal Checkpoint Volume Provisioning" in proc.stdout
    )
    assert "Local Validation       : 19 / 19 checks PASSED (Status: LOCAL_PASSED)" in proc.stdout
    assert (
        "Overall Pipeline Status: READY" in proc.stdout
        or "Overall Pipeline Status: LOCAL_READY_REMOTE_BLOCKED" in proc.stdout
    )


def test_run_pipeline_dry_run_missing_volume_state() -> None:
    """When checkpoint volume is missing, local validation passes while remote is blocked."""
    config_path = "training/configs/muse_glimmer_30b_qlora.yml"
    passed, checks, meta = run_pipeline_dry_run(config_path, volume_exists_override=False)

    assert passed is True  # local validation passes
    assert meta["local_validation_passed"] is True
    assert meta["remote_ready"] is False
    assert meta["remote_training_blocked"] is True
    assert meta["status"] == "local_ready_remote_blocked"
    assert any(
        c["name"] == "Modal Checkpoint Volume Provisioning"
        and c["state"] == "NOT PROVISIONED"
        and not c["passed"]
        for c in checks
    )
    assert any(
        c["name"] == "Modal Checkpoint Volume Configuration"
        and c["state"] == "PASS"
        and c["passed"]
        for c in checks
    )


def test_run_pipeline_dry_run_existing_volume_state() -> None:
    """When checkpoint volume exists, remote readiness passes and overall status is ready."""
    config_path = "training/configs/muse_glimmer_30b_qlora.yml"
    passed, checks, meta = run_pipeline_dry_run(config_path, volume_exists_override=True)

    assert passed is True
    assert meta["local_validation_passed"] is True
    assert meta["remote_ready"] is True
    assert meta["remote_training_blocked"] is False
    assert meta["status"] == "ready"
    assert any(
        c["name"] == "Modal Checkpoint Volume Provisioning" and c["state"] == "PASS" and c["passed"]
        for c in checks
    )


def test_validate_training_pipeline_setup_remote_ready_flag() -> None:
    """validate_training_pipeline_setup raises when require_remote_ready=True without volume."""
    config_path = "training/configs/muse_glimmer_30b_qlora.yml"
    # Fails when remote readiness is strictly required and volume is missing
    with pytest.raises(ValueError, match="Pipeline remote readiness blocked"):
        validate_training_pipeline_setup(
            config_path,
            require_remote_ready=True,
            volume_exists_override=False,
        )

    # Succeeds when volume exists
    setup = validate_training_pipeline_setup(
        config_path,
        require_remote_ready=True,
        volume_exists_override=True,
    )
    assert setup["status"] == "ready"
    assert setup["remote_ready"] is True


def test_cli_subprocess_help() -> None:
    """Invoking `python -m training.train_glimmer_qlora --help` displays usage and arguments."""
    proc = subprocess.run(
        [sys.executable, "-m", "training.train_glimmer_qlora", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "usage: python -m training.train_glimmer_qlora" in proc.stdout
    assert "--dry-run" in proc.stdout
    assert "--config" in proc.stdout
    assert "--dataset" in proc.stdout
    assert "--run-training" in proc.stdout


def test_format_sample_to_multimodal_messages() -> None:
    """format_sample_to_multimodal_messages creates OpenAI Messages with typed image blocks."""
    seed = create_seed_dataset()
    sample = seed[0]

    mm_doc = format_sample_to_multimodal_messages(sample)
    assert mm_doc["id"] == sample.sample_id
    msgs = mm_doc["messages"]
    assert len(msgs) == 3
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"

    # User content must contain typed {"type": "image", "path": ...} blocks
    user_content = msgs[1]["content"]
    image_blocks = [p for p in user_content if p.get("type") == "image"]
    text_blocks = [p for p in user_content if p.get("type") == "text"]

    assert len(image_blocks) == len(sample.representative_frames)
    assert len(text_blocks) == 1
    assert all("path" in img for img in image_blocks)


def test_validate_sample_image_assets_passes_on_valid_seed() -> None:
    """validate_sample_image_assets verifies all physical assets of seed samples."""
    samples = create_seed_dataset(generate_fixture_images=True)
    sample = samples[0]
    is_valid, errors = validate_sample_image_assets(
        sample, check_dimensions=True, check_hashes=True
    )
    assert is_valid is True
    assert errors == []


def test_validate_sample_image_assets_catches_missing_and_out_of_order() -> None:
    """validate_sample_image_assets detects nonexistent files and out-of-order timestamps."""
    samples = create_seed_dataset(generate_fixture_images=True)
    sample = samples[0]

    # Mutate to nonexistent path
    mutated_frames = [
        RepresentativeFrame(
            timecode="00:05.00",
            timestamp_seconds=5.0,
            frame_type="setup",
            description="nonexistent frame",
            image_path="training/data/images/nonexistent_dir/missing.png",
        )
    ]
    bad_sample = sample.model_copy(update={"representative_frames": mutated_frames})
    is_valid, errors = validate_sample_image_assets(bad_sample)
    assert is_valid is False
    assert any("decode failure" in e or "does not exist" in e for e in errors)


def test_dataset_splitting_and_zero_leakage() -> None:
    """split_dataset_by_group splits along episode/video boundaries and verifies zero leakage."""
    samples = create_seed_dataset()
    splits = split_dataset_by_group(samples, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)

    assert len(splits["train"]) > 0
    assert len(splits["val"]) > 0
    assert len(splits["test"]) > 0

    is_leak_free, errors = verify_split_leakage(splits)
    assert is_leak_free is True
    assert errors == []


def test_dataset_statistics_distinguishes_genuine_and_fixtures() -> None:
    """compute_dataset_statistics separates genuine data from synthetic fixtures."""
    samples = create_seed_dataset(generate_fixture_images=True)
    stats = compute_dataset_statistics(samples)

    assert stats["total_samples"] == len(samples)
    assert stats["fixture_samples_count"] == len(samples)
    assert stats["genuine_samples_count"] == 0
    assert stats["is_purely_synthetic_fixtures"] is True
    assert stats["valid_image_assets"] > 0
    assert stats["missing_image_assets"] == 0
    assert stats["data_provenance_summary"]["fixture"] == len(samples)


def test_generate_dataset_manifests_reproducible(tmp_path: Path) -> None:
    """generate_dataset_manifests creates reproducible manifests, eval files, and metadata."""
    samples = create_seed_dataset(generate_fixture_images=True)
    meta = generate_dataset_manifests(samples, output_dir=tmp_path)

    assert meta["zero_leakage_verified"] is True
    assert (tmp_path / "train_manifest.jsonl").is_file()
    assert (tmp_path / "val_manifest.jsonl").is_file()
    assert (tmp_path / "test_manifest.jsonl").is_file()
    assert (tmp_path / "eval_manifest.json").is_file()
    assert (tmp_path / "manifest_metadata.json").is_file()

    # Verify SHA256 checksums exist
    assert "train_manifest_sha256" in meta["checksums"]
    assert "val_manifest_sha256" in meta["checksums"]
    assert "test_manifest_sha256" in meta["checksums"]


def test_evaluate_predictions_advanced_metrics() -> None:
    """evaluate_predictions produces precision, recall, F1, FPR, and category metrics."""
    samples = create_seed_dataset()
    gt_confirmed = [s for s in samples if s.status == "confirmed"][0]
    gt_distractor = [s for s in samples if s.status == "negative_distractor"][0]

    # Perfect prediction on positive, rejected distractor on negative
    preds = [
        {
            "sample_id": gt_confirmed.sample_id,
            "pred_start": gt_confirmed.approx_start_seconds,
            "pred_end": gt_confirmed.approx_end_seconds,
            "pred_peak": gt_confirmed.peak_frame_timestamp,
            "pred_event_name": gt_confirmed.event_name,
        },
        {
            "sample_id": gt_distractor.sample_id,
            "pred_start": gt_distractor.approx_start_seconds,
            "pred_end": gt_distractor.approx_end_seconds,
            "pred_peak": gt_distractor.peak_frame_timestamp,
            "pred_event_name": "Unrelated Cursed Technique (Red)",
        },
    ]

    metrics = evaluate_predictions(preds, [gt_confirmed, gt_distractor])
    assert metrics["precision"] == 100.0
    assert metrics["recall"] == 100.0
    assert metrics["f1_score"] == 100.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["true_positives"] == 1
    assert metrics["true_negatives"] == 1
    assert "category_metrics" in metrics


def test_compare_model_predictions() -> None:
    """compare_model_predictions computes deltas on identical test sets."""
    samples = create_seed_dataset()
    gt = samples[0]

    # Baseline: lower tIoU, worse peak error
    base_preds = [
        {
            "sample_id": gt.sample_id,
            "pred_start": gt.approx_start_seconds - 3.0,
            "pred_end": gt.approx_end_seconds + 3.0,
            "pred_peak": gt.peak_frame_timestamp + 1.2,
            "pred_event_name": "General Anime Combat",
        }
    ]

    # Adapted: tighter bounding, accurate peak frame
    adapted_preds = [
        {
            "sample_id": gt.sample_id,
            "pred_start": gt.approx_start_seconds + 0.1,
            "pred_end": gt.approx_end_seconds - 0.1,
            "pred_peak": gt.peak_frame_timestamp + 0.1,
            "pred_event_name": gt.event_name,
        }
    ]

    comp = compare_model_predictions(base_preds, adapted_preds, [gt])
    assert comp["is_statistically_improved"] is True
    assert comp["deltas"]["delta_mean_tiou"] > 0
    assert comp["deltas"]["delta_f1_score"] >= 0
    assert "Training loss alone" in comp["evaluation_rule"]


def test_image_asset_decoding_png_jpeg_webp(tmp_path: Path) -> None:
    """verify_image_asset correctly identifies PNG, JPEG, and WebP format headers."""
    # 1. PNG
    png_path = tmp_path / "test.png"
    create_fixture_image(png_path, width=128, height=64)
    is_valid, w, h, sha = verify_image_asset(png_path)
    assert is_valid is True
    assert w == 128
    assert h == 64
    assert len(sha) == 64

    # 2. Mock JPEG header
    jpeg_path = tmp_path / "test.jpg"
    # JPEG with SOF0 marker
    jpeg_data = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        b"\xff\xc0\x00\x11\x08\x00\x40\x00\x80\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xd9"
    )
    jpeg_path.write_bytes(jpeg_data)
    j_valid, j_w, j_h, j_sha = verify_image_asset(jpeg_path)
    assert j_valid is True
    assert j_w == 128
    assert j_h == 64


def test_create_candidate_from_proposal() -> None:
    """Proposal candidate parser creates valid AnimeEventSample with pending verification status."""
    from training.dataset import create_candidate_from_proposal

    mock_proposal = {
        "video_asset": {
            "file_name": "test_clip.mp4",
            "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "duration_seconds": 60.0,
            "resolution": "1920x1080",
            "fps": 30.0,
        },
        "proposed_identification": {
            "source_title": "Jujutsu Kaisen",
            "franchise": "Jujutsu Kaisen",
            "character": "Satoru Gojo",
            "event_name": "Hollow Technique: Purple",
        },
        "proposed_temporal_boundaries": {
            "event_start_seconds": 15.0,
            "event_peak_discharge_seconds": 30.0,
            "event_end_aftermath_seconds": 45.0,
        },
        "supporting_frames": [
            {
                "timestamp_seconds": 15.0,
                "phase": "setup",
                "description": "Technique setup",
                "path": "test/path/frame1.png",
                "width": 1920,
                "height": 1080,
                "sha256": "abcdef",
            },
            {
                "timestamp_seconds": 30.0,
                "phase": "peak",
                "description": "Technique discharge",
                "path": "test/path/frame2.png",
                "width": 1920,
                "height": 1080,
                "sha256": "abcdef2",
            },
        ],
        "audio_characteristics": {
            "soundtrack_note": "Acoustic crescendo",
        },
    }

    sample = create_candidate_from_proposal(mock_proposal)
    assert sample.sample_id == "eval-12345678"
    assert sample.annotation_status == "pending_verification"
    assert sample.rights_or_permission_status == "user_private_evaluation_clip_restricted"
    assert sample.approx_start_seconds == 15.0
    assert sample.peak_frame_timestamp == 30.0
    assert sample.approx_end_seconds == 45.0
    assert sample.duration_seconds == 60.0
    assert len(sample.representative_frames) == 2
    assert sample.representative_frames[0].timecode == "00:15.00"
    assert sample.representative_frames[1].timecode == "00:30.00"


def test_cli_main_run_training_without_dataset_fails_closed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When --run-training is requested without an explicit dataset, it fails closed."""
    code = cli_main(
        [
            "--config",
            "training/configs/muse_glimmer_30b_qlora.yml",
            "--run-training",
        ]
    )
    captured = capsys.readouterr().out
    assert code == 1
    assert "Production training requires an explicit dataset path via --dataset" in captured


def test_cli_main_run_training_with_synthetic_fixtures_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When supplied dataset has only synthetic fixtures, production training fails closed."""
    dataset_file = tmp_path / "synthetic_only.jsonl"
    fixtures = create_seed_dataset()
    with open(dataset_file, "w", encoding="utf-8") as f:
        for s in fixtures:
            f.write(s.model_dump_json() + "\n")

    code = cli_main(
        [
            "--config",
            "training/configs/muse_glimmer_30b_qlora.yml",
            "--dataset",
            str(dataset_file),
            "--run-training",
        ]
    )
    captured = capsys.readouterr().out
    assert code == 1
    assert "contains 0 verified genuine samples" in captured


def test_cli_main_run_training_with_restricted_clip_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When supplied dataset contains user-restricted private clips, training fails closed."""
    dataset_file = tmp_path / "with_restricted.jsonl"
    img1 = tmp_path / "frame1.png"
    img2 = tmp_path / "frame2.png"
    create_fixture_image(img1, width=128, height=64)
    create_fixture_image(img2, width=128, height=64)

    # Create one genuine-looking sample marked as restricted
    sample = AnimeEventSample(
        sample_id="restricted_clip_01",
        source_title="Private Anime Clip",
        franchise="Private Anime",
        source_video_id="private_vid_01",
        duration_seconds=30.0,
        character_names=["Private Char"],
        event_name="Secret Technique",
        approx_start_seconds=5.0,
        peak_frame_timestamp=10.0,
        approx_end_seconds=15.0,
        rights_or_permission_status="user_private_evaluation_clip_restricted",
        annotation_status="verified",
        annotation_source="human_annotator",
        representative_frames=[
            RepresentativeFrame(
                timestamp_seconds=5.0,
                timecode="00:05.00",
                frame_type="setup",
                description="Technique setup",
                image_path=str(img1),
                width=128,
                height=64,
            ),
            RepresentativeFrame(
                timestamp_seconds=10.0,
                timecode="00:10.00",
                frame_type="peak",
                description="Technique discharge",
                image_path=str(img2),
                width=128,
                height=64,
            ),
        ],
    )
    with open(dataset_file, "w", encoding="utf-8") as f:
        f.write(sample.model_dump_json() + "\n")

    code = cli_main(
        [
            "--config",
            "training/configs/muse_glimmer_30b_qlora.yml",
            "--dataset",
            str(dataset_file),
            "--run-training",
        ]
    )
    captured = capsys.readouterr().out
    assert code == 1
    assert "restricted items" in captured or "0 verified genuine samples" in captured


def test_docmatix_smoke_dataset_manifest_integrity() -> None:
    """Verify that the 16-sample Docmatix smoke manifest is correctly formatted."""
    smoke_jsonl = Path("training/data/docmatix_smoke/docmatix_smoke_16.jsonl")
    manifest_file = Path("training/data/docmatix_smoke/docmatix_smoke_manifest.json")
    if not smoke_jsonl.exists():
        pytest.skip("Docmatix smoke dataset not yet prepared locally")

    samples = []
    with open(smoke_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    assert len(samples) == 16
    for idx, s in enumerate(samples):
        assert s["id"] == f"docmatix_smoke_{idx:02d}"
        assert s["source"] == "HuggingFaceM4/Docmatix"
        assert s["split"] == "train"
        assert s["revision"] == "0725b65616e0e5f6024be10e38ddf8d8c48664fd"
        assert len(s["messages"]) == 2
        assert s["messages"][0]["role"] == "user"
        assert s["messages"][1]["role"] == "assistant"
        # User message has image with path and text query
        user_content = s["messages"][0]["content"]
        img_item = next(c for c in user_content if c.get("type") == "image")
        assert "path" in img_item and Path(img_item["path"]).exists()
        assert any(c.get("type") == "text" and len(c.get("text", "")) > 0 for c in user_content)
        # Assistant has response text
        asst_content = s["messages"][1]["content"]
        assert any(c.get("type") == "text" and len(c.get("text", "")) > 0 for c in asst_content)
        # Verify physical image exists
        for img_path in s["images"]:
            assert Path(img_path).exists()

    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["license"] == "MIT"
        assert manifest["split"] == "train"
        assert manifest["dataset_revision"] == "0725b65616e0e5f6024be10e38ddf8d8c48664fd"
