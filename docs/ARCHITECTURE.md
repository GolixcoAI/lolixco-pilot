# LolixCopilot — Architecture and Implementation Decisions

## 1. Recommended initial stack

| Layer | Initial choice | Why |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind CSS + shadcn/ui | Fast iteration on a premium, responsive studio UI |
| Motion | Small Framer Motion usage or CSS transitions | Subtle transitions without making the editor feel decorative |
| API | FastAPI served as a Modal ASGI web app | Familiar Python stack and one place for API + background compute; Modal supports FastAPI via `@modal.asgi_app()` |
| Async processing | Modal serverless function, CPU first | FFmpeg/ffprobe, thumbnails, and optional scene-boundary detection without managing a fixed worker |
| Video object storage | Private Amazon S3 bucket | Durable binary storage, direct browser upload, short-lived signed URLs; does not tie videos to the lifetime of an app container |
| Metadata/auth | Supabase Auth + PostgreSQL | Durable job state and later account/project history |
| AI semantic analysis | Meta Model API — Muse Spark | Video understanding and creative plan generation |
| Speech (optional) | Meta Muse Voice Transcribe | Separate transcript path; current docs note Muse Spark 1.3 audio quality may be degraded for audio-containing requests |
| Object segmentation (stretch) | Meta SAM 3.1 | Tracking/segmentation masks when the product has a user-visible object-focus workflow |
| Visual direction (stretch) | Meta Muse Image | Explicitly requested moodboard/cover concepts |
| Hosting | Vercel for frontend; Modal for Python API/workers | Keeps video/AI workload out of a frontend-only serverless function |

If Supabase/S3 credentials are not ready quickly, implement local development adapters first, but preserve provider interfaces. Do not silently replace production storage with an ephemeral local directory.

## 2. System diagram

```text
Browser (Next.js)
  | 1. Sign in / create project / request upload URL
  v
LolixCopilot API (FastAPI on Modal)
  |-- Supabase Auth verification + Postgres job metadata
  |-- S3 presigned PUT/GET URLs (bucket remains private)
  |-- spawn analysis worker, return analysis_id immediately
  |
  +--> private S3: original upload + generated preview frames
  |
  +--> Modal background worker
         |-- ffprobe + FFmpeg: duration, dimensions, thumbnails, optional audio extraction
         |-- Meta Model API: Muse Spark video understanding
         |-- optional Muse Voice Transcribe when speech matters
         |-- validate result against Pydantic schema
         |-- persist job status/result in Postgres
         v
Browser polls GET /api/analyses/{id}
  |-- fetches status, blueprint, and short-lived preview/video URLs
  v
Studio: video player + scene cards + timestamp timeline + creative notes
```

## 3. Storage strategy

### Original videos

Store the original source file in a **private S3 bucket**. Do not store it in the Git repository, frontend public folder, Modal container filesystem, or a long-lived public URL.

Implemented key layout:

```text
users/{user_id}/projects/{project_id}/media/{media_id}/{unpredictable_token}.{ext}
```

- Browser requests a short-lived presigned upload URL from the API and uploads directly to S3 via PUT.
- API verifies the authenticated user owns the project/media and uses S3 `head_object` to verify existence and byte size before marking the media `verified`.
- The video player receives a short-lived presigned GET URL (15m TTL).
- Private bucket, all public access blocked, bucket CORS limited to the frontend origin, SSE-S3 encryption enabled.
- Idempotent setup script provided in `scripts/aws/setup_media_bucket.sh`.
- Local development leverages boto3's standard credential chain (`~/.aws/credentials` or `AWS_PROFILE`). Production will use IAM roles.

### Retention & Lifecycle Interaction

- **Database Retention:** `expires_at = created_at + 7 days`. On playback request, backend enforces HTTP 410 Gone if `now > expires_at`, ensuring stale DB records never make expired videos appear playable.
- **S3 Storage Lifecycle:** Automated S3 Lifecycle Rule (`ExpireUserFootageAfter7Days`) configured to delete objects under prefix `users/` after 7 days, and clean up incomplete multipart uploads after 1 day.
- **Interaction:** Because S3 lifecycle runs asynchronously (once daily), database expiration immediately prevents playback access at the 7-day boundary, and S3 physical object deletion cleans up underlying storage without manual intervention.

### Meta API file strategy

Prefer `input_video` with a short-lived URL when it fits the API's documented flow, so we don't create an extra managed upload copy. Meta's current video-understanding docs support a public or base64 `video_url`, or a `file_id` from the Files API. Verify whether a presigned S3 URL is retrievable from Meta's service in a smoke test. If it isn't, use the Files API and implement deletion/retention according to the current API's supported operations and terms.

## 4. Database model (Phase 1 Implemented)

Use migrations in source control (`supabase/migrations/20261030160559_phase1_projects_and_media.sql`).

### Supabase Project & Regional Topology

- **Supabase Project Reference:** `fhfkjviishfvfyawfckh`
- **Supabase Region:** Singapore (`ap-southeast-1`)
- **AWS S3 Region:** Mumbai (`ap-south-1`)
- **Cross-Region Strategy & Latency:**
  - This cross-region setup is intentional and optimal for initial development.
  - Supabase handles authentication and structured metadata (lightweight JSON payloads, typically 2-10 KB). The network round-trip between Mumbai and Singapore is approximately 30-50 ms, which is imperceptible for database queries.
  - High-bandwidth video assets (10-100 MB) stream directly between the client browser and the dedicated private S3 bucket in Mumbai (`ap-south-1`) via short-lived presigned URLs.
  - No media binary data traverses across cloud regions or passes through Supabase database connections, avoiding inter-region egress costs and latency penalties.

### Supabase GitHub Integration Configuration

- **Repository:** `GolixcoAI/lolixco-pilot`
- **Working directory:** `.`
- **Production branch:** `main`
- **Automatic production deployment:** Initially disabled (manual migration review).
- **Canonical Migration Path:** `supabase/migrations/<timestamp>_<name>.sql`
- **Local Configuration:** `supabase/config.toml` (project ID `fhfkjviishfvfyawfckh`, anonymous sign-ins enabled, 100MiB storage limit).

Implements tables:
1. `projects`:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL` (Supabase Auth identity, anonymous or linked)
   - `name TEXT NOT NULL DEFAULT 'Untitled Cut'`
   - `aspect_ratio TEXT NOT NULL DEFAULT '9:16'`
   - `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`

2. `media`:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE`
   - `user_id UUID NOT NULL`
   - `original_filename TEXT NOT NULL`
   - `s3_object_key TEXT NOT NULL UNIQUE`
   - `content_type TEXT NOT NULL`
   - `declared_size_bytes BIGINT NOT NULL`
   - `verified_size_bytes BIGINT NULL`
   - `duration_seconds DOUBLE PRECISION NULL`
   - `status TEXT NOT NULL CHECK (status IN ('pending', 'uploaded', 'verified', 'failed', 'expired'))`
   - `expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days')`
   - `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`

3. `analyses`:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE`
   - `media_id UUID REFERENCES media(id) ON DELETE CASCADE`
   - `user_id UUID NOT NULL`
   - `status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed'))`
   - `blueprint JSONB NULL`
   - `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`

All tables enforce Row Level Security (`auth.uid() = user_id`) so users (including anonymous visitors) cannot access each other's projects, media, or analyses.

### 4.1 SupabaseRepository & PostgREST Persistence Architecture

LolixCopilot implements a production-grade Supabase persistence layer for projects and media without adding bloated or opinionated client SDK dependencies:

1. **Lightweight PostgREST Client:**
   - Uses the installed `httpx.Client` to interact directly with Supabase's PostgREST REST endpoints (`/rest/v1/projects`, `/rest/v1/media`).
   - Cleanly implements all methods from the abstract `BaseRepository`:
     - **Projects:** `get_project`, `list_projects`, `create_project`, `get_or_create_default_project`, `update_project`.
     - **Media:** `create_media`, `get_media`, `list_media`, `update_media_status`, `delete_media`.

2. **Request-Scoped Isolation & Lifecycle:**
   - Every database request is strictly bound to the authenticated request lifecycle.
   - The repository is instantiated inside FastAPI's `get_repository` dependency with the caller's verified `AuthenticatedUser.access_token` and `SUPABASE_PUBLISHABLE_KEY`.
   - Headers sent on every PostgREST query:
     - `apikey: <SUPABASE_PUBLISHABLE_KEY>`
     - `Authorization: Bearer <CURRENT_USER_ACCESS_TOKEN>`
   - `get_repository` yields the repository and guarantees HTTP client closure via `finally: repo.close()`.
   - Never shares client instances or cached authentication tokens across different requests or users.

3. **Strict Row-Level Security & Ownership:**
   - In accordance with PostgreSQL RLS policies, all queries filter explicitly on `auth.uid() = user_id` derived directly from the verified Supabase JWT (never trusted from request payloads).
   - `Prefer: return=representation` header ensures atomicity and returns the mutated records immediately upon `POST`, `PATCH`, or `DELETE`.

4. **Fail-Closed Guarantees:**
   - Missing `SUPABASE_URL` or `SUPABASE_PUBLISHABLE_KEY` when `DATABASE_PROVIDER=supabase` raises a clear, immediate startup error (`RuntimeError`).
   - Database network, permission, or constraint errors raise typed domain exceptions (`DatabaseError`, `DatabaseConnectionError`, `DatabasePermissionError`, `DatabaseRecordNotFoundError`) rather than masking failures.
   - **Zero Silent Fallbacks:** The system never silently falls back to `InMemoryRepository` in production or live environments when Supabase is requested.
   - Authentication tokens and database credentials are strictly sanitized and never emitted to application logs.

5. **Orthogonal Storage & Database Configuration:**
   - `DATABASE_PROVIDER` (`memory` vs `supabase`) and `USE_MOCK_STORAGE` (`true` vs `false`) are completely separate configurations. Developers can mix-and-match (e.g., Supabase DB + Mock Storage, or Supabase DB + Live S3).

## 5. API contract (Phase 1 Implemented)

- `GET /api/health` — health check only; no secrets or diagnostics leaked.
- `GET /api/projects` — list authenticated user's projects.
- `POST /api/projects` — create or retrieve the user's active project.
- `GET /api/projects/{project_id}` — project details, owner scoped.
- `PATCH /api/projects/{project_id}` — update project name or aspect ratio.
- `GET /api/projects/{project_id}/media` — list project media assets with temporary authorized preview URLs.
- `POST /api/projects/{project_id}/media/presign-upload` — validate declared filename/type/size (max 100MB), create pending media record, generate unpredictable S3 key, return presigned PUT URL.
- `POST /api/projects/{project_id}/media/{media_id}/confirm` — server-side S3 verification via `head_object`, update status to `verified`, record verified size.
- `GET /api/projects/{project_id}/media/{media_id}/preview-url` — owner-only temporary signed GET download/stream URL (returns 410 Gone if expired).
- `DELETE /api/projects/{project_id}/media/{media_id}` — owner-only idempotent deletion of S3 object and media record.
- `POST /api/projects/{project_id}/media/{media_id}/analyze` — initiates video understanding analysis to produce an Editing Blueprint. Requires explicit user consent (`confirmed_baseten_consent: true`), generates short-lived presigned S3 URLs, and dispatches to the configured AI provider.

Use stable typed request/response schemas, request IDs, consistent errors, authentication, CORS allowlist, upload limits, and rate limits. Never accept arbitrary remote URLs for processing.

## 6. Modal worker boundaries

The worker should receive only what it needs:

- `analysis_id`
- a signed source URL with a limited expiry
- a small set of presigned preview-upload URLs (or another documented least-privilege upload path)
- the user creative brief

The worker performs:

1. Download the source to an ephemeral temp directory.
2. Run `ffprobe` to validate actual duration, resolution, and streams.
3. Reject media outside configurable limits.
4. Use FFmpeg to extract representative frames; optionally detect shot changes with a lightweight CPU library after validating its quality.
5. Call Muse Spark on the video URL and a prompt asking for a structured editing blueprint grounded in the supplied footage.
6. If optional transcription is enabled and audio contains speech, extract audio and call Muse Voice Transcribe as a separate step.
7. Validate/clamp timestamps and reject invalid results; do not invent missing facts.
8. Extract thumbnails at selected timestamps and upload with presigned PUT URLs.
9. Store result/status using a server-only database client or securely return results to an orchestrator.
10. Clean up temp files in `finally` blocks; use retries only for transient errors and keep retries bounded.

Use CPU for the first version. Modal credits do not justify running a GPU when the required inference is already hosted by Meta. Consider a GPU only for a measured, product-relevant open-weight workload in a later iteration.

## 7. Meta Model API integration

Current documented base URL: `https://api.meta.ai/v1`; bearer key from the server environment variable `MODEL_API_KEY`.

- Muse Spark model id to test first: `muse-spark-1.3`.
- Use `POST /v1/responses` for video understanding. The documented input includes an `input_text` part plus an `input_video` part with `video_url`, or a file reference as documented by Meta.
- Verify the actual model IDs enabled for the account by calling `GET /v1/models` or the Models dashboard before hardcoding assumptions.
- Use the official OpenAI-compatible SDK interface, but follow current Meta docs for video content parts, structured output, and errors.
- Pydantic validates all model output. Save model id, request id, latency, and token/usage metadata where returned; never save authorization or signed URLs.
- Cache analysis by a stable hash of object version/content hash + normalized brief + model version. Avoid re-analysing unchanged video/brief without user intent.
- On any provider error, show a retryable failure and preserve the uploaded source; don't make up a result.

### Model routing

| Product action | Model/service | Provider | Status |
|---|---|---|---|
| Main video understanding & blueprint | `meta-models/muse-spark-open-1026` | Baseten (`https://inference.baseten.co/v1`) | Primary Hackathon Provider ($100 Credits) |
| Fallback / Offline Testing | `mock-director-1.0` | In-memory Mock Provider | Deterministic baseline (0 credits) |
| Speech transcription | `muse-voice-transcribe-1.0` | Meta Model API | P1, only when speech is relevant |
| Object masks/tracking | `sam-3.1` | Meta Model API | Stretch; only with an object-focus UI |
| Cover/moodboard image | `muse-image-1.0` | Meta Model API | Stretch; explicit user click |

### 7.1 Baseten Provider Adapter Architecture

LolixCopilot integrates Baseten as the primary planned provider for hackathon model inference:
- **Base URL:** `https://inference.baseten.co/v1`
- **Model:** `meta-models/muse-spark-open-1026`
- **Secret Management:** Server-side secret `BASETEN_API_KEY`. The key is never exposed to the client, printed in logs, or included in diagnostics.
- **Provider Interface Isolation:** `app.services.ai_provider.BaseAIProvider` defines the domain contract (`generate_blueprint`), completely decoupling FastAPI routes and DB storage from Baseten-specific HTTP details.
- **Request Format:** OpenAI-compatible multimodal chat completions (`POST /v1/chat/completions`) with system instructions, user creative brief text, and `{"type": "video_url", "video_url": {"url": video_url}}`.
- **Private S3 URLs:** Uses short-lived presigned GET tokens (15-minute TTL). Query string signatures are stripped (`sanitize_url`) from all error logs and exception messages to prevent token leaks.
- **Structured Output:** Enforces `response_format={"type": "json_object"}`, bounded `max_tokens=2500`, and `temperature=0.2`. Output is strictly validated against `app.schemas.blueprint.EditingBlueprint`.
- **Bounded Retries & Error Mapping:**
  - Up to 2 retries with exponential backoff on retryable HTTP errors (`429`, `502`, `503`, `504`) and transport errors.
  - Non-retryable `401`/`403` maps to `AIAuthenticationError` (502 Bad Gateway to client).
  - `429` maps to `AIRateLimitError` (429 Too Many Requests to client).
  - Timeout maps to `AITimeoutError` (504 Gateway Timeout to client).
  - Malformed JSON / schema mismatch maps to `AIValidationError` (502 Bad Gateway to client).
- **User Authorization Safeguard:** Footage is never transmitted to Baseten without explicit user consent (`confirmed_baseten_consent: true`), verified at the API boundary (HTTP 400 if omitted).

### 7.2 Multimodal Audio & Vision Ingestion Architecture

Following empirical research and official Baseten documentation:

1. **Video Ingestion & Frame Sampling:**
   - Baseten's Muse Spark Open encoder retrieves video directly from private S3 via short-lived presigned HTTPS GET URLs.
   - Baseten limits: Up to 2 videos per request, up to 300 seconds per video, max 200 MB per video, 896 MiB encoded-media budget.
   - LolixCopilot enforces conservative MVP limits: max 60 seconds, max 100 MB.
   - The encoder samples a maximum of **96 frames per video** (for a 60-second video, ~1.6 fps).
   - **Crucial Multimodal Finding:** Muse Spark Open's video processing path **ignores the embedded audio track** entirely. Spoken words, dialogue, and sound design in the video are not processed unless audio is sent separately.

2. **Reasoning Effort & Token Budgeting:**
   - In accordance with empirical benchmark findings ([`MUSE_EXPERIMENTS_NOTES.md`](file:///home/vuld0/LolixCopilot/docs/research/MUSE_EXPERIMENTS_NOTES.md)):
     - Muse Spark Open peaks at `reasoning_effort="low"` (88.5% pass@1).
     - Muse rejects `reasoning_effort="none"`.
     - High reasoning effort (`high`, `xhigh`, `max`) causes token exhaustion and truncation (19 of 400 answers truncated at `max` in benchmarks).
   - LolixCopilot maintains `max_tokens=2500` and `temperature=0.2` to ensure intermediate chain-of-thought does not truncate the final `EditingBlueprint` JSON object.

3. **Audio Processing & Multimodal Pipeline (Implemented):**
   - **Extraction:** Bounded `LocalMediaProcessingService` (or Modal CPU worker) extracts the audio track (`16 kHz mono .wav`).
   - **Storage:** Audio stored in private S3 bucket under scoped key `users/{user_id}/projects/{project_id}/media/{media_id}/audio.wav`.
   - **Dual Ingestion:** In Baseten chat completion request, send both `video_url` and `audio_url` content parts in the same user message:
     ```json
     {
       "role": "user",
       "content": [
         {"type": "text", "text": "Analyze footage, identify anime/film source, recognized characters, soundtrack, and generate editing blueprint..."},
         {"type": "video_url", "video_url": {"url": "<presigned_video_url>"}},
         {"type": "audio_url", "audio_url": {"url": "<presigned_audio_url>"}}
       ]
     }
     ```
   - **Alignment:** Fuse dialogue timing with visual cuts to prevent cutting off speakers mid-sentence.

## 8. Provider Adapters: Meta Model API & Baseten

LolixCopilot supports two distinct, decoupled inference providers behind a unified interface:

1. **Baseten (`BasetenProvider`):**
   - **Model:** `meta-models/muse-spark-open` (configured default: `meta-models/muse-spark-open-1026`).
   - **Protocol:** OpenAI-compatible `POST /v1/chat/completions`.
   - **Capabilities:** Multimodal video, audio, and text input with serverless pay-per-token billing.
   - **Media ingestion:** Direct short-lived presigned S3 URLs up to 200 MB; video encoder samples up to 96 frames per clip (~144 tok/s, capped at ~6.9K tokens).
   - **Telemetry:** Real token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`) and request latency recorded per inference.

2. **Meta Model API (`MetaProvider`):**
   - **Model:** `muse-spark-1.3`.
   - **Protocol:** Official Meta Responses API `POST /v1/responses` with fallback to chat completions.
   - **Capabilities:** Server-side multimodal video understanding with structured Pydantic schema validation.
   - **Credentials:** Separate `MODEL_API_KEY` and `https://api.meta.ai/v1` base URL. If key is missing, system gracefully reports configuration required while allowing full operation with Baseten.

3. **Music Fingerprint Interface (`BaseMusicFingerprintProvider`):**
   - Decoupled interface for future specialized acoustic matching (e.g. ACRCloud) without blocking multimodal inference.

## 9. Credit and spend controls

### Meta Model API & Baseten
- **Explicit Authorization:** Users must explicitly authorize model inference via an in-UI checkbox ("Authorize Meta AI / Baseten to analyze video via short-lived private S3 URL"). No silent background inferences occur on upload or page reload.
- **Idempotency & Cost Protection:** Duplicate requests with identical media ID and brief parameters within TTL return cached analysis rather than re-billing paid tokens.
- **Token Limits:** Configurable generation limits (`max_tokens=2500` to `3500`) prevent infinite chain-of-thought loops while safeguarding complete blueprint JSON structure.
- **Rate & Upload Limits:** Enforces strict limits: max 60 seconds duration and 100 MB file size server-side.

### Modal Infrastructure
- **CPU-First Architecture:** FFmpeg probing, thumbnail extraction, and audio isolation execute on low-cost Debian CPU workers (< $0.09/hr per core), consuming < $2 across 1,000 clips.
- **$100 Credit Pool Allocation:**
  - Media workers: < $2.00 (2% of pool).
  - Fine-Tuning: Axolotl QLoRA on a single Nvidia H100 (80GB) @ $3.95/hr consumes ~$7.90 for a complete 2-hour SFT run (< 8% of pool).
  - Full-parameter FSDP2 on 8x H100 ($31.60/hr) is deferred as cost-prohibitive.

## 10. Database Persistence & User Feedback Loop

- **Database:** Supabase PostgreSQL with Row Level Security (RLS) and user-scoped policies.
- **Forward-Only Migration:** `supabase/migrations/20261101180000_media_intelligence_and_analyses_persistence.sql` extends `analyses` table:
  - `provider`: text (`baseten`, `meta`, `mock`).
  - `model`: text (e.g., `meta-models/muse-spark-open-1026`, `muse-spark-1.3`).
  - `source_identification`: JSONB (media classification, likely title, franchise, characters, confidence).
  - `audio_intelligence`: JSONB (soundtrack title, artist, match status, genre, tempo, mood).
  - `usage_metadata`: JSONB (tokens, latency, request IDs).
  - `user_feedback`: JSONB (user confirmation or editor corrections for source and song).
- **Feedback Loop:** AI Director interface lets editors validate identification accuracy or submit corrections, stored as structured feedback for future model adaptation.

## 11. Primary References

- Meta Model API Overview: https://dev.meta.ai/docs/overview
- Meta Muse Spark Open Post-Training: https://dev.meta.ai/docs/muse-spark-open/post-training
- Meta Muse Glimmer Post-Training: https://dev.meta.ai/docs/muse-glimmer/post-training
- Baseten Documentation: https://docs.baseten.co/
- Baseten Muse Spark Open Guide: https://github.com/meta-models/meta-oss-cookbook/blob/main/muse-spark/hosted/baseten.md
- Modal Pricing: https://modal.com/pricing
- Modal Training Infrastructure: https://modal.com/products/training
- Modal Muse Spark Open Launch: https://modal.com/blog/meta-muse-spark-open-now-available-on-modal
