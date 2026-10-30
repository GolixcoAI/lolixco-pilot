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

Do not blindly send every upload through every model. Route only to the service needed for the selected feature.

## 8. Credit and spend controls

### Meta Model API

- Keep a budget ledger per analysis, record API usage when supplied, and display only a user-friendly “analysis complete” status rather than invented dollar costs.
- Limit initial videos to 60 seconds / 100 MB.
- Limit a normal analysis to one main video-understanding call, plus an optional transcription call only if needed.
- Moodboard generation is opt-in and rate limited.
- Cache unchanged inputs.
- Add a configurable daily analysis cap for the demo.
- Before coding, review the current billing dashboard and verify which model mode the free credits use. The user's screenshot explicitly says content may be used for product improvement while free credits are in use; until terms are clear, use only authorized, non-sensitive test videos and display a concise notice before upload.

### Modal

- Start with CPU-only Modal functions for FFmpeg/ffprobe and orchestration.
- Do not deploy an always-on GPU or download giant model weights for this product's core path.
- Set max runtime/concurrency, use ephemeral storage, clean up temporary files, and inspect Modal usage/logs after each deploy.
- Install the official Modal agent skill with `modal skills install` and update it when current docs are needed. Modal's official skill is intended to help coding agents use current Modal patterns.

## 9. Production hardening after the hackathon

- Move from hackathon retention to user-selectable policies and deletion verification.
- Add plan/usage limits, abuse monitoring, job retry/queue policy, and audit logging.
- Add integration tests against a separate development bucket/database.
- Consider CDN playback only if product performance needs it; do not make private originals public to make the demo easier.
- Add provider adapters, API versioning, observability dashboards, data export, and backups.
- Integrate into the larger Lolixco application through a documented API or package; do not copy this repo into Lolixco.

## 10. Primary references

- Meta Model API overview: https://dev.meta.ai/docs/overview
- Meta API reference: https://dev.meta.ai/docs/api-reference
- Meta video and audio understanding: https://dev.meta.ai/docs/video-understanding
- Meta media segmentation: https://dev.meta.ai/docs/media-segmentation
- Meta pricing/rate limits: https://dev.meta.ai/docs/pricing-rate-limits
- Modal agent skills: https://modal.com/docs/cli/latest/skills
- Modal ASGI app: https://modal.com/docs/sdk/py/latest/asgi_app
- Modal volumes (do not use as the source of truth for user videos): https://modal.com/docs/sdk/py/latest/Volume
