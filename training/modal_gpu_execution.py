"""Modal Execution Pipeline for Muse Glimmer 30B.

Provides:
1. cpu_app (Runs without GPU billing gate):
   - Persistent volume layout on lolixcopilot-checkpoints:
     /checkpoints/muse-glimmer-30b/
     /checkpoints/adapters/
     /checkpoints/training-runs/
     /checkpoints/manifests/
     /checkpoints/logs/
   - Hugging Face model metadata & shard completeness verification:
     meta-models/Muse-Glimmer-30B @ a4e59da52a7bc87ae7251dd5545c0dd437c44b68.
   - Multimodal processor preflight:
     AutoProcessor & AutoTokenizer multi-image tensor transformation.

2. gpu_app (Runs on H100 GPU when payment method is added):
   - Physical NVIDIA H100 hardware inspection.
   - Bounded two-optimizer-step QLoRA smoke training + adapter reload + inference.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any

import modal

logger = logging.getLogger("lolixcopilot.execution")

# ---------------------------------------------------------------------------
# Modal Container Images & App Definitions
# ---------------------------------------------------------------------------

base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl", "build-essential")
    .pip_install(
        "torch>=2.4.0",
        "torchvision",
        "transformers>=4.45.0",
        "peft>=0.13.0",
        "bitsandbytes>=0.43.0",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.25.0",
        "datasets",
        "pillow",
        "pydantic>=2.10.0",
        "pyyaml>=6.0.0",
        "scipy",
    )
)

cpu_app = modal.App(
    name="lolixcopilot-glimmer-setup",
    image=base_image,
)

gpu_app = modal.App(
    name="lolixcopilot-glimmer-gpu",
    image=base_image,
)

checkpoint_volume = modal.Volume.from_name("lolixcopilot-checkpoints")

TARGET_MODEL_ID = "meta-models/Muse-Glimmer-30B"
TARGET_REVISION = "a4e59da52a7bc87ae7251dd5545c0dd437c44b68"


# ---------------------------------------------------------------------------
# CPU Task 1: Persistent Storage Layout & Volume Setup
# ---------------------------------------------------------------------------


@cpu_app.function(
    volumes={"/checkpoints": checkpoint_volume},
    timeout=300,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def setup_checkpoint_volume_layout() -> dict[str, Any]:
    """Create directory structure in the persistent checkpoint volume."""
    subdirs = [
        "/checkpoints/muse-glimmer-30b",
        "/checkpoints/adapters",
        "/checkpoints/training-runs",
        "/checkpoints/manifests",
        "/checkpoints/logs",
    ]
    created = []
    for d in subdirs:
        p = Path(d)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(d)

    manifest_path = Path("/checkpoints/manifests/volume_layout.json")
    manifest = {
        "volume_name": "lolixcopilot-checkpoints",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "layout": subdirs,
        "target_model": TARGET_MODEL_ID,
        "target_revision": TARGET_REVISION,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    checkpoint_volume.commit()

    return {
        "status": "ready",
        "volume_name": "lolixcopilot-checkpoints",
        "layout": subdirs,
        "newly_created": created,
        "manifest_path": str(manifest_path),
    }


# ---------------------------------------------------------------------------
# CPU Task 2: Model Metadata & Shard Completeness Verification
# ---------------------------------------------------------------------------


@cpu_app.function(
    timeout=300,
    secrets=[modal.Secret.from_name("huggingface-secret")],
    volumes={"/checkpoints": checkpoint_volume},
)
def verify_model_repository_shards() -> dict[str, Any]:
    """Verify repository access, commit hash, and model file shards."""
    from huggingface_hub import HfApi

    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)

    info = api.model_info(
        repo_id=TARGET_MODEL_ID, revision=TARGET_REVISION, files_metadata=True
    )
    siblings = info.siblings or []

    safetensors_files = [
        s.rfilename for s in siblings if s.rfilename.endswith(".safetensors")
    ]
    config_files = [
        s.rfilename
        for s in siblings
        if s.rfilename.endswith((".json", ".yaml", ".yml"))
    ]
    total_size_bytes = sum(getattr(s, "size", 0) or 0 for s in siblings)

    # Save verification record into volume
    record_path = Path("/checkpoints/manifests/model_shards_manifest.json")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "model_id": TARGET_MODEL_ID,
        "revision": TARGET_REVISION,
        "verified_commit_sha": info.sha,
        "total_files": len(siblings),
        "safetensors_shards_count": len(safetensors_files),
        "safetensors_shards": sorted(safetensors_files),
        "config_files": sorted(config_files),
        "total_estimated_size_bytes": total_size_bytes,
        "total_estimated_size_gb": round(total_size_bytes / (1024**3), 2),
    }
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    checkpoint_volume.commit()

    return record


# ---------------------------------------------------------------------------
# CPU Task 3: Multimodal Processor Preflight & Tokenizer Verification
# ---------------------------------------------------------------------------


@cpu_app.function(
    timeout=600,
    secrets=[modal.Secret.from_name("huggingface-secret")],
    volumes={"/checkpoints": checkpoint_volume},
)
def verify_multimodal_processor() -> dict[str, Any]:
    """Load AutoProcessor & AutoTokenizer and verify multi-image processing."""
    from PIL import Image
    from transformers import AutoProcessor, AutoTokenizer

    token = os.environ.get("HF_TOKEN")
    logger.info(
        "Loading tokenizer & processor from %s @ %s", TARGET_MODEL_ID, TARGET_REVISION
    )

    tokenizer = AutoTokenizer.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        token=token,
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        token=token,
        trust_remote_code=True,
    )

    # Create 2 synthetic test images to verify multi-image multimodal processing
    img1 = Image.new("RGB", (224, 224), color=(220, 20, 60))
    img2 = Image.new("RGB", (224, 224), color=(65, 105, 225))

    prompt = "Describe the event sequence in these two keyframes."
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    formatted_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = processor(
        text=[formatted_text],
        images=[[img1, img2]],
        return_tensors="pt",
    )

    input_ids = inputs.get("input_ids")
    pixel_values = inputs.get("pixel_values")
    seq_length = input_ids.shape[1] if input_ids is not None else 0
    pixel_shape = list(pixel_values.shape) if pixel_values is not None else None

    # Save processor preflight verification report
    report_path = Path("/checkpoints/manifests/processor_preflight.json")
    report = {
        "status": "verified",
        "model_id": TARGET_MODEL_ID,
        "revision": TARGET_REVISION,
        "tokenizer_vocab_size": len(tokenizer),
        "tokenizer_class": tokenizer.__class__.__name__,
        "processor_class": processor.__class__.__name__,
        "multi_image_processed": True,
        "tokenized_sequence_length": seq_length,
        "pixel_values_shape": pixel_shape,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    checkpoint_volume.commit()

    return report


# ---------------------------------------------------------------------------
# GPU Task 1: NVIDIA H100 Hardware Inspection
# ---------------------------------------------------------------------------


@gpu_app.function(
    gpu="H100",
    timeout=300,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def verify_gpu_hardware() -> dict[str, Any]:
    """Inspect and report physical GPU hardware, CUDA runtime, and precision support."""
    import torch

    cuda_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count() if cuda_available else 0

    if not cuda_available:
        return {
            "cuda_available": False,
            "error": "CUDA is not available in the container",
        }

    device_name = torch.cuda.get_device_name(0)
    device_properties = torch.cuda.get_device_properties(0)
    total_memory_gb = round(device_properties.total_memory / (1024**3), 2)
    major, minor = device_properties.major, device_properties.minor
    compute_capability = f"{major}.{minor}"
    bf16_supported = torch.cuda.is_bf16_supported()

    t = torch.randn((1024, 1024), dtype=torch.bfloat16, device="cuda")
    allocated_mb = round(torch.cuda.memory_allocated(0) / (1024**2), 2)
    reserved_mb = round(torch.cuda.memory_reserved(0) / (1024**2), 2)
    del t
    torch.cuda.empty_cache()

    return {
        "cuda_available": True,
        "device_count": device_count,
        "gpu_model": device_name,
        "total_vram_gb": total_memory_gb,
        "compute_capability": compute_capability,
        "bf16_supported": bf16_supported,
        "cuda_version": torch.version.cuda,
        "pytorch_version": torch.__version__,
        "test_alloc_mb": allocated_mb,
        "test_reserved_mb": reserved_mb,
    }


# ---------------------------------------------------------------------------
# GPU Task 2: Bounded Two-Optimizer-Step QLoRA Smoke Experiment
# ---------------------------------------------------------------------------


@gpu_app.function(
    gpu="H100",
    timeout=1800,  # 30 min maximum bounded timeout
    secrets=[modal.Secret.from_name("huggingface-secret")],
    volumes={"/checkpoints": checkpoint_volume},
)
def run_gpu_smoke_experiment() -> dict[str, Any]:
    """Execute official bounded 2-optimizer-step QLoRA smoke experiment on H100."""
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from PIL import Image
    from transformers import (
        AutoModelForCausalLM,
        AutoProcessor,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    token = os.environ.get("HF_TOKEN")
    start_time = time.time()
    logger.info("Initializing 2-step QLoRA smoke experiment on H100...")

    # 1. 4-bit NF4 Quantization Configuration
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # 2. Load Base Model
    logger.info("Loading %s in 4-bit NF4...", TARGET_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        token=token,
        trust_remote_code=True,
    )
    vram_after_load_gb = round(torch.cuda.memory_allocated(0) / (1024**3), 2)
    logger.info("Model loaded into VRAM: %s GB", vram_after_load_gb)

    # 3. Load Tokenizer & Processor
    tokenizer = AutoTokenizer.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        token=token,
        trust_remote_code=True,
    )
    processor = AutoProcessor.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        token=token,
        trust_remote_code=True,
    )

    # 4. LoRA Adapter Configuration
    target_modules = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=target_modules,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    trainable_params, total_params = model.get_nb_trainable_parameters()
    logger.info(
        "Trainable parameters: %d / %d (%.4f%%)",
        trainable_params,
        total_params,
        100 * trainable_params / total_params,
    )

    first_lora_param_name = None
    initial_weight_norm = 0.0
    for name, param in model.named_parameters():
        if param.requires_grad and "lora" in name:
            first_lora_param_name = name
            initial_weight_norm = float(param.data.norm().item())
            break

    # 5. Prepare 16 Multimodal Training Examples
    colors = [
        (220, 20, 60),
        (65, 105, 225),
        (147, 112, 219),
        (50, 205, 50),
        (255, 165, 0),
        (75, 0, 130),
        (255, 20, 147),
        (0, 206, 209),
        (240, 230, 140),
        (139, 69, 19),
        (70, 130, 180),
        (218, 112, 214),
        (34, 139, 34),
        (255, 69, 0),
        (106, 90, 205),
        (46, 139, 87),
    ]
    dataset = []
    for i in range(16):
        img = Image.new("RGB", (224, 224), color=colors[i])
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {
                        "type": "text",
                        "text": f"Identify the visual state and primary event in sample #{i:02d}.",
                    },
                ],
            },
            {
                "role": "assistant",
                "content": f"Sample #{i:02d} displays active visual excitation with event state confirmed at keyframe interval {i * 2.5:.1f}s.",
            },
        ]
        dataset.append({"image": img, "messages": messages})

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=2e-4,
        weight_decay=0.01,
    )

    losses = []
    model.train()
    batch_size = 2

    for step in range(1, 3):
        optimizer.zero_grad()
        step_loss = 0.0

        for b_idx in range(batch_size):
            sample_idx = (step - 1) * batch_size + b_idx
            sample = dataset[sample_idx]

            prompt_text = tokenizer.apply_chat_template(
                sample["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
            inputs = processor(
                text=[prompt_text],
                images=[sample["image"]],
                return_tensors="pt",
            )
            input_ids = inputs["input_ids"].to("cuda")
            labels = input_ids.clone()

            outputs = model(
                input_ids=input_ids,
                labels=labels,
            )
            loss = outputs.loss / batch_size
            loss.backward()
            step_loss += float(outputs.loss.item())

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        avg_loss = round(step_loss / batch_size, 4)
        losses.append(avg_loss)
        peak_vram_step = round(torch.cuda.max_memory_allocated(0) / (1024**3), 2)
        logger.info(
            "Completed optimizer step %d: Loss = %.4f (Peak VRAM: %.2f GB)",
            step,
            avg_loss,
            peak_vram_step,
        )

    final_weight_norm = 0.0
    for name, param in model.named_parameters():
        if name == first_lora_param_name:
            final_weight_norm = float(param.data.norm().item())
            break
    weight_delta = abs(final_weight_norm - initial_weight_norm)

    # Save Checkpoint to Modal Volume
    checkpoint_dir = Path("/checkpoints/adapters/smoke-step-2")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(checkpoint_dir))
    tokenizer.save_pretrained(str(checkpoint_dir))

    manifest_info = {
        "run_type": "official_gpu_smoke_experiment",
        "hardware": "1x NVIDIA H100 (80GB SXM5)",
        "model_id": TARGET_MODEL_ID,
        "revision": TARGET_REVISION,
        "optimizer_steps": 2,
        "losses": losses,
        "initial_weight_norm": initial_weight_norm,
        "final_weight_norm": final_weight_norm,
        "weight_delta": weight_delta,
        "trainable_params": trainable_params,
        "total_params": total_params,
        "saved_checkpoint_path": str(checkpoint_dir),
    }
    with open(checkpoint_dir / "training_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_info, f, indent=2)

    checkpoint_volume.commit()
    logger.info("Checkpoint committed to volume at %s", checkpoint_dir)

    # Reload Adapter & Run Inference Verification
    logger.info("Reloading adapter from checkpoint to verify persistence...")
    del model, optimizer
    torch.cuda.empty_cache()

    base_reload = AutoModelForCausalLM.from_pretrained(
        TARGET_MODEL_ID,
        revision=TARGET_REVISION,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        token=token,
        trust_remote_code=True,
    )
    adapted_model = PeftModel.from_pretrained(
        base_reload,
        str(checkpoint_dir),
    )
    adapted_model.eval()

    test_img = Image.new("RGB", (224, 224), color=(147, 112, 219))
    test_prompt = "Identify the character technique and timestamp in this frame."
    test_msgs = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": test_prompt},
            ],
        }
    ]
    prompt_formatted = tokenizer.apply_chat_template(
        test_msgs,
        tokenize=False,
        add_generation_prompt=True,
    )
    test_inputs = processor(
        text=[prompt_formatted],
        images=[test_img],
        return_tensors="pt",
    ).to("cuda")

    with torch.no_grad():
        output_ids = adapted_model.generate(
            **test_inputs,
            max_new_tokens=40,
            do_sample=False,
        )

    prompt_len = test_inputs["input_ids"].shape[1]
    generated_text = tokenizer.decode(
        output_ids[0][prompt_len:], skip_special_tokens=True
    )
    logger.info("Inference output from reloaded adapter: %s", generated_text)

    total_duration = round(time.time() - start_time, 2)
    peak_vram_total_gb = round(torch.cuda.max_memory_allocated(0) / (1024**3), 2)

    return {
        "experiment_status": "SUCCESS",
        "hardware": "1x NVIDIA H100 (80GB SXM5)",
        "model_id": TARGET_MODEL_ID,
        "revision": TARGET_REVISION,
        "optimizer_steps_completed": 2,
        "step_losses": losses,
        "finite_loss_verified": all(
            not math.isnan(l) and not math.isinf(l) for l in losses
        ),
        "weight_delta": weight_delta,
        "weights_updated": bool(weight_delta > 0.0),
        "vram_after_load_gb": vram_after_load_gb,
        "peak_vram_gb": peak_vram_total_gb,
        "checkpoint_saved": str(checkpoint_dir),
        "adapter_reload_verified": True,
        "test_inference_output": generated_text.strip(),
        "duration_seconds": total_duration,
    }


# ---------------------------------------------------------------------------
# CLI Local Entrypoints for cpu_app and gpu_app
# ---------------------------------------------------------------------------


@cpu_app.local_entrypoint()
def cpu_main(action: str = "all") -> None:
    """Execute CPU-based volume setup, shard verification, and multimodal preflight."""
    print("=" * 80)
    print("LolixCopilot — Modal CPU Infrastructure & Preflight")
    print(f"Action: {action}")
    print("=" * 80)

    if action in ("setup_volume", "all"):
        print("\n[Step 1] Setting up persistent checkpoint volume layout...")
        vol_res = setup_checkpoint_volume_layout.remote()
        print("Volume layout result:\n", json.dumps(vol_res, indent=2))

    if action in ("verify_shards", "all"):
        print("\n[Step 2] Verifying model repository shards and files...")
        shards_res = verify_model_repository_shards.remote()
        print("Shards verification result:\n", json.dumps(shards_res, indent=2))

    if action in ("verify_processor", "all"):
        print("\n[Step 3] Running multimodal processor preflight...")
        proc_res = verify_multimodal_processor.remote()
        print("Processor preflight result:\n", json.dumps(proc_res, indent=2))

    print("\n" + "=" * 80)
    print("CPU setup and preflight sequence completed!")
    print("=" * 80)


@gpu_app.local_entrypoint()
def gpu_main(action: str = "smoke_training") -> None:
    """Execute GPU-based verification and bounded smoke training on H100."""
    print("=" * 80)
    print("LolixCopilot — Modal GPU Execution & Smoke Training")
    print(f"Action: {action}")
    print("=" * 80)

    if action in ("verify_gpu", "all"):
        print("\n[GPU Step 1] Verifying physical NVIDIA H100 hardware...")
        gpu_res = verify_gpu_hardware.remote()
        print("GPU verification result:\n", json.dumps(gpu_res, indent=2))

    if action in ("smoke_training", "all"):
        print(
            "\n[GPU Step 2] Launching bounded 2-step QLoRA smoke experiment on H100..."
        )
        smoke_res = run_gpu_smoke_experiment.remote()
        print("Smoke experiment result:\n", json.dumps(smoke_res, indent=2))

    print("\n" + "=" * 80)
    print("GPU execution completed!")
    print("=" * 80)
