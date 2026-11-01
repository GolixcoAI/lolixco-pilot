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

- **Phase 0 (Complete):** Application scaffold, dark editing workstation design system, environment configuration, health endpoint (`GET /api/health`), strict Pydantic blueprint schemas, and unified checks.
- **Phase 1 (Complete):** Real video upload lifecycle directly to private Amazon S3 using short-lived presigned PUT URLs, server-side object verification (`head_object`), Supabase anonymous authentication without login UI, project & media persistence across page reloads, 7-day auto-retention policy, and comprehensive zero-cost test suites.
- **Phase 2 (Complete):** Dual provider adapters for **Baseten** (`meta-models/muse-spark-open-1026`) and **Meta Model API** (`muse-spark-1.3`), media intelligence feature ("Identify source, characters & soundtrack") with confidence ratings, bounded audio extraction and probing service, AI Director UI with provider toggle and contextual suggestion, editor feedback & correction loop, Supabase analyses persistence with RLS, and controlled CLI smoke-test script (`scripts/smoke_test_inference.py`).
- See `docs/PHASE1_SETUP.md` for manual cloud setup instructions.
- See `docs/PRODUCT_SPEC.md` for the MVP, `docs/ARCHITECTURE.md` for technical design, `docs/HACKATHON_EXECUTION_PLAN.md` for milestones, and `docs/IMPLEMENTATION_STATUS.md` for detailed progress.

## Implemented architecture

- **Frontend (`frontend/`):** Next.js 16 (App Router) + TypeScript + Tailwind CSS with dark studio workstation (near-black `#050505` / `#0d1016`, charcoal `#1f2433`, neon yellow accent `#ffe600`, monospace timecodes, accessible focus states). Features provider toggle (`Baseten` vs `Meta AI`), contextual suggestion banner ("Video uploaded. Want me to identify the source, characters and soundtrack?"), media intelligence display, editor feedback submission, and direct-to-S3 video uploads with honest progress bars.
- **Backend (`backend/`):** FastAPI ASGI application with Supabase PostgREST repository layer, private Amazon S3 storage service (`boto3` + mock provider fallback), dual provider adapters for Baseten and Meta Model API, media intelligence and blueprint generation, bounded audio extraction service (`LocalMediaProcessingService`), cost protection caching and idempotency, and 7-day auto-retention handling.
- **Database & Storage:** PostgreSQL migrations with Row Level Security (`supabase/migrations/20261101180000_media_intelligence_and_analyses_persistence.sql`) persisting media assets, analyses, and editor feedback scoped to authenticated user IDs; and private S3 bucket configuration with Block Public Access and CORS.
- **Research & Optimization:** Empirical evaluation of Muse Spark Open reasoning effort (`docs/research/MUSE_EXPERIMENTS_NOTES.md`), Modal architecture & cost analysis (`docs/research/MODAL_ARCHITECTURE_AND_EVALUATION.md`), Baseten vs Modal inference comparison (`docs/research/BASETEN_VS_MODAL_INFERENCE_COMPARISON.md`), and anime event dataset specification (`docs/research/JUJUTSU_KAISEN_EVENT_DATASET_SPEC.md`).
- **Zero-Credit-Consumption Policy:** Server secrets (`BASETEN_API_KEY`, `MODEL_API_KEY`, AWS credentials, Supabase service keys) are never exposed via API endpoints or frontend bundles. No external API calls or credit-consuming workloads occur in automated test suites (Meta $150, Modal $100, Baseten $100, and AWS $120 credits remain 100% protected).

## Developer quickstart

### Prerequisites

- Node.js `v20+` (verified on `v24.18.0`) and npm (`11.16.0`)
- Python `3.11+` (verified on `3.13.14`)

### Setup

1. **Configure Environment:**
   ```bash
   # Server-side configuration (FastAPI)
   cp .env.example .env

   # Frontend configuration (Next.js)
   cp .env.example frontend/.env.local
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
