# LolixCopilot — Modal Architecture, Credit Consumption & Training Specification

**Document Version:** 1.0.0
**Status:** Approved Architecture & Implementation Spec
**Target:** Meta Global AI Developer Hackathon & Golixco Engineering
**Scope:** Modal CPU Media Worker, Muse Glimmer 30B QLoRA Training Pipeline, Baseten Integration Compatibility, and $100 Credit Pool Optimization.

---

## 1. Executive Summary

LolixCopilot leverages **Modal** as an asynchronous compute engine for two distinct, high-impact responsibilities:
1. **Serverless CPU Media Processing Worker (`workers/media_worker.py`):**
   - High-throughput video metadata probing via `ffprobe`.
   - Bounded 16kHz mono audio extraction (WAV / MP3) required for multimodal intelligence.
   - Timestamped keyframe and scene transition extraction.
   - Zero-downtime integration with private AWS S3 using short-lived presigned URLs.
2. **Specialist Training Pipeline (`training/train_glimmer_qlora.py`):**
   - Muse Glimmer 30B parameter-efficient fine-tuning (QLoRA 4-bit) on a single NVIDIA H100 (80GB).
   - Event recognition and temporal synchronization dataset based on *Jujutsu Kaisen* combat sequences.
   - Resumable training loop backed by durable Modal Volumes (`modal.Volume`).

---

## 2. Published Modal Unit Rates

Based on Modal's current published rate schedule:

| Compute / Storage Resource | Unit Rate (USD) | Effective Hourly / Monthly Rate |
| :--- | :--- | :--- |
| **CPU Physical Core** | $0.000024 / core-sec | $0.0864 / core-hour |
| **System Memory (RAM)** | $0.0000025 / GiB-sec | $0.0090 / GiB-hour |
| **Modal Volume Storage** | $0.150000 / GB-month | $0.0050 / GB-day |
| **NVIDIA H100 (80GB SXM5)**| $0.001097 / sec | **$3.95 / hour** |
| **NVIDIA A100 (80GB)** | $0.000764 / sec | $2.75 / hour |
| **NVIDIA A100 (40GB)** | $0.000583 / sec | $2.10 / hour |
| **NVIDIA L40S (48GB)** | $0.000542 / sec | $1.95 / hour |
| **NVIDIA A10G (24GB)** | $0.000306 / sec | $1.10 / hour |
| **Network Egress** | 10 GB / month free | $0.10 / GB thereafter |

---

## 3. CPU Media Processing Cost Model

Each Modal CPU worker container is configured with **2 CPU cores** and **2048 MiB (2 GiB) of RAM**:
$$\text{Cost per Container-Second} = (2 \times \$0.000024) + (2 \times \$0.0000025) = \$0.000053\text{ / second} \quad (\approx \$0.1908\text{ / hour})$$

### 3.1 Per-Operation Costs

| Media Operation | Average Wall-Clock Latency | Unit Compute Cost | Operations per $1.00 USD |
| :--- | :---: | :---: | :---: |
| **Video Metadata Probe (`probe_video_metadata`)** | 3.0 seconds | **$0.000159** | 6,289 operations |
| **Audio Track Extraction (`extract_audio_track`)** | 12.0 seconds | **$0.000636** | 1,572 operations |
| **Frame Extraction (5 moments, `extract_frames`)** | 8.0 seconds | **$0.000424** | 2,358 operations |
| **Scene Keyframe Cuts (10 cuts, `extract_scene_keyframes`)**| 15.0 seconds | **$0.000795** | 1,257 operations |

**Conclusion:** Offloading 1,000 full video upload workflows (probe + audio extraction + 5 thumbnail cuts) consumes **~$1.22 total** (< 1.3% of our $100 credit pool).

---

## 4. Muse Glimmer 30B QLoRA Training Cost Model

### 4.1 Memory & Hardware Justification
- **Full-Precision (BF16) 30B Model:** Requires ~60GB purely for model weights. Training requires 8x H100 (80GB) under FSDP2 ($31.60/hr, burning $63.20 in 2 hours).
- **QLoRA (4-bit NF4 Quantization):**
  - Base model weights quantized to 4-bit: **~17.5 GB VRAM**.
  - LoRA Adapter ($r=16, \alpha=32$, all linear attention & MLP layers): **~0.6 GB**.
  - Activations + Paged AdamW 8-bit Optimizer states (sequence length 4096, micro-batch size 1): **~14.4 GB**.
  - **Total Peak VRAM:** **~32.5 GB**, fitting comfortably on a single **NVIDIA H100 (80GB SXM5)** at **$3.95/hr**.

### 4.2 Training Step & Time Calculation
- **Dataset Size:** 600 curated anime combat & narrative demonstration samples.
- **Batch Schedule:** Micro-batch size 1, gradient accumulation steps 8 $\implies$ effective batch size 8.
- **Steps per Epoch:** $600 / 8 = 75\text{ steps/epoch}$.
- **3 Epochs:** $75 \times 3 = 225\text{ total optimization steps}$.
- **Throughput:** ~2.0 seconds per step on H100 $\implies 450\text{ seconds}$ (~7.5 minutes compute).
- **Setup & Evaluation Overhead:** Container image initialization, Hugging Face weight loading, evaluation checkpoints $\implies$ **~45 to 60 minutes wall-clock execution**.
- **Max Budgeted Function Timeout:** 7,200 seconds (2.0 hours).

### 4.3 Training Cost Breakdown
| Phase | Duration / Size | Hardware | Unit Rate | Projected Cost |
| :--- | :--- | :--- | :--- | :--- |
| **QLoRA Fine-Tuning** | 2.0 hours (capped) | 1 × NVIDIA H100 (80GB) | $3.95 / hr | **$7.90** |
| **Model Evaluation** | 0.5 hours | 1 × NVIDIA A100 (40GB) | $2.10 / hr | **$1.05** |
| **Checkpoint Storage (Modal Volume)** | 20 GB for 14 days | Distributed Modal Volume | $0.15 / GB-mo | **$1.40** |
| **Total Training Experiment Cost** | — | — | — | **$10.35** |

---

## 5. $100 Modal Credit Pool Allocation

| Allocation Category | Budgeted Amount | Share of $100 Pool | Operational Buffer |
| :--- | :---: | :---: | :--- |
| **CPU Media Workers (1,000+ uploads)** | $2.50 | 2.5% | Thousands of clips |
| **Muse Glimmer QLoRA Training Experiment** | $7.90 | 7.9% | 1 complete 3-epoch H100 run |
| **Model Evaluation & Checkpoint Push** | $1.50 | 1.5% | Evaluation benchmark suite |
| **Durable Volume Checkpoint Storage** | $1.50 | 1.5% | 20 GB for ~1 month |
| **Contingency / Safety Reserve** | **$86.60** | **86.6%** | Protected buffer against overspend |
| **Total** | **$100.00** | **100.0%** | **Safe, bounded, zero waste** |

---

## 6. Compatibility Review with Baseten Integration

LolixCopilot's active multimodal intelligence architecture utilizes **Baseten** as the primary inference provider. Modal and Baseten complement each other without friction:

```
[User Browser]
      │
      ▼ presigned S3 PUT
[Private AWS S3]
      │
      ├─────────────────────────────────────────┐
      │ (presigned GET URL)                     │ (presigned GET URL)
      ▼                                         ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│     MODAL CPU WORKER POOL       │   │      BASETEN INFERENCE POOL     │
│                                 │   │                                 │
│ 1. Probe duration, FPS, codecs  │   │ Model: meta-models/muse-spark-  │
│ 2. Extract 16kHz mono WAV       │   │        open-1026                │
│    (Uploaded to private S3)     │   │                                 │
│ 3. Extract moment keyframes     │   │ Input: video_url + audio_url    │
└────────────────┬────────────────┘   └────────────────┬────────────────┘
                 │                                     │
                 ▼                                     ▼
         [Extracted Audio URL] ────────────────> [Multimodal Reasoning]
                                                       │
                                                       ▼
                                            [Structured Blueprint JSON]
```

### Key Compatibility Findings:
1. **Audio Track Ingestion:** Muse Spark Open on Baseten bypasses video audio tracks. Modal's `extract_audio_track` generates the exact 16kHz mono WAV file needed for Baseten's `audio_url` content part.
2. **Ephemeral S3 Tokens:** Both Modal workers and Baseten ingest short-lived presigned S3 URLs, ensuring master AWS credentials are never exposed or passed across networks.
3. **Fail-Closed Fallback:** In `backend/app/services/modal_media_service.py`, if Modal workers are unreachable, media processing falls back to `LocalMediaProcessingService` automatically.

---

## 7. Safety, Cost Controls & Safeguards

1. **Strict Function Timeouts:**
   - Probing: `timeout=60`
   - Audio extraction: `timeout=90`
   - Training: `timeout=7200` (hard 2-hour cap)
2. **Resumable Training via Modal Volumes:**
   - `modal.Volume.from_name("lolixcopilot-checkpoints", create_if_missing=True)`
   - Preemption-safe checkpoint commits (`volume.commit()`)
   - `single_use_containers=True` ensures clean recovery from interruptions.
3. **Zero Idle Container Burn:**
   - Functions scale to 0 when not receiving requests. No persistent GPU container reservation fees.

---

## 8. Live Preflight Telemetry & Multimodal Compatibility

### 8.1 Modal Remote CPU Preflight Telemetry
- **Invocation:** `modal run training/modal_preflight.py`
- **Container Environment:** `modal.Image.debian_slim(python_version="3.11")`, CPU: 1.0 core, Memory: 1024 MiB
- **Wall-Clock Duration:** 0.35 seconds execution time (0 GPUs, zero billable GPU credits)
- **Modal App Run URL:** `https://modal.com/apps/golixco40/main/ap-i8v0okYNBc7uW0gbQUWtlf`
- **Secret Detection:** `HF_TOKEN` detected inside container environment (value protected and never logged)
- **Hugging Face Identity:** Authenticated as user `'Golixco'`
- **Target Repository:** `meta-models/Muse-Glimmer-30B` -> **AUTHORIZED** (Commit SHA: `cec94fcfd6...`, verified files: `config.json`, `generation_config.json`, `model.safetensors.index.json`, `processor_config.json`, `.eval_results/mmi.yaml`)
- **Volume Inspection:** `lolixcopilot-checkpoints` verified as **MISSING** (inspected safely without auto-creating to preserve storage quotas)

### 8.2 Muse Glimmer Multimodal Compatibility Verification
- **Architecture:** Dense text decoder paired with a frozen ViT-G/14 vision perception encoder (~1.8B parameters), repeating `[local, local, local, global]` attention blocks.
- **Trainable vs Frozen Modules:**
  - ViT-G/14 vision encoder: **FROZEN** (`freeze_vision_tower: true`)
  - Trainable LoRA targets: Attention projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`), MLP SwiGLU (`gate_proj`, `up_proj`, `down_proj`), and `multi_modal_projector`
- **Input Formatting:** Multi-image inputs formatted as OpenAI Messages schema (`messages` array with typed `{"type": "image", "path": ...}` content blocks followed by text instructions).
- **Critical Packing Rules:** `sample_packing: false` and `eval_sample_packing: false` are mandatory to prevent spatial 2D token cross-contamination.
- **Hardware Profile:** Single NVIDIA H100 (80GB SXM5) provides ~32.5 GB peak VRAM in NF4 QLoRA, leaving ~47.5 GB headroom for sequence context and activation caching.
