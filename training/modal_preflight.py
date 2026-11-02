"""Modal CPU Preflight Verification for Hugging Face Environment & Model Access.

Performs:
1. Safe verification of HF_TOKEN existence inside the Modal container (no credentials exposed).
2. Authenticated identity check with Hugging Face via whoami().
3. Model metadata access check for meta-models/Muse-Glimmer-30B without downloading weights.
4. Programmatic Modal Volume existence check for lolixcopilot-checkpoints without auto-creation.
5. Structured PASS/FAIL reporting and timing telemetry.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

import modal

logger = logging.getLogger("lolixcopilot.preflight")

app = modal.App("lolixcopilot-preflight")

preflight_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "huggingface_hub>=0.25.0",
    "requests>=2.31.0",
)


@app.function(
    image=preflight_image,
    cpu=1.0,
    memory=1024,
    timeout=120,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def verify_huggingface_environment() -> dict[str, Any]:
    """Execute authenticated preflight checks in remote Modal CPU container."""
    from huggingface_hub import HfApi  # type: ignore[import-not-found]
    from huggingface_hub.utils import (  # type: ignore[import-not-found]
        GatedRepoError,
        RepositoryNotFoundError,
    )

    start_time = time.time()

    # 1. Verify token presence safely (NEVER log or return the token value)
    token = os.environ.get("HF_TOKEN")
    token_present = bool(token and token.strip())
    if not token_present:
        return {
            "token_present": False,
            "auth_status": "MISSING_TOKEN",
            "account": None,
            "model_access_status": "DENIED",
            "model_id": "meta-models/Muse-Glimmer-30B",
            "details": "HF_TOKEN environment variable is not present or empty in huggingface-secret.",
            "duration_seconds": round(time.time() - start_time, 2),
        }

    api = HfApi(token=token)

    # 2. Authenticated Identity Check
    auth_status = "FAILED"
    account_info: dict[str, Any] = {}
    try:
        whoami_res = api.whoami()
        auth_status = "AUTHENTICATED"
        account_info = {
            "name": whoami_res.get("name", "unknown"),
            "type": whoami_res.get("type", "user"),
            "is_pro": whoami_res.get("isPro", False),
        }
    except Exception as exc:  # noqa: BLE001
        safe_msg = str(exc).replace(token, "[REDACTED]") if token else str(exc)
        return {
            "token_present": True,
            "auth_status": "INVALID_TOKEN",
            "account": None,
            "model_access_status": "UNAUTHORIZED",
            "model_id": "meta-models/Muse-Glimmer-30B",
            "details": f"Token verification failed: {safe_msg}",
            "duration_seconds": round(time.time() - start_time, 2),
        }

    # 3. Model Metadata Access Check
    target_model = "meta-models/Muse-Glimmer-30B"
    target_revision = "a4e59da52a7bc87ae7251dd5545c0dd437c44b68"
    model_access_status = "UNKNOWN"
    metadata: dict[str, Any] = {}

    try:
        info = api.model_info(repo_id=target_model, revision=target_revision)
        model_access_status = "AUTHORIZED"
        siblings = [s.rfilename for s in (info.siblings or [])]
        metadata = {
            "sha": getattr(info, "sha", None),
            "target_revision": target_revision,
            "pipeline_tag": getattr(info, "pipeline_tag", None),
            "tags": [
                t for t in (getattr(info, "tags", []) or []) if isinstance(t, str)
            ][:10],
            "gated": getattr(info, "gated", False),
            "config_files": [
                f for f in siblings if f.endswith((".json", ".yaml", ".yml"))
            ],
            "total_files": len(siblings),
            "siblings": siblings,
        }
    except GatedRepoError as gre:
        safe_msg = str(gre).replace(token, "[REDACTED]") if token else str(gre)
        model_access_status = "GATED_ACTION_REQUIRED"
        metadata = {"error": f"Gated repository access required: {safe_msg}"}
    except RepositoryNotFoundError:
        model_access_status = "NOT_FOUND"
        metadata = {
            "error": "Repository not found or token lacks read scope for this repository."
        }
    except Exception as exc:  # noqa: BLE001
        safe_msg = str(exc).replace(token, "[REDACTED]") if token else str(exc)
        model_access_status = "ACCESS_DENIED"
        metadata = {"error": f"Metadata access failed: {safe_msg}"}

    duration = round(time.time() - start_time, 2)
    return {
        "token_present": True,
        "auth_status": auth_status,
        "account": account_info,
        "model_access_status": model_access_status,
        "model_id": target_model,
        "metadata": metadata,
        "duration_seconds": duration,
    }


def check_volume_status(
    volume_name: str = "lolixcopilot-checkpoints",
) -> dict[str, Any]:
    """Check existence of volume via Modal SDK without creating it."""
    try:
        volumes = modal.Volume.objects.list()
        matching = [v for v in volumes if getattr(v, "name", None) == volume_name]
        if matching:
            return {
                "name": volume_name,
                "exists": True,
                "status": "AVAILABLE",
                "details": f"Volume exists in environment (created: {getattr(matching[0], 'created_at', 'unknown')})",
            }
        return {
            "name": volume_name,
            "exists": False,
            "status": "MISSING",
            "details": "Volume does not exist. Must be created or authorized prior to training.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": volume_name,
            "exists": False,
            "status": "LOOKUP_ERROR",
            "details": f"Volume check error: {exc}",
        }


def format_preflight_report(
    hf_result: dict[str, Any],
    vol_result: dict[str, Any],
) -> str:
    """Format structured PASS/FAIL preflight report."""
    lines: list[str] = [
        "=" * 80,
        "LolixCopilot — Modal CPU Preflight Verification",
        "=" * 80,
    ]

    # Token check
    if hf_result.get("token_present"):
        lines.append(
            "[PASS] Secret HF_TOKEN: Variable detected in container (value protected)"
        )
    else:
        lines.append("[FAIL] Secret HF_TOKEN: Missing or empty in huggingface-secret")

    # Auth check
    if hf_result.get("auth_status") == "AUTHENTICATED":
        acc = hf_result.get("account") or {}
        lines.append(
            f"[PASS] Hugging Face Identity: Authenticated as '{acc.get('name')}' (type: {acc.get('type')})"
        )
    else:
        lines.append(
            f"[FAIL] Hugging Face Identity: Authentication failed ({hf_result.get('details')})"
        )

    # Model Access check
    model_status = hf_result.get("model_access_status")
    meta = hf_result.get("metadata") or {}
    if model_status == "AUTHORIZED":
        lines.append(
            f"[PASS] Model Access ({hf_result.get('model_id')}): AUTHORIZED (SHA: {meta.get('sha', 'unknown')[:10]}...)"
        )
        if meta.get("config_files"):
            lines.append(
                f"       Configuration files found: {', '.join(meta['config_files'][:5])}"
            )
    elif model_status == "GATED_ACTION_REQUIRED":
        lines.append(
            f"[WARN] Model Access ({hf_result.get('model_id')}): GATED_ACTION_REQUIRED"
        )
        lines.append(f"       Action: {meta.get('error')}")
    else:
        lines.append(
            f"[FAIL] Model Access ({hf_result.get('model_id')}): {model_status}"
        )
        if meta.get("error"):
            lines.append(f"       Details: {meta.get('error')}")

    # Volume check
    if vol_result.get("exists"):
        lines.append(
            f"[PASS] Modal Checkpoint Volume ({vol_result.get('name')}): AVAILABLE"
        )
    else:
        lines.append(
            f"[INFO] Modal Checkpoint Volume ({vol_result.get('name')}): MISSING"
        )
        lines.append(f"       Notice: {vol_result.get('details')}")

    lines.append("=" * 80)
    lines.append(
        f"Preflight Execution Time: {hf_result.get('duration_seconds', 0.0)}s (CPU only, 0 GPUs used)"
    )
    lines.append("=" * 80)

    return "\n".join(lines)


@app.local_entrypoint()
def main() -> None:
    """Execute remote CPU preflight and print report."""
    print("Launching CPU-only Modal preflight function...")
    hf_result = verify_huggingface_environment.remote()
    vol_result = check_volume_status("lolixcopilot-checkpoints")
    report = format_preflight_report(hf_result, vol_result)
    print(report)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--local-volume-only":
        print(check_volume_status("lolixcopilot-checkpoints"))
    else:
        main()
