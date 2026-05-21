# LoreVia

LoreVia is an AI-powered manuscript intelligence platform for fiction authors. It helps authors understand, revise, and maintain continuity in complex manuscripts across characters, relationships, plot threads, worldbuilding, and cross-book arcs.

Instead of acting like a generic document chatbot, LoreVia is organized around the author workflow itself: continuity-aware summaries, evolving character profiles, relationship tracking, grounded Q&A, manuscript notes, export tools, and invite-only collaborator surfaces when they are needed.

## What The Project Does

LoreVia lets an author upload a manuscript or book, process it into chapters and chunks, and work with it through a set of AI-assisted continuity tools. The product is structured around three levels of understanding:

- `Character Engine` for the micro view of people, motivations, traits, aliases, and relationships
- `Plot / Continuity Tracker` for the meso view of what has happened, what is unresolved, and what may break
- `Theme / Cross-Book Analysis` for the macro view of recurring motifs, arcs, and multi-book continuity

The app is built as a full-stack system with asynchronous processing so that ingestion, extraction, and intelligence features can run independently from the main web app.

## Core Features

- `Manuscript Upload and Parsing`
  Upload PDF, EPUB, DOCX, DOC, or text-based manuscript files and turn them into chapter-aware, searchable drafting material.

- `Author Continuity Workspace`
  Track book mode, chapter progress, draft state, and editing context in a workspace built for revision.

- `Continuity-Aware Summaries`
  Show summaries, chapter notes, and recall only within the spoiler boundaries that the book and user context allow.

- `Character Engine`
  Build evolving character profiles with merged aliases, roles, motivations, fears, traits, and descriptions.

- `Relationship Graph and Evolution`
  Track how characters are connected and how those connections change through events over time.

- `Continuity Recall / Previously On`
  Generate quick recaps so an author or collaborator can resume a draft without rereading old chapters.

- `Grounded Q&A`
  Ask questions about the book or manuscript and receive answers grounded in the text instead of speculative outputs.

- `Foreshadowing and Timeline Views`
  Surface earlier hints, major events, and arc progression from already-processed material.

- `Thematic Search`
  Explore scenes and passages by idea or motif rather than just raw keyword matching.

- `Annotations, Notes, and Saved Quotes`
  Store passages with metadata such as source book, chapter, and optional character context.

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

The frontend handles authentication, library management, manuscript editing, pricing, settings, and all author-side continuity tools.

### Backend

- `FastAPI`
- `SQLAlchemy`
- `PostgreSQL + pgvector`
- `Redis`

The backend manages auth, uploads, parsing, progress tracking, book metadata, character and relationship APIs, summaries, search, and billing routes.

### Background Processing

- `Celery`
- Separate worker queues for extraction, analysis, embedding, and intelligence tasks

Workers parse books, generate chunks, compute embeddings, extract characters and relationships, and produce derived continuity features.

### Infrastructure

- `Docker Compose`
- `Postgres`
- `Redis`
- Local object storage mounted through a Docker volume for development

## How LoreVia Works

1. An author uploads a manuscript or book.
2. The backend stores the file and records a book entry.
3. Workers parse the source into chapters and chunks.
4. AI-backed extraction builds summaries, character data, relationships, and retrieval context.
5. The frontend exposes those features through a structured author continuity workspace.
6. Book state determines what the app should reveal and what it should keep spoiler-safe.

## Running Locally

This project is intended to run locally with Docker only. Production deployment is on a Hetzner VPS, with Nginx in front of a Gunicorn-managed FastAPI backend and Cloudflare-origin TLS for the current edge setup.

### Prerequisites

- `Docker Desktop`
- Available ports:
  - `3000` for the frontend
  - `5432` for Postgres
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
REDIS_PASSWORD=replace_local_redis_password

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
PADDLE_AUTHOR_MONTHLY_PRICE_ID=pri_author_monthly
PADDLE_AUTHOR_ANNUAL_PRICE_ID=pri_author_annual
PADDLE_ARCHITECT_MONTHLY_PRICE_ID=pri_architect_monthly
PADDLE_ARCHITECT_ANNUAL_PRICE_ID=pri_architect_annual
PADDLE_DEFAULT_CHECKOUT_URL=http://localhost:3000/checkout

RESEND_API_KEY=dummy
INTERNAL_JOB_SECRET=replace_with_an_internal_job_secret
SENTRY_DSN=
CLOUDFLARE_TUNNEL_TOKEN=

FREE_MAX_BOOKS=999
```

Notes:

- Do not paste any real secret values into this README.
- Keep `backend/.env.local` out of version control.
- Local Docker Compose injects `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` using the internal `redis` hostname and the `REDIS_PASSWORD` value above.
- For local development, file storage is mounted to a Docker volume instead of cloud storage.
- Paddle checkout requires the API key, webhook secret, and plan price IDs to be set together.
- In Paddle Checkout settings, set the default payment link to your public HTTPS checkout page, such as `https://getlorevia.com/checkout` on the Hetzner deployment or `http://localhost:3000/checkout` in local sandbox testing.
- Trial lifecycle emails can be run from a scheduler with `python backend/scripts/run_due_trial_emails.py --limit 100` or through the protected internal job endpoint.

Production deployment notes for the Hetzner VPS live in [ops/production-firewall-and-monitoring.md](/C:/Users/madha/.vscode/prod/LoreVia2/ops/production-firewall-and-monitoring.md), [docs/hetzner-redis-operations.md](/C:/Users/madha/.vscode/prod/LoreVia2/docs/hetzner-redis-operations.md), and [docs/hetzner-service-management.md](/C:/Users/madha/.vscode/prod/LoreVia2/docs/hetzner-service-management.md). Production Compose now reads interpolation values from `backend/.env` via `--env-file`.

### 2. Create frontend environment file

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=test_your_paddle_client_side_token_here
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

LoreVia has backend tests, frontend unit tests, and frontend E2E smoke tests.

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

LoreVia was built to solve a real writing problem: long manuscripts are hard to keep consistent over time. Authors and collaborators lose track of character state, unresolved promises, chapter history, and cross-book continuity. This project turns that pain point into a full product experience by combining retrieval, summarization, entity extraction, asynchronous processing, and a focused author continuity workspace.
