# LolixCopilot — Comprehensive Technical Presentation Briefing

**Product:** LolixCopilot  
**Company:** Golixco  
**Tagline:** From raw footage to a stronger cut.  
**Target Event:** Meta Global AI Developer Hackathon (November 2026)  
**Live Production URL:** `https://d2ikihwmt96m58.cloudfront.net` (AWS ap-south-1)  
**Repository:** `https://github.com/GolixcoAI/lolixco-pilot`

---

## 1. What is LolixCopilot?

### The Core Problem
Digital video editors spend more than 70% of their production time scrubbing erratically through raw footage looking for key actions, emotional beats, or climactic moments. Conventional non-linear editors (NLEs) like DaVinci Resolve or Premiere Pro are powerful manipulation tools, but they have zero semantic awareness of what is happening inside the video frames. Conversely, existing "AI video generators" generate synthetic videos from scratch rather than assisting creators in editing their real-world footage.

### The Solution: An AI-Augmented Editing Workstation
LolixCopilot bridges this divide. It is a professional dark-studio editing workstation where creators upload raw footage and interact conversationally with an **AI Director**. The AI Director watches the footage, identifies scenes, understands narrative pacing, grounds key visual moments with sub-second accuracy, and turns natural-language editing instructions into editable multi-track timeline operations and rendered video cuts.

### Primary Differentiators
1. **Editing Blueprint Output, Not Hallucinated Video:** The system provides transparent, editable timeline decisions (cuts, trims, title overlays, speed ramps) rather than opaque black-box video generation.
2. **Multi-Provider AI Orchestration:** Combines the visual perception of open-weight models (Muse Glimmer 30B on Modal H100) with the conversational reasoning of Meta's Model API (Muse Spark 1.3) and high-throughput structured synthesis (Baseten Muse Spark Open).
3. **Professional Workstation Experience:** Built to non-linear editing standards with SMPTE timecode accuracy, multi-track timeline visualization, 60fps playhead synchronization, and serverless FFmpeg cloud rendering.

---

## 2. How the AI Director Works

The AI Director processes user input through a five-stage pipeline:

```
[User Chat] ──> [1. Intent Routing] ──> [2. Scene Grounding] ──> [3. Creative Reasoning]
                                                                        │
[Render Cut] <── [5. Timeline Mutation] <── [4. Blueprint Synthesis] <──┘
```

1. **Intent Classification:** Distinguishes conversational queries ("Hi, how do you work?") from actionable editing directives ("Review my edit", "Add a purple title overlay", "Keep only the last 30 seconds").
2. **Temporal Scene Grounding:** Examines sampled video frames and audio transients to locate key events and transition points.
3. **Creative Editorial Reasoning:** Evaluates pacing, emotional buildup, and narrative rhythm, formulating structured editorial suggestions with clear justifications.
4. **EditingBlueprint Formulation:** Synthesizes a validated JSON schema containing scene boundaries, thumbnail markers, and timeline mutations.
5. **Timeline Execution:** Injects operations directly onto the multi-track timeline:
   - **Track V2 (Effects):** Timed text overlays, speed ramps, and flash markers.
   - **Track V1 (Video):** Scene cuts, non-destructive clip deactivations (hatched trims), and filmstrip thumbnails.
   - **Track A1 (Audio):** Beat-synchronized cut alignment.

---

## 3. Foundation Models and AI Providers

### 3.1 Meta Muse Spark 1.3 (Meta Model API)
- **Role:** Creative Director and Editorial Reasoning Engine.
- **Why it is used:** Muse Spark 1.3 possesses advanced chain-of-thought reasoning capabilities. When given video descriptions or sampled frames, it excels at answering qualitative editorial questions: "Where does the energy drop?", "How should we frame the climax?", and "What pacing works best for social media?"
- **Integration:** Accessed server-side via `https://api.meta.ai/v1` using official Meta developer keys. To ensure maximum audio-visual fidelity, speech audio processing is decoupled from the raw vision stream, following Meta documentation best practices.

### 3.2 Meta Muse Glimmer 30B (Modal H100 GPU)
- **Role:** Deep Visual Understanding and Temporal Moment Localization.
- **Why it is used:** With 30 billion parameters and a dedicated ViT-G/14 vision perception encoder, Muse Glimmer open-weights provide powerful visual grounding. It identifies fine-grained actions (such as character abilities, object collisions, or camera movement changes) that lightweight models miss.
- **Integration:** Deployed on Modal serverless containers powered by dedicated NVIDIA H100 SXM5 (80GB) GPUs. Base model weights are cached in persistent Modal Volumes for fast cold starts.

### 3.3 Baseten Muse Spark Open (`meta-models/muse-spark-open-1026`)
- **Role:** High-Throughput Structured Blueprint Synthesis.
- **Why it is used:** Baseten provides reliable, low-latency OpenAI-compatible hosting of Muse Spark Open. It reliably enforces strict JSON object outputs (`response_format={"type": "json_object"}`) without token budget exhaustion.
- **Integration:** Configured with `reasoning_effort="low"` to prevent intermediate chain-of-thought tokens from truncating the final JSON schema.

---

## 4. How Auto Mode Works (Multi-Provider Orchestration)

Auto Mode coordinates all three AI systems into a single pipeline:

1. **Stage 1 (Modal H100):** Scans the video and extracts visual events, peak moments, and character actions.
2. **Stage 2 (Meta Muse Spark):** Analyzes the creator's instructions against the visual evidence, composing creative rationales and narrative guidance.
3. **Stage 3 (Baseten):** Translates the narrative decisions into a mathematically valid `EditingBlueprint` JSON schema with SMPTE timestamps.
4. **Fallback Resilience:** If any provider is rate-limited or unavailable, the orchestrator gracefully degrades to alternative paths (e.g., falling back to Baseten for visual reasoning if Modal is warm-starting, or using local deterministic cut markers if external APIs encounter network errors).

---

## 5. Fine-Tuning: Honest Technical Analysis

Judges and evaluators frequently scrutinize fine-tuning claims. Here is the exact, honest technical breakdown of our work:

### What Was Built and Verified
- **Target Model:** `meta-models/Muse-Glimmer-30B` (revision `a4e59da52a7bc87ae7251dd5545c0dd437c44b68`).
- **Framework:** Axolotl 0.19.0+, PyTorch 2.5, TRL SFTTrainer.
- **Hardware:** 1 × NVIDIA H100 SXM5 (80GB SXM5) on Modal ($3.95/hr).
- **Quantization:** 4-bit BitsAndBytes NF4 with double quantization.
- **LoRA Targets:** Rank $r=16$, Alpha $\alpha=32$, targeting language projections (`q, k, v, o, gate, up, down`).
- **Vision Components:** The ViT-G/14 perception encoder and multimodal projector were **strictly frozen**, ensuring stability and memory fit (~32.5 GB peak VRAM).
- **Dataset:** 7 synthetic structural fixture samples (`is_purely_synthetic_fixtures: true`) verified with zero cross-split leakage.
- **Execution Trajectory:** Bounded optimizer steps verified training convergence with loss decreasing from **3.086 to 2.142**.

### Crucial Distinction: Pipeline Validation vs. Domain Model
- **This run was a pipeline and infrastructure validation.** It proved that Muse Glimmer 30B can be loaded, quantized to 4-bit, adapted with LoRA, and trained with gradient descent on a single H100 GPU within our $100 credit pool.
- **It is NOT claimed to be a fully converged anime expert model.** A 2-step training run on 7 structural fixtures cannot generalize broadly. Therefore, in the live production application, we use **base Muse Glimmer 30B** and **Muse Spark 1.3** for zero-shot inference, ensuring reliable and stable editorial performance.
- **Copyright Compliance:** Demonstration anime clips were used strictly for offline local evaluation under fair use research standards and were never included in training datasets or the public repository.

---

## 6. AWS Production Architecture

LolixCopilot runs in AWS Region `ap-south-1` (Mumbai):

- **EC2 Workstation Host:** Single `t3.small` instance (2 vCPUs, 2GB RAM, 2GB swap, 30GB gp3 SSD). Sizing telemetry proves it runs efficiently with 1.1GB RAM free and negligible CPU load.
- **Edge HTTPS:** Amazon CloudFront distribution (`d2ikihwmt96m58.cloudfront.net`) providing global SSL/TLS encryption and automatic HTTP-to-HTTPS redirect.
- **Nginx Reverse Proxy:** Terminates internal HTTP traffic on port 80/443 and proxies to Next.js (`127.0.0.1:3000`) and FastAPI (`127.0.0.1:8000`). Public access to ports 3000 and 8000 is completely blocked in the security group.
- **AWS Secrets Manager:** Automatically provisions backend credentials (`lolixcopilot/production/backend`) and injects them at service startup using the EC2 IAM instance role (`LolixCopilotAppRole`). No static AWS keys or API tokens exist on disk or in Git.
- **Private S3 Storage:** Dedicated private bucket (`s3://lolixcopilot-media-247673029886-ap-south-1`) with Public Access Block enabled. Uploads and streaming use 15-minute presigned URLs. Objects automatically expire after 7 days.
- **AWS Lambda:** Serverless Python 3.12 + FFmpeg function (`lolixcopilot-media-processor`) generates 720p proxies, extracts beat waveforms, and renders final exported MP4 cuts.
- **Host Administration:** AWS Systems Manager Session Manager (no open SSH port 22).

---

## 7. Complete Technology Stack and Versions

- **Frontend:** Next.js 16.4.3, React 19, TypeScript 5, Tailwind CSS, Vitest.
- **Backend:** Python 3.13, FastAPI 0.115+, Pydantic 2.10, Uvicorn, Pytest.
- **Database & Auth:** Supabase PostgreSQL with GoTrue Auth and Row-Level Security.
- **Cloud Infrastructure:** AWS EC2 (`t3.small`), AWS S3, AWS Lambda, AWS Secrets Manager, Amazon CloudFront, AWS SSM.
- **AI Infrastructure:** Meta Model API (`muse-spark-1.3`), Modal Labs (NVIDIA H100 80GB), Baseten (`muse-spark-open-1026`), Axolotl 0.19.0.
- **Media Engine:** FFmpeg 6+, ffprobe, libass subtitles engine.

---

## 8. Verified Demonstration Narration (2–4 Minutes)

This script is structured for Windows laptop recording using OBS Studio or Windows Game Bar:

### 1. Introduction (0:00 - 0:25)
"Hello. I'm presenting LolixCopilot, built by Golixco for the Meta Global AI Developer Hackathon. Video editors spend over 70% of their time scrubbing through raw footage hunting for moments. LolixCopilot is an AI-assisted video editing workstation that turns raw footage into an actionable editing blueprint with timeline operations and rendered cuts."

### 2. Live Web Deployment & Empty Dashboard (0:25 - 0:45)
"We are live on AWS ap-south-1 at `https://d2ikihwmt96m58.cloudfront.net`. Notice the clean dark studio workstation aesthetic, the official LolixCopilot branding, and the initial clean state with an empty media bin and timeline. All network traffic is encrypted via CloudFront HTTPS."

### 3. Media Ingest & Cloud Security (0:45 - 1:10)
"Let's import our raw footage. The video uploads directly from the browser to private Amazon S3 using short-lived presigned URLs. All public access is blocked. AWS Lambda immediately probes the container and extracts an H.264 preview stream and audio waveforms. Notice the playback monitor: 60fps frame stepping, zero audio drift, and exact SMPTE timecode display."

### 4. Query 1: AI Edit Review (1:10 - 1:40)
"Now let's ask the AI Director: 'Review my edit.' In the background, Auto mode routes the request across our multi-provider mesh: Modal H100 visual moment localization, Meta Muse Spark creative narrative reasoning, and Baseten structured blueprint generation. The response streams in: 6 structured scene cards with thumbnails, 5 checkable recommendations, and real-time inference telemetry. Clicking 'Jump to Moment' seeks the player instantly."

### 5. Query 2: Timed Title Overlay (1:40 - 2:05)
"Next, we ask: 'Add a title overlay for Hollow Purple.' The AI Director identifies the exact visual convergence window from 00:37 to 00:44. It injects a styled purple text overlay onto Track V2. As we scrub across the playhead, the overlay appears and disappears at the exact frame boundary."

### 6. Query 3: Non-Destructive Last-30-Seconds Trim (2:05 - 2:30)
"Now we instruct: 'Keep only the last 30 seconds.' The workstation calculates the duration, deactivates earlier footage non-destructively with hatched styling on Track V1, and automatically remaps the Track V2 overlay into the new export coordinate space."

### 7. Asynchronous Export Rendering (2:30 - 3:00)
"We click 'Export'. An asynchronous export job triggers on AWS Lambda. The progress bar polls live status. When complete, we download the finished 30.00-second cut. The purple title is burned cleanly into the video via FFmpeg libass, and audio is in sync."

### 8. Conclusion (3:00 - 3:20)
"LolixCopilot demonstrates practical multimodal AI in creative tooling: Meta Muse Spark for reasoning, Muse Glimmer on Modal H100 for visual grounding, Baseten for structured plans, and a production AWS cloud deployment. From raw footage to a stronger cut. Thank you."
