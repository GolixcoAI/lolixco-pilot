# LolixCopilot — AI Providers Specification

LolixCopilot integrates three complementary AI backends to achieve grounded multimodal video editing: Meta Model API, Modal GPU Infrastructure, and Baseten Serverless Inference.

## Summary Comparison

| Attribute | Meta Model API | Modal Infrastructure | Baseten Inference |
|---|---|---|---|
| **Primary Model** | `muse-spark-1.3` | `meta-models/Muse-Glimmer-30B` | `meta-models/muse-spark-open-1026` |
| **Model Type** | Proprietary API | Open-Weight Multimodal Foundation | Hosted Open-Weight Foundation |
| **Hardware** | Meta Cloud Managed | Dedicated NVIDIA H100 SXM5 (80GB) | Baseten Serverless GPU Cluster |
| **Primary Task** | Creative reasoning and conversational editing | Visual grounding and QLoRA fine-tuning | High-throughput structured JSON blueprints |
| **Interface** | REST API (`api.meta.ai/v1`) | Modal Python SDK & Ephemeral Containers | OpenAI-compatible REST API |
| **Audio Processing** | Decoupled / external audio track | CPU FFmpeg waveform extraction | External audio reference |
| **Cost Profile** | Per-token API rate | $3.95/hr per H100, $0.0864/hr per CPU | Per-token / execution-second rate |

---

## 1. Meta Model API (Muse Spark 1.3)

### Role and Capabilities
Meta's official Model API powers the creative brain of LolixCopilot. It interprets complex creative editing prompts, evaluates scene pacing, and crafts conversational responses that maintain editorial voice.

### Integration Details
- **Base URL:** `https://api.meta.ai/v1`
- **Configured Model ID:** `muse-spark-1.3`
- **Authentication:** Bearer token via `MODEL_API_KEY` (server-side only, never sent to client).
- **Request Format:** Multi-turn chat completions with optional structured system prompts.
- **Audio Handling:** Following Meta documentation recommendations, video audio is not fed raw into the vision path; speech transcription is kept separate via dedicated audio extraction to avoid audio degradation in multimodal reasoning.

### Error Handling and Resilience
- Automatic retries on HTTP 429 (rate limits) and HTTP 5xx errors with exponential backoff.
- Strict timeout enforcement (`AI_REQUEST_TIMEOUT_SECONDS=120`).
- Safe fallback to cached or alternative provider responses when Meta API is unreachable.

---

## 2. Modal Infrastructure (Muse Glimmer 30B)

### Role and Capabilities
Modal provides high-performance asynchronous compute for two distinct responsibilities:
1. **CPU Media Processing (`workers/media_worker.py`):** Serverless FFmpeg probing, 16kHz mono WAV extraction, and keyframe thumbnail generation at high throughput and low cost.
2. **GPU Intelligence & Training (`training/train_glimmer_qlora.py`):** Execution of the 30-billion parameter Muse Glimmer open-weight model on physical NVIDIA H100 SXM5 (80GB) hardware for temporal scene localization and fine-tuning experiments.

### Integration Details
- **Base Model:** `meta-models/Muse-Glimmer-30B` (revision `a4e59da52a7bc87ae7251dd5545c0dd437c44b68`).
- **Quantization:** 4-bit BitsAndBytes NormalFloat4 (NF4) with double quantization.
- **Architecture Adaptation:** Frozen vision perception tower (ViT-G/14) and multimodal projector; trainable rank-16 LoRA adapters on language attention and MLP SwiGLU layers.
- **Storage:** Checkpoints persisted to durable Modal Volumes (`modal.Volume`).

---

## 3. Baseten Inference (Muse Spark Open 1026)

### Role and Capabilities
Baseten hosts the open-weight release of Muse Spark Open, providing dedicated OpenAI-compatible inference with fast cold starts and consistent structured JSON output.

### Integration Details
- **Base URL:** `https://inference.baseten.co/v1`
- **Configured Model ID:** `meta-models/muse-spark-open-1026`
- **Authentication:** Bearer token via `BASETEN_API_KEY`.
- **Reasoning Configuration:** Based on empirical research, reasoning effort is set to `low`. Higher reasoning levels (`high`, `max`) risk output token exhaustion and malformed JSON schemas.
- **Structured Schema:** Enforces `response_format={"type": "json_object"}` with Pydantic validation of the returned `EditingBlueprint`.
