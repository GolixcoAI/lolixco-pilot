# LolixCopilot — Getting Started and Local Development Guide

This guide describes how to configure, run, and test LolixCopilot locally on Linux or macOS.

## Prerequisites

- Python 3.11, 3.12, or 3.13
- Node.js 20 LTS or later
- npm 10 or later
- FFmpeg and ffprobe installed and available on system PATH
- Git

## Repository Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/GolixcoAI/lolixco-pilot.git
cd lolixco-pilot
```

## Python Backend Setup

1. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install backend dependencies in editable mode:

```bash
pip install --upgrade pip
pip install -e backend
pip install -r backend/requirements-dev.txt
```

3. Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` to supply the following local credentials:

- `APP_ENV=development`
- `DATABASE_PROVIDER=memory` (or `supabase` if connecting to hosted database)
- `AI_PROVIDER=baseten` (or `meta` or `mock` for zero-credit local testing)
- `USE_MOCK_STORAGE=true` (or `false` when using real AWS S3 credentials)
- `MODEL_API_KEY` (Meta Model API key)
- `BASETEN_API_KEY` (Baseten API key)

4. Run the FastAPI development server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
```

The backend API will be available at `http://localhost:8000`.
Interactive OpenAPI documentation will be accessible at `http://localhost:8000/docs`.

## Node.js Frontend Setup

1. Install frontend dependencies:

```bash
cd frontend
npm install
```

2. Configure frontend environment:

Create `frontend/.env.local` if custom parameters are needed:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://fhfkjviishfvfyawfckh.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
```

3. Start the Next.js development server:

```bash
npm run dev
```

The workstation web interface will be accessible at `http://localhost:3000`.

## Running the Automated Test Suite

### Backend Unit and Integration Tests

Run the complete 197-test backend test suite using the virtual environment:

```bash
./.venv/bin/pytest backend/tests
```

All unit tests execute with mocked providers by default, consuming zero external API credits or cloud compute.

### Frontend Unit Tests

Run the 30-test Vitest suite:

```bash
npm test --prefix frontend
```

### Static Type Checking

Verify strict TypeScript compliance across all frontend components:

```bash
frontend/node_modules/.bin/tsc --noEmit --project frontend/tsconfig.json
```

### Comprehensive Local Acceptance Suite

With both frontend (`http://localhost:3000`) and backend (`http://localhost:8000`) running, execute the 6-step acceptance verification suite via Chrome DevTools Protocol:

```bash
./.venv/bin/python scripts/verify_acceptance_suite.py
```

This verifies:
1. Clean first-launch workstation state.
2. Natural-language chat greeting handling without premature timeline operations.
3. 60 fps synchronized video playback and audio timeline scrubbing.
4. Genuine multi-provider inference traces.
5. All three editing queries (Review my edit, Hollow Purple title overlay, last 30 seconds retention).
6. Asynchronous FFmpeg export rendering and frame verification.
