# LoreVia

LoreVia is an AI-powered reading workspace for long-form fiction. It helps readers move through dense novels and series without losing track of characters, relationships, events, themes, or prior chapters.

Instead of acting like a generic document chatbot, LoreVia is designed around the reading journey itself: progress-aware summaries, evolving character profiles, relationship tracking, spoiler-sensitive recall, grounded Q&A, saved quotes, and book-level navigation tools.

## What The Project Does

LoreVia lets a reader upload a book, process it into chapters and chunks, and explore it through a set of AI-assisted reading tools. The product is structured around three levels of understanding:

- `Character Engine` for the micro view of people, motivations, traits, aliases, and relationships
- `Event / Plot Tracker` for the meso view of what has happened so far
- `Theme / Cross-Book Analysis` for the macro view of recurring motifs, arcs, and multi-book continuity

The app is built as a full-stack system with asynchronous processing so that ingestion, extraction, and intelligence features can run independently from the main web app.

## Core Features

- `Book Upload and Parsing`
  Upload PDF or EPUB files and turn them into chapter-aware, searchable reading material.

- `Progress-Aware Reading`
  Track current chapter, reading progress, and chapter completion state.

- `Spoiler-Safe Summaries`
  Show summaries only for chapters the reader has already finished.

- `Character Engine`
  Build evolving character profiles with merged aliases, roles, motivations, fears, traits, and descriptions.

- `Relationship Graph and Evolution`
  Track how characters are connected and how those connections change through events over time.

- `Recall / Previously On`
  Generate quick recaps so a reader can resume a book without rereading old chapters.

- `Grounded Q&A`
  Let readers ask questions about the book and receive answers grounded in the text instead of speculative outputs.

- `Foreshadowing and Timeline Views`
  Surface earlier hints, major events, and arc progression from already-read material.

- `Thematic Search`
  Explore scenes and passages by idea or motif rather than just raw keyword matching.

- `Saved Quotes and Notes`
  Store quotes with metadata such as source book, chapter, and optional character context.

- `Library and Shelf Management`
  Keep books in the library, archive them, or hide them from the UI while still preserving usage accounting.

- `Authentication and Billing Foundations`
  Includes JWT auth, refresh flows, session handling, Paddle checkout and portal flows, and webhook-backed subscription updates for pricing plans.

## Architecture

LoreVia is split into a frontend, a FastAPI backend, background workers, and supporting infrastructure.

### Frontend

- `Next.js 15`
- `TypeScript`
- `Tailwind CSS`

The frontend handles authentication, library management, reading UI, pricing, settings, and all reader-side tools.

### Backend

- `FastAPI`
- `SQLAlchemy`
- `PostgreSQL + pgvector`
- `Redis`

The backend manages auth, uploads, parsing, progress tracking, book metadata, character and relationship APIs, summaries, search, and billing routes.

### Background Processing

- `Celery`
- Separate worker queues for extraction, analysis, embedding, and intelligence tasks

Workers parse books, generate chunks, compute embeddings, extract characters and relationships, and produce derived reading features.

### Infrastructure

- `Docker Compose`
- `Postgres`
- `Redis`
- Local object storage mounted through a Docker volume for development

## How LoreVia Works

1. A user uploads a book.
2. The backend stores the file and records a book entry.
3. Workers parse the book into chapters and chunks.
4. AI-backed extraction builds summaries, character data, relationships, and retrieval context.
5. The frontend exposes those features through a structured reading workspace.
6. User progress determines what the app should reveal and what it should keep spoiler-safe.

## Running Locally

This project is intended to run locally with Docker only.

### Prerequisites

- `Docker Desktop`
- Available ports:
  - `3000` for the frontend
  - `5432` for Postgres
  - `6379` for Redis
  - `8000` for the API
  - `5555` for Flower

### 1. Create backend environment file

Create `backend/.env.local` and add your local values.

Use this template:

```env
APP_NAME=LoreVia
DEBUG=true
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lorevia
REDIS_URL=redis://redis:6379/0

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EXTRACT_MODEL=gpt-4o-mini
OPENAI_INTEL_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

S3_BUCKET=local-dev
S3_ENDPOINT_URL=file:///app/storage
AWS_ACCESS_KEY_ID=local-dev
AWS_SECRET_ACCESS_KEY=local-dev

JWT_SECRET=replace_with_a_long_random_secret

PADDLE_API_KEY=pdl_live_or_sandbox_key_here
PADDLE_WEBHOOK_SECRET=pdl_webhook_secret_here
PADDLE_READER_MONTHLY_PRICE_ID=pri_reader_monthly
PADDLE_READER_ANNUAL_PRICE_ID=pri_reader_annual
PADDLE_AUTHOR_MONTHLY_PRICE_ID=pri_author_monthly
PADDLE_AUTHOR_ANNUAL_PRICE_ID=pri_author_annual
PADDLE_ARCHITECT_MONTHLY_PRICE_ID=pri_architect_monthly
PADDLE_ARCHITECT_ANNUAL_PRICE_ID=pri_architect_annual
PADDLE_DEFAULT_CHECKOUT_URL=http://localhost:3000/pricing

RESEND_API_KEY=dummy
INTERNAL_JOB_SECRET=replace_with_an_internal_job_secret
SENTRY_DSN=
CLOUDFLARE_TUNNEL_TOKEN=

FREE_MAX_BOOKS=999
```

Notes:

- Do not paste any real secret values into this README.
- Keep `backend/.env.local` out of version control.
- For local development, file storage is mounted to a Docker volume instead of cloud storage.
- Paddle checkout requires the API key, webhook secret, and plan price IDs to be set together.
- Trial lifecycle emails can be run from a scheduler with `python backend/scripts/run_due_trial_emails.py --limit 100` or through the protected internal job endpoint.

### 2. Create frontend environment file

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 3. Start the full stack

From the project root:

```bash
docker compose -f docker-compose-local.yml up --build
```

This starts:

- `api`
- `worker-extraction`
- `worker-analysis`
- `worker-intelligence`
- `postgres`
- `redis`
- `flower`

### 4. Open the app

- Frontend: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Flower: [http://localhost:5555](http://localhost:5555)

## Stopping The App

```bash
docker compose -f docker-compose-local.yml down
```

To remove containers, networks, and volumes:

```bash
docker compose -f docker-compose-local.yml down -v
```

## Testing

LoreVia now has backend tests, frontend unit tests, and frontend E2E smoke tests.

### Backend tests

From the repo root:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests -v
```

Notes:

- Prefer Docker Compose Local so tests run against the repo's pinned app image, Postgres, Redis, and extensions.
- DB-backed backend tests require the local compose stack and required extensions such as `pgvector`.

### Frontend unit tests

From the repo root:

```powershell
cd frontend
npm.cmd test
```

This runs the Vitest suite for frontend utilities, stores, API wrappers, config, and security-sensitive frontend logic.

### Frontend E2E smoke tests

From the repo root:

```powershell
cd frontend
npm.cmd run test:e2e
```

Notes:

- These smoke tests run against the local Next.js dev server, not production.
- The suite mocks API traffic in the browser, so it does not require a live backend to verify the core UI flows.
- The Playwright config uses Playwright-managed Chromium so the same browser engine can run locally and in CI.

### Will these fail in non-production environments?

Not just because the environment is non-production.

- Backend tests should pass in local or CI-style non-production environments as long as the Python environment, local test database, and required extensions are present.
- Frontend unit tests should pass in local or CI-style non-production environments as long as Node dependencies are installed.
- Frontend E2E smoke tests are intentionally non-production-friendly because they run against a local dev server with mocked API responses.
- The CI pipeline runs the same frontend unit and E2E smoke suites, so a passing local run should match CI as long as dependencies and browser prerequisites are present.

They can still fail if the environment is missing prerequisites such as:

- backend venv or Python dependencies
- local test database / `pgvector`
- frontend `node_modules`
- a supported Playwright browser runtime

## Project Structure

```text
LoreVia/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── engine/
│   │   ├── models/
│   │   ├── parsers/
│   │   ├── services/
│   │   └── workers/
│   ├── Dockerfile.api
│   └── Dockerfile.worker
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── types/
├── docker-compose-local.yml
└── README.md
```

## Why This Project Matters

LoreVia was built to solve a real reading problem: long books are hard to hold in working memory. Readers often forget who a character is, when an event happened, or why a relationship matters. This project turns that pain point into a full product experience by combining retrieval, summarization, entity extraction, asynchronous processing, and a focused reading UI.
