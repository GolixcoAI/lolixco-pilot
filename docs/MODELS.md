# LolixCopilot — Model Inventory and Reference Specifications

This document catalogs all models used across LolixCopilot's multimodal editing pipeline.

## Model Inventory

| Model Identifier | Provider / Platform | Parameters | Modality | Primary Function | Context Window |
|---|---|---|---|---|---|
| `muse-spark-1.3` | Meta Model API | Undisclosed (Proprietary) | Multimodal (Text + Vision) | Conversational editorial reasoning, intent translation, pacing direction | 128,000 tokens |
| `meta-models/Muse-Glimmer-30B` | Modal (Dedicated H100) | 30 Billion | Multimodal (Vision + Text) | Visual scene grounding, keyframe event detection, PEFT QLoRA training | 4,096 tokens (Fine-tuning) |
| `meta-models/muse-spark-open-1026` | Baseten Serverless | Undisclosed (Open Weights) | Text + Vision Embeddings | High-throughput structured JSON `EditingBlueprint` generation | 32,768 tokens |
| `muse-voice-transcribe-1.0` | Meta Model API (Optional) | Undisclosed | Audio-to-Text | Dedicated speech transcription when dialogue drives the cut | Streaming audio |

---

## Model Capabilities and Operating Details

### 1. Meta Muse Spark 1.3 (`muse-spark-1.3`)
- **Host:** Meta managed cloud infrastructure (`https://api.meta.ai/v1`).
- **Role:** High-level creative director. Ingests user instructions such as "Review my edit" or "Make this cut more energetic" and evaluates the macro narrative arc.
- **Audio Guidance:** Meta documentation advises that raw audio in `muse-spark-1.3` vision requests may have reduced fidelity; LolixCopilot separates audio track processing to ensure high-fidelity timeline beat alignment.
- **Output:** Conversational Markdown responses, creative pacing rationales, and structured scene annotations.

### 2. Meta Muse Glimmer 30B (`meta-models/Muse-Glimmer-30B`)
- **Host:** Modal serverless container with dedicated 1x NVIDIA H100 (80GB SXM5).
- **Architecture:** ViT-G/14 vision perception encoder paired with an autoregressive language model.
- **Role:** Fine-grained temporal moment detection. Scans video keyframes to locate action peaks (such as energy sphere convergence or character technique execution).
- **Fine-Tuning:** Serves as the base model for parameter-efficient QLoRA fine-tuning in `training/train_glimmer_qlora.py`.

### 3. Baseten Muse Spark Open (`meta-models/muse-spark-open-1026`)
- **Host:** Baseten OpenAI-compatible inference cluster (`https://inference.baseten.co/v1`).
- **Role:** Deterministic structured blueprint generation. Emits strictly typed JSON schemas with exact float timestamps for timeline track injection.
- **Reasoning Effort:** Configured to `reasoning_effort="low"` to prevent intermediate reasoning token exhaustion.
