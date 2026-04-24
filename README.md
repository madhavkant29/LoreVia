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
  Includes JWT auth, refresh flows, session handling, and Stripe billing hooks for pricing plans.

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
- Single Celery worker (MVP) consuming extraction, analysis, embedding, and intelligence queues

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
OPENAI_INTEL_MODEL=gpt-4o
OPENAI_EMBED_MODEL=text-embedding-3-small

S3_BUCKET=local-dev
S3_ENDPOINT_URL=file:///app/storage
AWS_ACCESS_KEY_ID=local-dev
AWS_SECRET_ACCESS_KEY=local-dev

JWT_SECRET=replace_with_a_long_random_secret

STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder

RESEND_API_KEY=dummy
SENTRY_DSN=
CLOUDFLARE_TUNNEL_TOKEN=

FREE_MAX_BOOKS=999
```

Notes:

- Do not paste any real secret values into this README.
- Keep `backend/.env.local` out of version control.
- For local development, file storage is mounted to a Docker volume instead of cloud storage.

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

This starts (MVP single-worker mode):

- `api`
- `worker`
- `postgres`
- `redis`
- `flower`

#### Rollback (full multi-worker isolation)

If you want the original queue isolation (or you hit user-facing latency issues), use:

```bash
docker compose -f docker-compose-local.multiworkers.yml up --build
```

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
