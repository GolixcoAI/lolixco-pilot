# LolixCopilot — Baseten vs Modal Inference Comparison

**Document Purpose:** Grounded architectural comparison between **Baseten** and **Modal** for hosting and running **Muse Spark Open** inference for LolixCopilot, based on official documentation from Meta, Baseten, and Modal.

---

## 1. Feature & Capability Comparison Matrix

| Dimension | Baseten | Modal |
| :--- | :--- | :--- |
| **Model String** | `meta-models/muse-spark-open` (alias: `muse-spark-open-1026`) | `meta-models/muse-spark-open` |
| **Endpoint Architecture** | Serverless Model API (warm pool) & Dedicated Inference | Shared Auto Endpoints & Container Functions |
| **Request Protocol** | OpenAI-compatible `POST /v1/chat/completions` | OpenAI-compatible Shared Endpoints or Python SDK |
| **Context Window** | **1,048,576 tokens** (1M tokens full context) | **1,048,576 tokens** |
| **Modalities Supported** | **Text, Image, Video, Audio** | Text, Image, Video, Audio |
| **Media Ingestion Format** | Standard OpenAI content-parts: `image_url`, `video_url`, `audio_url` | Content-parts or raw container file mount via Volumes |
| **Video Constraints** | Max 200 MB via URL; samples max 96 frames/clip (~144 tok/s, capped at ~6.9K tokens) | Depends on deployment container VRAM / vLLM settings |
| **Audio Ingestion** | Supported as separate `audio_url` content-part (video audio track is bypassed) | Supported as separate audio input or combined pipeline |
| **Billing Model** | Pay-per-token (serverless); no idle compute cost | Pay-per-token on Shared Endpoints; or pay-per-second on dedicated containers |
| **Cold Start Latency** | **Sub-second to 2s** (managed warm pool) | Instant on Shared Endpoints; 15–45s if spinning up custom containers |
| **Current Integration** | **Fully implemented and configured** in LolixCopilot backend (`BasetenProvider`) | Prototype / prospective integration |

---

## 2. Operational & Developer Experience Analysis

### 2.1 Baseten Strengths for LolixCopilot
1. **Turnkey Serverless Model APIs:** Baseten maintains a managed warm cluster for `meta-models/muse-spark-open`. This eliminates cold-start penalties when users click "Identify source, characters & soundtrack".
2. **Predictable Per-Token Cost:** Video processing consumes ~144 tokens per second of footage, with a strict hard cap at ~6,900 tokens (achieved at ~48 seconds). Clips up to 60 seconds (LolixCopilot's hard constraint) are automatically capped at this ceiling, ensuring deterministic, low inference costs per analysis.
3. **OpenAI Compatibility:** Fits seamlessly into `backend/app/services/ai_provider.py` using standard HTTPX async transport, error mappings (401, 403, 429, 503), and structured JSON decoding.
4. **Existing Configuration:** Baseten credentials (`BASETEN_API_KEY`) and endpoints (`https://inference.baseten.co/v1`) are already provisioned and validated in LolixCopilot.

### 2.2 Modal Strengths & Primary Niche
1. **Custom Asynchronous Processing:** Modal excels at raw containerized operations: running FFmpeg with custom compiled codecs, extracting audio waveforms, probing timestamps, and slicing keyframes.
2. **Fine-Tuning & Model Adaptation:** Modal provides fine-grained GPU control (e.g. spinning up a single H100 for 2 hours of Axolotl QLoRA on Muse Glimmer 30B).
3. **Storage & Data Pipelines:** Modal Volumes (`modal.Volume`) allow streaming high-resolution anime datasets directly into GPUs without local disk bottlenecks.

---

## 3. Final Recommendation for LolixCopilot

### **Primary Multimodal Inference Provider: Baseten**
- **Decision:** Keep **Baseten** as LolixCopilot's primary inference engine for `Muse Spark Open`.
- **Rationale:**
  1. Already tested and integrated with complete schema parsing and error boundaries.
  2. Serverless per-token billing avoids burning funds on idle container reservations.
  3. Direct support for presigned S3 `video_url` and `audio_url` payloads up to 200 MB.
  4. Preserves our current environment configuration without disrupting the active workstation.

### **Secondary / Asynchronous Infrastructure Provider: Modal**
- **Decision:** Position **Modal** as the **Asynchronous Media Processing & Model Training Engine**:
  1. Offload bounded FFmpeg probing and audio extraction to Modal CPU containers.
  2. Reserve Modal GPU credits ($100 pool) exclusively for targeted fine-tuning experiments (Muse Glimmer QLoRA) and specialized model evaluation.
