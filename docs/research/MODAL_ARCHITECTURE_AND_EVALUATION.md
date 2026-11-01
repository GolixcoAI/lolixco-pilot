# LolixCopilot — Modal Architecture Design & Cost Evaluation

**Document Version:** 1.0.0
**Target:** Meta Global AI Developer Hackathon & Golixco Production Roadmap
**Scope:** Distributed FFmpeg preprocessing, asynchronous media probing, audio extraction, Muse Spark Open inference comparison, and Muse Glimmer 30B QLoRA fine-tuning feasibility under our $100 Modal credit pool.

---

## 1. Executive Summary

LolixCopilot requires heavy media computation (video validation, metadata probing, audio extraction, keyframe sampling) and multimodal inference. To maintain high throughput and minimize costs, LolixCopilot separates **stateless web serving** (FastAPI on Modal CPU / Container) from **asynchronous media processing workers** and **multimodal intelligence**.

Key Architectural Conclusions:
1. **FFmpeg & Audio Extraction:** Bounded CPU-based Modal functions (`modal.Function`) running Debian with FFmpeg binaries provide fast, low-cost (fraction of a cent per clip) media probing and audio extraction without GPU overhead.
2. **Modal Credit Pool Assessment ($100 Pool):**
   - **CPU Media Workers:** Consumes < $2.00 across 1,000+ clip conversions.
   - **Muse Glimmer 30B Fine-Tuning:** Feasible via **QLoRA (4-bit frozen base + rank-16 adapter) on a single Nvidia H100 (80GB)** at $3.95/hr. A 2-hour SFT run costs **~$7.90**, safely within our $100 credit pool (< 10% budget). Full-parameter FSDP2 on 8x H100 ($31.60/hr) is cost-prohibitive for the hackathon.
   - **Inference Hosting:** Baseten serves as the primary inference provider (zero cold start, warm serverless pool), while Modal serves as our asynchronous pipeline engine.

---

## 2. Modal Media Processing Pipeline

```
  [Browser Direct Upload]
             │
             ▼ (presigned PUT)
    [Private AWS S3]
             │
   (presigned GET URL)
             ▼
┌─────────────────────────────────────────────────────────────┐
│                    MODAL CPU WORKER POOL                    │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │  FFmpeg Probe Worker  │       │ Audio Extract Worker  │  │
│  │  • Container: Debian  │       │ • 16kHz Mono WAV      │  │
│  │  • Resolution/FPS/Dur │       │ • Normalized loudness │  │
│  │  • Keyframe offsets   │       │ • Short-lived S3 PUT  │  │
│  └───────────┬───────────┘       └───────────┬───────────┘  │
└──────────────┼───────────────────────────────┼──────────────┘
               ▼                               ▼
       [Verified Media]              [Temporary Audio URL]
               │                               │
               └───────────────┬───────────────┘
                               ▼
            [Multimodal Inference (Baseten / Meta)]
```

### 2.1 FFmpeg Video Preprocessing Worker

```python
import modal

app = modal.App("lolixcopilot-media-processing")

# Container image with ffmpeg, ffprobe, and python-ffmpeg
media_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "curl")
    .pip_install("ffmpeg-python", "boto3", "pydantic")
)


@app.function(
    image=media_image,
    cpu=2.0,
    memory=2048,
    timeout=60,
    secrets=[modal.Secret.from_name("aws-s3-credentials")],
)
def probe_video_metadata(presigned_url: str) -> dict:
    """Probes media container with ffprobe directly from presigned S3 stream."""
    import ffmpeg

    probe = ffmpeg.probe(presigned_url)
    video_stream = next(
        (s for s in probe["streams"] if s["codec_type"] == "video"), None
    )
    audio_stream = next(
        (s for s in probe["streams"] if s["codec_type"] == "audio"), None
    )

    duration = float(probe["format"].get("duration", 0.0))
    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "has_audio": audio_stream is not None,
        "codec": video_stream.get("codec_name") if video_stream else None,
    }
```

### 2.2 Audio Extraction Worker

Muse Spark Open requires separate audio input because its video encoder does not ingest audio tracks. The audio extraction worker converts video audio to a compact 16kHz mono WAV format:

```python
@app.function(
    image=media_image,
    cpu=2.0,
    memory=2048,
    timeout=90,
    secrets=[modal.Secret.from_name("aws-s3-credentials")],
)
def extract_audio_track(video_presigned_url: str, output_s3_key: str) -> str:
    """Extracts audio to 16kHz mono WAV, uploads back to private S3, returns key."""
    import subprocess
    import tempfile
    import boto3

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_wav:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_presigned_url,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            tmp_wav.name,
        ]
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # Upload back to private S3 bucket
        s3 = boto3.client("s3")
        s3.upload_file(
            tmp_wav.name, "lolixcopilot-media-247673029886-ap-south-1", output_s3_key
        )

    return output_s3_key
```

### 2.3 Frame Extraction & Timestamp Tracking

For fine-grained event and scene transition recognition:
- Extracts I-frames / scene changes: `ffmpeg -i input.mp4 -vf "select='gt(scene,0.3)',showinfo" -vsync vfr frames/%04d.jpg`
- Tracks exact presentation timestamps (PTS) to associate each representative frame with its timecode in the `EditingBlueprint`.

---

## 3. Muse Glimmer 30B Fine-Tuning Feasibility on Modal

Meta's official documentation (`dev.meta.ai/docs/muse-glimmer/post-training`) specifies training profiles for **Muse Glimmer 30B** (`meta-models/Muse-Glimmer-30B`).

### 3.1 Hardware & Framework Evaluation

| Fine-Tuning Method | Framework | Required Hardware | Modal Rate | 2-Hour Cost | $100 Pool Feasibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **QLoRA (4-bit)** | Axolotl / TRL | **1 × Nvidia H100 (80GB)** | **$3.95 / hr** | **~$7.90** | **100% Feasible (Recommended)** |
| **BF16 LoRA** | Axolotl (FSDP2) | 8 × Nvidia H100 (80GB) | $31.60 / hr | ~$63.20 | Marginal (>60% of pool) |
| **Full FSDP2** | Axolotl | 8 × Nvidia H100 (80GB) | $31.60 / hr | ~$94.80 (3h) | High Risk (Exhausts pool) |

### 3.2 Modal QLoRA Training Configuration

Using Modal Volumes (`modal.Volume`) to persist Hugging Face cache and training datasets:

```python
training_image = modal.Image.from_registry(
    "winglian/axolotl:v0.19.0-py3.11-cu124-20241015"
).pip_install("bitsandbytes>=0.43.0", "peft", "transformers", "accelerate")

volume = modal.Volume.from_name("lolixcopilot-model-checkpoints")


@app.function(
    image=training_image,
    gpu="H100",
    timeout=7200,  # 2 hours max
    volumes={"/checkpoints": volume},
    secrets=[modal.Secret.from_name("hf-token"), modal.Secret.from_name("wandb-token")],
)
def train_glimmer_qlora(dataset_path: str):
    """Executes Axolotl QLoRA on Muse Glimmer 30B."""
    import subprocess

    cmd = ["accelerate", "launch", "-m", "axolotl.cli.train", "/config/qlora_30b.yml"]
    subprocess.run(cmd, check=True)
    volume.commit()
```

### 3.3 Training Hyperparameters (Axolotl)
- **Base Model:** `meta-models/Muse-Glimmer-30B`
- **Adapter:** LoRA rank $r=16$, alpha $\alpha=32$, target modules `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- **Quantization:** 4-bit NormalFloat (NF4), double quant enabled
- **Optimizer:** Paged AdamW 8-bit (`paged_adamw_8bit`)
- **Batch Size:** Micro-batch size 1, gradient accumulation steps 8 (effective batch size 8)
- **Context Length:** 4,096 tokens
- **Epochs:** 3 epochs on 600 curated anime event demonstrations

---

## 4. Modal Credit Budget Breakdown

With our **$100 Modal credit pool**:

| Workload | Hardware | Expected Usage | Hourly Rate | Total Cost | % of $100 Pool |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FFmpeg Media Probing** | 2 CPU, 2GB RAM | 500 clips @ 3s avg | $0.09 / hr | $0.04 | < 0.1% |
| **Audio Extraction (16kHz WAV)** | 2 CPU, 2GB RAM | 200 clips @ 15s avg | $0.09 / hr | $0.08 | < 0.1% |
| **Frame Extraction (Scene Cuts)**| 4 CPU, 4GB RAM | 100 clips @ 20s avg | $0.18 / hr | $0.10 | < 0.1% |
| **Muse Glimmer QLoRA SFT** | 1 × Nvidia H100 (80GB) | 2.0 hours | $3.95 / hr | **$7.90** | **7.9%** |
| **Model Evaluation & Checkpoint Push**| 1 × Nvidia A100 (40GB) | 0.5 hours | $2.10 / hr | $1.05 | 1.1% |
| **Buffer / Reserved Balance** | — | — | — | **$90.83** | **90.8%** |

**Conclusion:** The $100 Modal credit pool is more than sufficient to run one focused 2-hour QLoRA fine-tuning experiment on a single H100 GPU while providing hundreds of hours of CPU preprocessing headroom.
