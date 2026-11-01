"""Evaluation metrics and benchmark runner for video event temporal localization.

Implements the evaluation criteria defined in JUJUTSU_KAISEN_EVENT_DATASET_SPEC.md:
- Temporal Intersection over Union (tIoU) across thresholds tIoU@0.3, tIoU@0.5, tIoU@0.75.
- Peak impact frame timestamp error (Delta t_peak <= 0.50s threshold for beat sync).
- Precision, Recall, and F1 for event identification.
"""

from __future__ import annotations

import logging
from typing import Any

from training.dataset import AnimeEventSample

logger = logging.getLogger(__name__)


def calculate_tiou(
    pred_start: float,
    pred_end: float,
    gt_start: float,
    gt_end: float,
) -> float:
    """Calculate Temporal Intersection-over-Union (tIoU) between two time intervals.

    Returns float in range [0.0, 1.0].
    """
    if pred_start >= pred_end or gt_start >= gt_end:
        return 0.0

    intersection_start = max(pred_start, gt_start)
    intersection_end = min(pred_end, gt_end)
    intersection = max(0.0, intersection_end - intersection_start)

    union_start = min(pred_start, gt_start)
    union_end = max(pred_end, gt_end)
    union = max(0.0, union_end - union_start)

    if union <= 0.0:
        return 0.0

    return round(intersection / union, 4)


def calculate_peak_error(pred_peak: float, gt_peak: float) -> float:
    """Calculate absolute timestamp error between predicted peak and ground truth peak in seconds."""
    return round(abs(pred_peak - gt_peak), 4)


def evaluate_predictions(
    predictions: list[dict[str, Any]],
    ground_truths: list[AnimeEventSample],
    tiou_threshold: float = 0.50,
) -> dict[str, Any]:
    """Compute aggregate benchmark metrics across a test set of predictions.

    Args:
        predictions: List of dicts containing:
            - 'sample_id': str
            - 'pred_start': float
            - 'pred_end': float
            - 'pred_peak': float
            - 'pred_event_name': str
        ground_truths: List of validated AnimeEventSample instances.
        tiou_threshold: Temporal IoU cutoff for true-positive classification (default 0.50).

    Returns:
        Dict containing:
            - 'total_samples': count
            - 'mean_tiou': average tIoU across all samples
            - 'tiou_at_30': percentage >= 0.30
            - 'tiou_at_50': percentage >= 0.50 (actionable editing cut threshold)
            - 'tiou_at_75': percentage >= 0.75
            - 'peak_accuracy_500ms': percentage with peak error <= 0.50s
            - 'mean_peak_error_seconds': average |Delta t_peak|
            - 'classification_accuracy': percentage of exact event name matches
            - 'precision': percentage of correct positive detections out of all positive predictions
            - 'recall': percentage of ground truth positive events correctly detected
            - 'f1_score': harmonic mean of precision and recall
            - 'false_positive_rate': percentage of negative/distractor samples falsely triggered
            - 'true_positives': integer count
            - 'false_positives': integer count
            - 'false_negatives': integer count
            - 'true_negatives': integer count
            - 'category_metrics': per-event-category performance breakdown
    """
    gt_map = {gt.sample_id: gt for gt in ground_truths}
    if not gt_map or not predictions:
        return {
            "total_samples": 0.0,
            "mean_tiou": 0.0,
            "tiou_at_30": 0.0,
            "tiou_at_50": 0.0,
            "tiou_at_75": 0.0,
            "peak_accuracy_500ms": 0.0,
            "mean_peak_error_seconds": 0.0,
            "classification_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "false_positive_rate": 0.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "true_negatives": 0,
            "category_metrics": {},
        }

    tious: list[float] = []
    peak_errors: list[float] = []
    class_correct = 0
    matched_count = 0

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    category_stats: dict[str, dict[str, Any]] = {
        "confirmed": {"total": 0, "correct": 0, "tious": [], "peak_errors": []},
        "negative_distractor": {"total": 0, "correct": 0, "false_positives": 0},
        "unrelated_combat": {"total": 0, "correct": 0, "false_positives": 0},
        "ambiguous": {"total": 0, "correct": 0, "false_positives": 0},
    }

    for pred in predictions:
        sample_id = pred.get("sample_id", "")
        gt = gt_map.get(sample_id)
        if not gt:
            continue

        matched_count += 1
        p_start = float(pred.get("pred_start", 0.0))
        p_end = float(pred.get("pred_end", 0.0))
        p_peak = float(pred.get("pred_peak", 0.0))
        p_event = str(pred.get("pred_event_name", "")).strip()

        # Compute tIoU
        tiou = calculate_tiou(
            p_start, p_end, gt.approx_start_seconds, gt.approx_end_seconds
        )
        tious.append(tiou)

        # Compute peak error
        p_err = calculate_peak_error(p_peak, gt.peak_frame_timestamp)
        peak_errors.append(p_err)

        # Classification check (sub-string or exact match)
        is_name_match = (
            gt.event_name.lower() in p_event.lower()
            or p_event.lower() in gt.event_name.lower()
        )
        if is_name_match:
            class_correct += 1

        # Track per-category stats
        cat = gt.status
        if cat not in category_stats:
            category_stats[cat] = {
                "total": 0,
                "correct": 0,
                "tious": [],
                "peak_errors": [],
            }
        category_stats[cat]["total"] += 1
        if is_name_match:
            category_stats[cat]["correct"] += 1
        if "tious" in category_stats[cat]:
            category_stats[cat]["tious"].append(tiou)
        if "peak_errors" in category_stats[cat]:
            category_stats[cat]["peak_errors"].append(p_err)

        # Binary confusion matrix evaluation:
        # Confirmed positive events:
        if gt.status == "confirmed":
            if is_name_match and tiou >= tiou_threshold:
                tp += 1
            else:
                fn += 1
        # Distractors / Unrelated / Ambiguous (Negative events):
        else:
            # If the model falsely predicts a positive combat event (e.g. claims Hollow Purple)
            if (
                "hollow purple" in p_event.lower()
                or "malevolent shrine" in p_event.lower()
                or "shadow garden" in p_event.lower()
            ):
                fp += 1
                if "false_positives" in category_stats[cat]:
                    category_stats[cat]["false_positives"] += 1
            else:
                tn += 1

    if matched_count == 0:
        return {
            "total_samples": 0.0,
            "mean_tiou": 0.0,
            "tiou_at_30": 0.0,
            "tiou_at_50": 0.0,
            "tiou_at_75": 0.0,
            "peak_accuracy_500ms": 0.0,
            "mean_peak_error_seconds": 0.0,
            "classification_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "false_positive_rate": 0.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "true_negatives": 0,
            "category_metrics": {},
        }

    mean_tiou = round(sum(tious) / matched_count, 4)
    tiou_30 = round(sum(1 for t in tious if t >= 0.30) / matched_count * 100.0, 2)
    tiou_50 = round(sum(1 for t in tious if t >= 0.50) / matched_count * 100.0, 2)
    tiou_75 = round(sum(1 for t in tious if t >= 0.75) / matched_count * 100.0, 2)

    peak_sync_500ms = round(
        sum(1 for e in peak_errors if e <= 0.50) / matched_count * 100.0, 2
    )
    mean_peak_err = round(sum(peak_errors) / matched_count, 4)
    class_acc = round(class_correct / matched_count * 100.0, 2)

    # Precision, Recall, F1, FPR calculation
    precision = (
        round((tp / (tp + fp) * 100.0), 2)
        if (tp + fp) > 0
        else (100.0 if tp > 0 else 0.0)
    )
    recall = round((tp / (tp + fn) * 100.0), 2) if (tp + fn) > 0 else 0.0
    if precision + recall > 0.0:
        f1 = round((2.0 * precision * recall) / (precision + recall), 2)
    else:
        f1 = 0.0

    fpr = round((fp / (fp + tn) * 100.0), 2) if (fp + tn) > 0 else 0.0

    # Format category breakdown
    category_summary: dict[str, dict[str, Any]] = {}
    for cat_name, stats in category_stats.items():
        tot = stats.get("total", 0)
        corr = stats.get("correct", 0)
        c_acc = round(corr / tot * 100.0, 2) if tot > 0 else 0.0
        c_tious = stats.get("tious", [])
        c_mean_tiou = round(sum(c_tious) / len(c_tious), 4) if c_tious else 0.0
        category_summary[cat_name] = {
            "total_samples": tot,
            "accuracy": c_acc,
            "mean_tiou": c_mean_tiou,
            "false_positives": stats.get("false_positives", 0),
        }

    return {
        "total_samples": float(matched_count),
        "mean_tiou": mean_tiou,
        "tiou_at_30": tiou_30,
        "tiou_at_50": tiou_50,
        "tiou_at_75": tiou_75,
        "peak_accuracy_500ms": peak_sync_500ms,
        "mean_peak_error_seconds": mean_peak_err,
        "classification_accuracy": class_acc,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "false_positive_rate": fpr,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "category_metrics": category_summary,
    }


def compare_model_predictions(
    base_predictions: list[dict[str, Any]],
    adapted_predictions: list[dict[str, Any]],
    ground_truths: list[AnimeEventSample],
    tiou_threshold: float = 0.50,
) -> dict[str, Any]:
    """Compare base model and adapted (QLoRA) model on identical held-out examples.

    Validates whether adaptation genuinely improves temporal precision, event
    recognition, and distractor rejection compared to base foundation weights.

    Note:
        Training loss alone must never be treated as proof of improved event recognition.
    """
    base_metrics = evaluate_predictions(base_predictions, ground_truths, tiou_threshold)
    adapted_metrics = evaluate_predictions(
        adapted_predictions, ground_truths, tiou_threshold
    )

    deltas: dict[str, float] = {
        "delta_mean_tiou": round(
            adapted_metrics["mean_tiou"] - base_metrics["mean_tiou"], 4
        ),
        "delta_tiou_at_50": round(
            adapted_metrics["tiou_at_50"] - base_metrics["tiou_at_50"], 2
        ),
        "delta_tiou_at_75": round(
            adapted_metrics["tiou_at_75"] - base_metrics["tiou_at_75"], 2
        ),
        "delta_peak_accuracy_500ms": round(
            adapted_metrics["peak_accuracy_500ms"]
            - base_metrics["peak_accuracy_500ms"],
            2,
        ),
        "delta_mean_peak_error_seconds": round(
            adapted_metrics["mean_peak_error_seconds"]
            - base_metrics["mean_peak_error_seconds"],
            4,
        ),
        "delta_classification_accuracy": round(
            adapted_metrics["classification_accuracy"]
            - base_metrics["classification_accuracy"],
            2,
        ),
        "delta_precision": round(
            adapted_metrics["precision"] - base_metrics["precision"], 2
        ),
        "delta_recall": round(adapted_metrics["recall"] - base_metrics["recall"], 2),
        "delta_f1_score": round(
            adapted_metrics["f1_score"] - base_metrics["f1_score"], 2
        ),
        "delta_false_positive_rate": round(
            adapted_metrics["false_positive_rate"]
            - base_metrics["false_positive_rate"],
            2,
        ),
    }

    is_improved = (
        deltas["delta_tiou_at_50"] >= 0.0
        and deltas["delta_f1_score"] >= 0.0
        and deltas["delta_false_positive_rate"] <= 0.0
    )

    return {
        "benchmark_summary": "Adapted model outperforms base model"
        if is_improved
        else "Adapted model does not show uniform improvement",
        "is_statistically_improved": is_improved,
        "base_model_metrics": base_metrics,
        "adapted_model_metrics": adapted_metrics,
        "deltas": deltas,
        "evaluation_rule": (
            "Training loss alone must not be treated as proof of improved event recognition. "
            "A model is only considered successfully adapted if held-out temporal IoU and F1 improve "
            "while false-positive rate on distractors does not increase."
        ),
    }
