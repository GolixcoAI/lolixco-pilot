# Coding-Agent Instructions — LolixCopilot

You are the senior full-stack engineer working on **LolixCopilot**, a real Golixco product whose first release is for the Meta Global AI Developer Hackathon.

## Work style

1. Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/HACKATHON_EXECUTION_PLAN.md` before coding.
2. Work in small, end-to-end milestones. Do not attempt a giant rewrite in one pass.
3. Inspect the current repository before editing. Do not replace working code or rewrite files without understanding them.
4. After each milestone, run the relevant tests, lint, type-check, and build. Fix errors before continuing.
5. Keep `docs/IMPLEMENTATION_STATUS.md` up to date with completed work, commands run, failures, and the next concrete task.
6. If an environment variable is missing, implement a safe configuration path and update `.env.example`; do not ask the user to paste secrets into chat or source files.
7. Never claim a live API integration works until an explicit smoke test has passed with the user's local credentials.
8. No real Meta API calls from tests or default app startup. Unit/integration tests must use mocked providers.
9. Do not add a dependency, service, model, GPU, or paid feature just because it is available. Explain its user-facing value and cost first.
10. Keep the MVP achievable for the hackathon. Defer stretch features if the upload → analysis → editing blueprint flow is not stable.

## Product decisions that must remain consistent

- Brand name in UI: **LolixCopilot**.
- Repository slug: `lolixco-pilot`.
- Tagline: **From raw footage to a stronger cut.**
- Audience: independent video editors and short-form creators.
- Main output: a useful editing blueprint with approximate timestamped moments and reasons, not a finished exported video.
- Visual identity: premium dark editing studio; near-black and charcoal surfaces, restrained neon yellow accent, crisp off-white typography, clear timecodes, subtle borders, excellent keyboard/focus states. Avoid generic purple AI gradients, noisy glow effects, and excessive glassmorphism.
- Keep this repository independent from the existing Lolixco codebase. Design clean API boundaries for later integration.

## Meta Model API rules

- Server-side only. Use `MODEL_API_KEY`; never expose it to the browser.
- Base URL: `https://api.meta.ai/v1`.
- Prefer the official OpenAI-compatible SDK surface if it fits the chosen endpoint; follow the current Meta docs for exact request and response schema.
- Start with `muse-spark-1.3` for video understanding only after validating it is enabled on the user's account. Use structured output where supported and validate it with Pydantic before saving.
- Use `muse-voice-transcribe-1.0` as a separate, optional transcription step if speech materially helps the edit plan. The current Meta docs warn that audio quality in `muse-spark-1.3` may be degraded for audio-containing requests; do not rely on that path for accurate transcription.
- `sam-3.1` is for object detection, segmentation masks, and video tracking. It is a stretch feature, not a substitute for scene description.
- `muse-image-1.0` is an explicit user-triggered moodboard/cover-generation stretch feature. Never generate images automatically on every analysis.
- Handle rate limits, timeouts, unavailable models, malformed JSON, empty responses, and provider errors gracefully. Never silently fabricate model results.
- Respect the current Meta billing/dashboard terms. The user's screenshot explicitly warns that content processed while using free credits may be used for product improvement. Show a clear disclosure before upload and test with authorized, non-sensitive footage.

## Modal rules

- Read the installed Modal skill (`.agents/skills/**/SKILL.md`) before implementing or changing Modal-specific code. Install the official skill with `modal skills install` after the Modal CLI is installed and authenticated.
- Use Modal for app/API hosting and/or asynchronous media-processing functions only where it simplifies the chosen architecture. Use CPU for FFmpeg initially; do not reserve a GPU just to use the credits.
- Modal secrets must be configured in the Modal dashboard/CLI. Never hardcode `MODEL_API_KEY`, AWS credentials, Supabase service-role keys, or callback secrets.
- Use ephemeral working directories for processing. Do not store user uploads in Modal's ephemeral container filesystem as the source of truth.
- Use private object storage for durable originals. Pass short-lived presigned URLs to workers; avoid putting credentials in URLs beyond the necessary signed URL and never log signed URLs.
- Inspect Modal logs and credit usage after deployments; don't leave unneeded warm GPU containers running.

## Storage, privacy, and security rules

- S3 bucket private; public access blocked; browser uploads use short-lived presigned PUT URLs and originals are played back with short-lived presigned GET URLs.
- Never accept arbitrary remote URLs from users for server-side fetching; that creates SSRF risk. Inference URLs must be minted by our own backend for known S3 object keys.
- Validate file extension, MIME type, byte size, duration, ownership, and actual media metadata with `ffprobe` before expensive inference.
- Initial limits: MP4/MOV/WebM; max 60 seconds and 100 MB. Make limits configurable. Do not trust browser metadata.
- Use an explicit retention policy and delete action. Hackathon default: expire originals and derived previews after 7 days unless the owner explicitly deletes earlier; keep the policy configurable for production.
- Do not store presigned URLs in the database; store object keys and generate URLs on demand.
- Use UUID identifiers, authenticated access, least-privilege cloud permissions, CORS allowlists, request-size limits, rate limiting, and safe error messages.
- Do not log video content, full prompts that may contain private details, auth headers, signed URLs, or API keys.

## UX and accessibility rules

- Every long-running action needs visible progress states: Uploading → Preparing footage → Understanding scenes → Building blueprint → Ready / Needs attention.
- All video, thumbnails, and timeline timestamps must remain in sync. Clicking a scene seeks the player.
- Render AI timestamps as **suggestions**; validate `0 <= start < end <= duration` and flag low-confidence timing rather than implying frame-perfect edits.
- Provide empty, loading, success, error, and retry states. Do not use fake progress percentages that imply work completion.
- Support keyboard navigation, visible focus, readable contrast, reduced motion, responsive layouts, and accessible labels.

## Definition of done for each milestone

- Code is formatted and type-checked.
- Tests cover success and error paths without paid API calls.
- No secrets or generated user videos are tracked by Git.
- README/setup instructions reflect actual implemented behavior.
- `docs/IMPLEMENTATION_STATUS.md` records the files changed and test results.
