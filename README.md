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

Phase 0 completed: application scaffold, premium dark editor design system, environment configuration validation, health endpoint (`GET /api/health`), strict Pydantic blueprint schemas, and end-to-end type-checking/testing suites established.

See `docs/PRODUCT_SPEC.md` for the MVP, `docs/ARCHITECTURE.md` for the technical design, `docs/HACKATHON_EXECUTION_PLAN.md` for delivery milestones, and `docs/IMPLEMENTATION_STATUS.md` for current progress.

## Implemented architecture

- **Frontend (`frontend/`):** Next.js 16 (App Router) + TypeScript + Tailwind CSS with dark studio visual identity (near-black `#0a0c0f`, charcoal `#111418`, neon yellow `#e6ff00`, monospace timecodes, accessible focus rings).
- **Backend (`backend/`):** FastAPI ASGI application with strict CORS allowlist, environment settings validation (Pydantic Settings), public health endpoint (`/api/health`), and Pydantic schemas validating the Editing Blueprint data contract.
- **Zero-Leak Policy:** Server secrets (`MODEL_API_KEY`, AWS credentials, Supabase service keys) are never exposed via API endpoints or frontend bundles. No external API calls occur in automated test suites.

## Developer quickstart

### Prerequisites

- Node.js `v20+` (verified on `v24.18.0`) and npm (`11.16.0`)
- Python `3.11+` (verified on `3.13.14`)

### Setup

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Setup Backend Virtualenv & Dependencies:**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
   ```
3. **Setup Frontend Dependencies:**
   ```bash
   npm --prefix frontend install
   ```

### Running locally

- **Run Frontend Dev Server (port 3000):**
  ```bash
  npm run dev:frontend
  ```
- **Run Backend FastAPI Server (port 8000):**
  ```bash
  npm run dev:backend
  ```

### Verification & tests

Run all static analysis, type checks, and tests with zero external API calls:
```bash
# Run everything:
npm run check:all

# Or individually:
npm run lint         # ESLint (frontend) + Ruff (backend)
npm run type-check   # tsc (frontend) + Mypy strict (backend)
npm test             # Vitest (frontend) + Pytest (backend)
```

## Security and privacy

Never commit a real `.env` file, API keys, cloud credentials, or user footage. Originals belong in private object storage and should be accessed with short-lived signed URLs. The Meta dashboard screenshot used during planning warns that content processed while using free credits may be used for product improvement. Until the account's exact terms are confirmed, use only authorized, non-sensitive demo footage.

## References

- Meta Model API: https://dev.meta.ai/docs/overview
- Meta video understanding: https://dev.meta.ai/docs/video-understanding
- Modal skills: https://modal.com/docs/cli/latest/skills
