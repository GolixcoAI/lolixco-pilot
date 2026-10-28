# LolixCopilot

**From raw footage to a stronger cut.**

LolixCopilot is Golixco's AI-powered creative copilot for video editors. It turns a short video and a plain-language creative brief into a structured editing blueprint: promising moments, approximate timestamps, pacing suggestions, and a recommended narrative sequence.

This repository is being developed as a long-term product. The Meta Global AI Developer Hackathon is its first delivery milestone; the project should remain useful and maintainable after the event.

## Product goals

- Help editors find moments that support a creative intent.
- Turn raw footage into a useful, timestamped editing plan.
- Keep the editor in control: suggestions are reviewable, not an automatically rendered final video.
- Keep the AI integration and media pipeline modular so selected capabilities can later integrate with Lolixco.

## Current status

Planning and implementation scaffolding. See `docs/PRODUCT_SPEC.md` for the MVP, `docs/ARCHITECTURE.md` for the technical design, and `docs/HACKATHON_EXECUTION_PLAN.md` for delivery milestones.

## Intended stack

- Next.js + TypeScript + Tailwind CSS for the studio UI.
- FastAPI served on Modal, with Modal functions for media-processing jobs.
- Meta Model API for video understanding, with optional transcription/segmentation/image generation added only after the core path is reliable.
- Private Amazon S3 bucket for original video and derived previews.
- Supabase Auth/PostgreSQL for user identity and persistent job metadata.

## Security and privacy

Never commit a real `.env` file, API keys, cloud credentials, or user footage. Originals belong in private object storage and should be accessed with short-lived signed URLs. The Meta dashboard screenshot used during planning warns that content processed while using free credits may be used for product improvement. Until the account's exact terms are confirmed, use only authorized, non-sensitive demo footage.

## Start building

1. Read `AGENTS.md` and all documents under `docs/`.
2. Install the official Modal agent skill in Antigravity using `modal skills install` (see `docs/MODAL_SKILL_SETUP.md`).
3. Open `docs/ANTIGRAVITY_FIRST_PROMPT.md` and paste the prompt into Antigravity.
4. Implement one tested milestone at a time. Never run real paid AI calls in automated tests.

## References

- Meta Model API: https://dev.meta.ai/docs/overview
- Meta video understanding: https://dev.meta.ai/docs/video-understanding
- Modal skills: https://modal.com/docs/cli/latest/skills
