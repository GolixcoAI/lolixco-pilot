# LolixCopilot — Hackathon Execution Plan

**Planning date:** October 28, 2026  
**Hackathon submission date listed by the event:** November 4, 2026, 9:00 PM ET. Verify the live page and submit well before it.  
**Internal deadline:** November 4, 2026, 8:00 PM IST.

## Priority order

1. An end-to-end flow that works on a real clip.
2. Trustworthy output and clear disclosure/retention behavior.
3. Polished editing-studio experience.
4. Reliable deployment and a concise demo.
5. Stretch Meta model capabilities only after the core path is stable.

## Daily plan

### Day 1 — October 28: Repository, setup, and technical spike

- Create `GolixcoAI/lolixco-pilot` and add this starter pack.
- Install the official Modal skill in Antigravity; authenticate Modal CLI locally.
- Create Meta Model API key, Supabase project, private S3 bucket, and Modal secrets. Never place secret values in repo files or chat.
- Validate one small authorized test video with `muse-spark-1.3` using the current official video-understanding example.
- Verify `ffprobe`/FFmpeg can inspect the exact test clip locally or in a Modal CPU function.
- Set `docs/IMPLEMENTATION_STATUS.md` and create `.env.example`.

**Gate:** Don't build out UI until the team has verified that the account can analyze the test video with the documented API request. If this fails, diagnose it immediately.

### Day 2 — October 29: App shell + secure upload

- Create Next.js app shell, brand system, navigation, upload dropzone, and project workspace.
- Add Supabase Auth and the `analyses` schema/RLS, or use a tightly scoped authenticated demo path if auth setup blocks progress.
- Implement presigned S3 PUT upload and owner checks.
- Add MIME, extension, content-size, actual duration, and file metadata validation.
- Add consent/data-use disclosure and delete action.

**Gate:** A user can upload a supported test clip to a private bucket; the app does not expose a public S3 URL.

### Day 3 — October 30: Modal pipeline

- Add Modal ASGI API and async processing function, following the installed Modal skill.
- Add ffprobe metadata validation, thumbnail extraction, ephemeral cleanup, and job states.
- Test function errors, invalid file, missing audio stream, oversized clip, timeout, and retries.

**Gate:** Uploaded video can produce metadata and thumbnails, and status survives page refresh.

### Day 4 — October 31: Meta video understanding

- Implement the Meta provider adapter using `MODEL_API_KEY` on the server only.
- Send the video URL/file reference as documented in the current Meta API.
- Ask for the structured creative brief and timestamped moments; validate result with Pydantic.
- Store analysis JSON, safe errors, model id, and usage metadata when available.
- Test malformed/empty results and provider failures with mocks.

**Gate:** A real, authorized test clip reliably produces a validated editing blueprint from the deployed backend.

### Day 5 — November 1: The editing studio experience

- Build the central video player and timeline.
- Build timestamped scene cards with thumbnail, moment, why-it-works, and editing direction.
- Click a scene to seek the video; ensure timecode formatting is stable.
- Add real progress stages, empty/loading/failed states, retry, and responsive layout.
- Add realistic sample project only if the sample video is licensed/authorized.

**Gate:** A new user can complete the main workflow without developer instructions.

### Day 6 — November 2: Quality, UX polish, and one optional Meta capability

- Add keyboard/focus states, accessibility checks, useful error copy, mobile layout, and reduced-motion support.
- Verify timestamps against clip duration and mark approximate recommendations honestly.
- If core path is stable, add separate Muse Voice Transcribe for clips with speech, or a single explicit Muse Image moodboard action — choose one, not both unless time remains.
- Run upload/load/error regression tests.

**Gate:** The product feels cohesive and no core workflow regressed.

### Day 7 — November 3: Deployment, testing, and demo capture

- Deploy frontend and Modal app; verify production CORS and environment variables.
- Run smoke test from a clean browser session with one clip.
- Verify no keys are present in the frontend bundle, logs, or Git history.
- Confirm S3 private access, expiration rule, deletion behavior, and user isolation.
- Prepare a 90–120 second demo script and record a backup video.
- Add screenshots, architecture diagram, setup steps, limitations, and model attribution to README.

**Gate:** A reviewer can understand what it does in 30 seconds and see it work in 2 minutes.

### Day 8 — November 4: Buffer and final submission

- Freeze features; fix blockers only.
- Verify hackathon track, submission requirements, license/ownership rules, repository visibility, and demo URL.
- Submit before the internal deadline of 8:00 PM IST. Confirm the event's current deadline on the official page.

## Strict feature cut line

If schedule slips, remove these in order:

1. SAM 3.1 object tracking UI.
2. Muse Image moodboard generation.
3. Speech transcription.
4. Project history beyond the current workspace.

Do **not** remove upload integrity, private storage, real Meta inference, schema validation, job status, timestamp click-to-seek, or the demo reliability pass.

## Demo script (target 90–120 seconds)

1. Introduce a real creator problem: footage is easy to capture, but finding a compelling sequence is slow.
2. Upload an authorized 20–45 second clip and enter one specific creative brief.
3. Show honest progress stages while Modal prepares the clip and Meta analyses it.
4. Show the editing blueprint: hook, scene sequence, reasons, pacing, and ending.
5. Click two proposed moments; demonstrate the player seeking to the respective timestamps.
6. Show that this is a recommendation tool built for editors, not a generic video summary and not a fake automated final cut.
7. Close with the path to integrate EditPilot's stable capabilities into Lolixco later.

## Release checklist

- [ ] Current official rules and submission criteria checked.
- [ ] At least 3 authorized test clips pass, including one clip with speech and one without audio.
- [ ] Invalid file and provider failure paths tested.
- [ ] Timestamps validated against actual duration.
- [ ] Video storage is private and deletion works.
- [ ] Consent/data-use notice visible before upload.
- [ ] S3 lifecycle expiration configured.
- [ ] Modal CPU usage checked; no idle GPU endpoints.
- [ ] Model usage dashboard checked; no loops/retries that burn credits.
- [ ] No secret in Git or frontend source map/bundle.
- [ ] Public README, deployed demo, backup demo video, and clear limitations.
- [ ] Submission completed before the team's internal deadline.
