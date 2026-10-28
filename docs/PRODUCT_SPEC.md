# LolixCopilot — Product Specification

## 1. Product identity

- **Name:** LolixCopilot
- **Company:** Golixco
- **Repository:** `GolixcoAI/lolixco-pilot`
- **Tagline:** From raw footage to a stronger cut.
- **Category:** AI creative pre-production and editing assistant

## 2. Product thesis

Editors often know the feeling or story they want a video to convey but spend time reviewing footage, locating the useful moments, and deciding on a sequence. LolixCopilot turns footage plus a plain-language creative brief into an editable plan that explains **what moment to use, where it occurs, and why it supports the story**.

The product is a creative copilot, not an autonomous editor. In the MVP it does not render, publish, or upload a finished cut to a social platform.

## 3. Target user

Primary: solo video editors and short-form creators who edit clips for Reels, Shorts, TikTok-style vertical videos, and cinematic/social edits.

Secondary: creators working with interviews, product footage, travel videos, sports clips, or authorized original footage.

Initial demo clips must be original, licensed, public-domain, or otherwise explicitly authorized for analysis. Do not build the demo around copyrighted TV/anime footage unless the team has rights to process and display it.

## 4. Core user story

> As a video editor, I want to upload a short clip, explain the edit I am trying to make, and receive a structured timeline of promising moments and editing recommendations so that I can get from raw footage to a clear first cut faster.

## 5. MVP workflow

1. User opens the studio and chooses a demo clip or uploads a supported short video.
2. User enters a creative brief, for example: “Create a tense 30-second cinematic teaser; prioritize movement and emotional reactions.”
3. UI explains what will be processed and links to the privacy/retention information.
4. Client uploads directly to a private S3 bucket using a short-lived presigned URL.
5. Backend validates metadata and creates an analysis job.
6. A Modal worker uses FFmpeg/ffprobe to validate the clip, derive metadata, and generate a small number of thumbnail frames.
7. Meta Muse Spark analyses the video and returns candidate moments and creative direction. If enabled and speech is present, Muse Voice Transcribe provides a separate transcript; do not trust Muse Spark 1.3 alone for precise speech transcription.
8. Backend validates the response against a schema, clamps/flags invalid timestamps, persists the blueprint, and marks the job ready.
9. User sees the original video, a timestamped scene list, and a timeline. Selecting a scene seeks the player to the proposed moment.
10. User can retry a failed analysis or delete their project.

## 6. MVP scope — must ship

- Professional landing/studio screen with one clear primary action.
- Video upload, validation, cancel/retry/error paths.
- Creative brief form with a few presets (Cinematic, Hype, Story, Product, Interview).
- Durable analysis-job status and polling.
- Meta Muse Spark video understanding.
- Validated JSON editing blueprint.
- Video player with clickable timestamped scene cards.
- Thumbnail/contact sheet output.
- Results panel with summary, suggested hook, scene sequence, pacing notes, and recommended ending.
- Basic account/auth or a narrowly scoped authenticated demo session; do not leave unrestricted anonymous compute endpoints in production.
- Manual delete and automatic retention expiration.
- Cost-aware logging of model usage metadata where returned.
- Error and fallback UX that never substitutes invented AI output.
- README, architecture doc, setup instructions, demo script, and tests.

## 7. Stretch scope — only after MVP is stable

1. **Voice transcript alignment:** extract audio and call `muse-voice-transcribe-1.0`; associate transcript turns with scene recommendations.
2. **Object focus:** user names one object and `sam-3.1` returns masks/tracking for an opt-in visual overlay. Keep the feature disabled unless rendering and decoding are verified.
3. **Moodboard:** user explicitly clicks “Generate visual direction” to create a cover/concept image through `muse-image-1.0`.
4. Export the editing blueprint as JSON or a simple PDF/CSV/EDL-like draft. Do not promise compatibility with major NLEs until tested.
5. User accounts, saved projects, project history, and production retention controls.

## 8. Explicit non-goals for the hackathon

- Full nonlinear editing timeline or replacement for Premiere/DaVinci/CapCut.
- Automatic final video rendering, transitions, music licensing, or social publishing.
- Support for long-form videos, 4K originals, or unlimited uploads.
- Training or fine-tuning a foundation model.
- Deploying Muse Spark Open or another giant model on Modal. Meta already hosts the relevant API capability; do not duplicate inference without evidence that it is needed.
- Building every feature before one end-to-end path works.

## 9. Editing blueprint data contract

Validate the model output into an application-owned schema similar to:

```json
{
  "title": "string",
  "creative_intent": "string",
  "summary": "string",
  "target_duration_seconds": 30,
  "aspect_ratio": "9:16",
  "hook": "string",
  "scenes": [
    {
      "id": "scene-01",
      "start_seconds": 2.4,
      "end_seconds": 6.8,
      "moment": "What visibly happens",
      "why_it_works": "Why the moment supports the brief",
      "editing_direction": "Suggested cut/pacing/emphasis",
      "pacing": "slow | medium | fast",
      "confidence": 0.0,
      "thumbnail_key": "private S3 object key or null"
    }
  ],
  "sequence_rationale": "string",
  "ending_suggestion": "string",
  "caveats": ["string"]
}
```

The schema is a proposed application contract, not a claim that the model returns this structure automatically. The backend must validate/repair only safe formatting issues; if semantic output remains invalid, mark the job failed with a useful message.

Rules:

- `start_seconds` and `end_seconds` must be finite numbers and satisfy `0 <= start < end <= media_duration`.
- Each scene needs a reason and a useful editing action, not just a caption.
- Avoid overlapping scenes unless the result explicitly marks an intentional overlap.
- Do not fabricate confidence scores from the model. If no calibrated confidence is available, use `null` or an application-defined “unrated” state instead of a fake number.
- Tell users that AI-generated moment boundaries are suggestions and should be reviewed before editing.

## 10. Success criteria

The MVP is successful when a new user can upload a supported clip, submit a brief, see honest progress, receive a validated editing blueprint, click a suggested moment to seek the player, and delete the project. The experience should work from a deployed public demo with no developer-only steps.

Engineering success requires test coverage for file validation, provider errors, invalid model output, job lifecycle, permissions, and retention behavior.
