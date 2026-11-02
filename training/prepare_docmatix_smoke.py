"""Prepare the official 16-example Docmatix multimodal smoke dataset.

Uses the official HuggingFaceM4/Docmatix dataset (zero-shot-exp train split),
downloading genuine document images and question-answer pairs for the
multimodal training compatibility experiment.

Strictly avoids using any private evaluation media (such as the Gojo clip).
"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("lolixcopilot.docmatix_smoke")

DOCMATIX_REPO = "HuggingFaceM4/Docmatix"
DOCMATIX_REVISION = "0725b65616e0e5f6024be10e38ddf8d8c48664fd"
DOCMATIX_CONFIG = "zero-shot-exp"
DOCMATIX_SPLIT = "train"
DOCMATIX_LICENSE = "MIT"

DOCMATIX_ROWS_API = (
    "https://datasets-server.huggingface.co/rows"
    f"?dataset=HuggingFaceM4%2FDocmatix&config={DOCMATIX_CONFIG}&split={DOCMATIX_SPLIT}&offset=0&length=16"
)


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch_docmatix_smoke_subset(
    output_dir: Path,
    max_samples: int = 16,
) -> dict[str, Any]:
    """Download and format the 16-example Docmatix multimodal smoke subset.

    Args:
        output_dir: Directory where images and JSONL manifest will be stored.
        max_samples: Number of samples to prepare (default 16).

    Returns:
        Dictionary summarizing downloaded samples, image paths, and manifest metadata.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "docmatix_smoke_16.jsonl"
    manifest_path = output_dir / "docmatix_smoke_manifest.json"

    logger.info("Fetching Docmatix metadata from %s", DOCMATIX_ROWS_API)
    req = urllib.request.Request(
        DOCMATIX_ROWS_API,
        headers={"User-Agent": "LolixCopilot-DatasetPrep/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        api_data = json.loads(resp.read().decode("utf-8"))

    raw_rows = api_data.get("rows", [])
    if len(raw_rows) < max_samples:
        raise ValueError(
            f"Expected at least {max_samples} rows from Docmatix API, got {len(raw_rows)}"
        )

    formatted_samples: list[dict[str, Any]] = []
    manifest_entries: list[dict[str, Any]] = []

    for idx, item in enumerate(raw_rows[:max_samples]):
        row = item["row"]
        sample_id = f"docmatix_smoke_{idx:02d}"

        # 1. Download image(s) for this sample
        raw_images = row.get("images", [])
        if not raw_images:
            raise ValueError(f"Sample {sample_id} has no images in Docmatix row")

        saved_image_paths: list[str] = []
        image_hashes: list[str] = []

        for img_idx, img_info in enumerate(raw_images[:1]):
            img_url = img_info["src"]
            img_filename = f"{sample_id}_page{img_idx}.png"
            dest_img_path = images_dir / img_filename

            if not dest_img_path.exists() or dest_img_path.stat().st_size == 0:
                img_req = urllib.request.Request(
                    img_url,
                    headers={"User-Agent": "LolixCopilot-DatasetPrep/1.0"},
                )
                with urllib.request.urlopen(img_req, timeout=30) as img_resp:
                    img_bytes = img_resp.read()
                with open(dest_img_path, "wb") as f_out:
                    f_out.write(img_bytes)

            img_hash = calculate_sha256(dest_img_path)
            saved_image_paths.append(str(dest_img_path.resolve()))
            image_hashes.append(img_hash)

        # 2. Extract conversation turns
        texts = row.get("texts", [])
        if not texts:
            raise ValueError(f"Sample {sample_id} has no texts in Docmatix row")

        first_turn = texts[0]
        user_query = first_turn.get("user", "").strip() or "Describe this document."
        assistant_resp = (
            first_turn.get("assistant", "").strip() or "Document information extracted."
        )

        primary_image_path = saved_image_paths[0]

        # 3. Format OpenAI messages for Axolotl / Muse Glimmer with exact image path
        message_record = {
            "id": sample_id,
            "source": DOCMATIX_REPO,
            "revision": DOCMATIX_REVISION,
            "split": DOCMATIX_SPLIT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "path": primary_image_path},
                        {"type": "text", "text": user_query},
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": assistant_resp},
                    ],
                },
            ],
            "images": saved_image_paths,
        }
        formatted_samples.append(message_record)

        manifest_entries.append(
            {
                "id": sample_id,
                "image_files": [Path(p).name for p in saved_image_paths],
                "image_paths": saved_image_paths,
                "image_hashes": image_hashes,
                "user_query_preview": user_query[:80],
                "assistant_resp_preview": assistant_resp[:80],
                "num_turns": len(texts),
            }
        )

    # 4. Write JSONL file
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.writelines(
            json.dumps(sample, ensure_ascii=False) + "\n"
            for sample in formatted_samples
        )

    # 5. Write manifest
    summary = {
        "dataset_name": DOCMATIX_REPO,
        "dataset_revision": DOCMATIX_REVISION,
        "config": DOCMATIX_CONFIG,
        "split": DOCMATIX_SPLIT,
        "license": DOCMATIX_LICENSE,
        "sample_count": len(formatted_samples),
        "jsonl_path": str(jsonl_path.resolve()),
        "jsonl_sha256": calculate_sha256(jsonl_path),
        "images_dir": str(images_dir.resolve()),
        "entries": manifest_entries,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        "Successfully prepared %d Docmatix smoke samples at %s",
        len(formatted_samples),
        jsonl_path,
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    out = Path("training/data/docmatix_smoke")
    res = fetch_docmatix_smoke_subset(out, max_samples=16)
    print(
        f"Prepared {res['sample_count']} samples. JSONL SHA-256: {res['jsonl_sha256']}"
    )
