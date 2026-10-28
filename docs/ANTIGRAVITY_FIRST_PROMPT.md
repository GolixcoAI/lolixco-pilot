# First Prompt for Antigravity

Copy this prompt into Antigravity after the `GolixcoAI/lolixco-pilot` repository is created and these documents are committed.

---

You are the senior full-stack engineer for **LolixCopilot**, a long-term Golixco product. The Meta Global AI Developer Hackathon is our first delivery milestone, not the end of the project.

Before editing code, read `AGENTS.md`, `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/HACKATHON_EXECUTION_PLAN.md`. Also inspect the whole repository and any installed Modal Agent Skill under `.agents/skills/`. If Modal skills are missing, tell me to install them with `modal skills install` after the CLI is authenticated; do not guess current Modal APIs.

## Goal

Build a polished, reliable MVP that turns a short uploaded video plus a creative brief into a structured editing blueprint with timestamped scene recommendations. The editor must be able to click a recommendation and seek the video player to that moment. This is a recommendation/coplan product, not a finished-video renderer.

## Operating rules

- Follow the docs as the source of truth. If a change is necessary, update the docs first and explain the trade-off.
- Implement one vertical slice at a time and keep the project runnable after each slice.
- First write `docs/IMPLEMENTATION_STATUS.md` with the repository assessment, planned phases, and missing configuration; then implement Phase 0 only (app scaffolding, visual design tokens, health route, environment config, tests, and README setup). Run checks and report exact results.
- Do not generate a large all-at-once code dump. After Phase 0, continue through the phases in `docs/HACKATHON_EXECUTION_PLAN.md` in small changes.
- Never modify or copy the existing Lolixco repository. This is the independent `lolixco-pilot` repo.
- Use actual Meta and Modal documentation. Never invent API payloads, model identifiers, SDK calls, or environment variable names. Current Meta API base URL is `https://api.meta.ai/v1`, but verify the model list and request schema before implementing the provider.
- Keep `MODEL_API_KEY`, Supabase service-role credentials, AWS credentials, and Modal tokens server-side only. Add placeholders to `.env.example`, never real values.
- Automated tests must mock Meta/S3/Modal and must not make real model calls or incur credits. Add a separate explicit smoke-test script that runs only when the user invokes it and confirms required env vars are set.
- Show a data-use notice before upload because the Meta dashboard says free-credit content may be used for product improvement. The test fixture clips must be authorized and non-sensitive.
- Use a private S3 bucket and short-lived presigned URLs. Never store a presigned URL in the database or logs. Never accept arbitrary user-provided remote URLs.
- Use Modal CPU functions for initial FFmpeg/ffprobe processing. Do not deploy an always-on GPU or host a copy of Meta's model unless we prove a measured need.
- If model output is invalid, show a retryable error instead of manufacturing an answer. Validate timestamps within the video duration.
- UI design: near-black/charcoal editor studio, neon-yellow primary accent, crisp off-white typography, clear timecodes, dense but readable scene cards, careful spacing, restrained motion, keyboard accessibility, and no generic purple AI gradients.
- Keep feature scope small enough to deliver, test, and demo before the official deadline. If behind schedule, cut stretch features using the order in `docs/HACKATHON_EXECUTION_PLAN.md`.

## MVP order

1. Repository assessment, app shell, design system, health route, lint/typecheck/test setup.
2. Auth + metadata schema + private S3 presigned upload and delete.
3. Modal worker for media validation and thumbnails.
4. Meta Muse Spark video-analysis provider and validated editing blueprint.
5. Results studio with timeline, video seek, progress, retry, and error states.
6. Optional transcription or moodboard only after the core path passes end-to-end tests.
7. Deploy, audit security/credits, write demo script, and freeze features.

## Report after each milestone

Include: what changed, files touched, commands run, test/build results, required manual setup, known limitations, and the next highest-priority task. Do not claim success for any step that was not run and verified.

Start now with repository inspection and Phase 0 only.

---
