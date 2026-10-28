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

Suggested key layout:

```text
users/{user_id}/analyses/{analysis_id}/source/{safe_filename}
users/{user_id}/analyses/{analysis_id}/previews/scene-01.jpg
users/{user_id}/analyses/{analysis_id}/previews/scene-02.jpg
```

- Browser asks the API for a short-lived presigned upload URL and uploads directly to S3.
- API verifies the authenticated user owns the analysis and uses `head_object` plus media inspection before processing.
- The API creates a short-lived presigned GET URL for the model/worker; never save the signed URL in Postgres or logs.
- The video player receives a short-lived presigned GET URL. Refresh it on demand.
- Private bucket, public access blocked, bucket CORS limited to the deployed frontend origin, encryption at rest enabled.
- Use a least-privilege IAM identity scoped to this bucket and required operations. Never use root AWS credentials.

### Retention

For the hackathon build, configure a short retention default (7 days) for source uploads and derived previews, plus a visible “Delete project” action. Make the retention window configurable. Before production, add explicit user-controlled retention and deletion of all source and derived objects.

### Meta API file strategy

Prefer `input_video` with a short-lived URL when it fits the API's documented flow, so we don't create an extra managed upload copy. Meta's current video-understanding docs support a public or base64 `video_url`, or a `file_id` from the Files API. Verify whether a presigned S3 URL is retrievable from Meta's service in a smoke test. If it isn't, use the Files API and implement deletion/retention according to the current API's supported operations and terms.

## 4. Database model

Use migrations in source control. Initial table `analyses`:

- `id UUID PRIMARY KEY`
- `user_id UUID NOT NULL` (Supabase Auth identity)
- `title TEXT NULL`
- `status TEXT NOT NULL CHECK status IN ('created','uploaded','queued','preprocessing','analyzing','ready','failed','deleting','deleted')`
- `source_object_key TEXT NOT NULL`
- `duration_seconds DOUBLE PRECISION NULL`
- `width INTEGER NULL`, `height INTEGER NULL`, `filesize_bytes BIGINT NULL`
- `creative_brief TEXT NOT NULL`
- `model_id TEXT NULL`
- `result_json JSONB NULL`
- `error_code TEXT NULL`, `error_message_safe TEXT NULL`
- `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `expires_at TIMESTAMPTZ NULL`, `completed_at TIMESTAMPTZ NULL`

Add Row Level Security so users can read/delete only their own rows. Only the server-side service role/worker can update processing status. Never ship the service role key to the browser.

## 5. API contract (initial proposal)

- `GET /api/health` — health only; no secrets or internal diagnostics.
- `POST /api/uploads/presign` — validate declared filename/type/size, create an analysis UUID and private object key, return presigned PUT URL and required headers.
- `POST /api/analyses` — validate uploaded object belongs to current user; create queued job; spawn Modal function; return `{analysis_id, status}`.
- `GET /api/analyses/{analysis_id}` — owner-only status, validated result, and short-lived view URLs as needed.
- `DELETE /api/analyses/{analysis_id}` — owner-only deletion of database record and original/derived objects; make retries safe.
- Optional `POST /api/analyses/{analysis_id}/moodboard` — only after core MVP, explicit user click, per-user rate limit.

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

| Product action | Model/service | Status |
|---|---|---|
| Main visual/video understanding | `muse-spark-1.3` | Core |
| Speech transcription | `muse-voice-transcribe-1.0` | P1, only when speech is relevant |
| Object masks/tracking | `sam-3.1` | Stretch; only with an object-focus UI |
| Cover/moodboard image | `muse-image-1.0` | Stretch; explicit user click |

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
