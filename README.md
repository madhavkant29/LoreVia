# LoreVia — AI-Powered Manuscript Intelligence Platform

LoreVia is a full-stack writing workspace that turns a fiction manuscript into chapter-aware, searchable story context. It tracks characters, relationships, plot threads, and continuity findings, and gives authors answers linked to source passages. The engineering work spans asynchronous ingestion, durable task recovery, retrieval with spoiler boundaries, and a production VPS deployment.

## Product Demo & Technical Walkthrough

The **4:35 narrated architecture walkthrough** follows a manuscript through the API, Celery queues, pgvector retrieval, recovery path, and deployment. Select the preview to see the short animated cut. The full 1920×1080 MP4 is generated at `portfolio-showcase/videos/lorevia-technical-walkthrough.mp4` locally; it is intentionally excluded from normal Git history until a Release asset or another authorized video host is available.

<a href="portfolio-showcase/technical-preview.gif"><img src="portfolio-showcase/technical-thumbnail.webp" alt="Preview of LoreVia technical walkthrough showing the verified system architecture" width="720"></a>

**[Open the technical preview](portfolio-showcase/technical-preview.gif)** · **[Read the full technical walkthrough](portfolio-showcase/TECHNICAL_WALKTHROUGH_TRANSCRIPT.md)** · [Subtitles](portfolio-showcase/subtitles.srt) · [Reproduction guide](portfolio-showcase/README.md)

The short product preview tours application screens populated with synthetic demo content. The full product demo follows an original sample manuscript through the authenticated application.

<a href="https://youtu.be/LVwVqo5X4LA"><img src="portfolio-showcase/product-thumbnail.webp" alt="Watch the LoreVia product demo" width="720"></a>

**[Watch the full product demo (6:02)](https://youtu.be/LVwVqo5X4LA)** · [Open the short product UI preview](portfolio-showcase/product-preview.gif)

## Key product capabilities

- **Manuscript ingestion:** bounded PDF, EPUB, DOCX, DOC, text, and Markdown uploads, structure preview, chapter parsing, and processing status.
- **Author workspace:** manuscript editor, chapter organization, notes, export tools, and reading or writing modes.
- **Story intelligence:** character profiles and alias review, relationship graph, timeline, plot threads, and continuity checks.
- **Grounded retrieval:** book-scoped search over chunks, chapter limits for spoiler control, and advisor responses with source references.
- **Collaborator and operations surfaces:** scoped book access, billing and webhooks, public sharing, and administrator review tools. See the [feature inventory](docs/feature-inventory.md) and [admin guide](docs/admin-guide.md).

## Screenshots

These are captures of the actual LoreVia interface with synthetic demo content. They contain no customer manuscript or account data.

**Manuscript workspace** — editor and context inspector.

<img src="portfolio-showcase/screenshots/manuscript-analysis.webp" alt="LoreVia manuscript editor with chapter context and continuity warnings" width="780">

**Character intelligence** — profile, aliases, review state, and evidence tabs.

<img src="portfolio-showcase/screenshots/character-continuity.webp" alt="Character Bible with Gregor profile, relationships, and review indicators" width="780">

**Relationship graph** — a chapter-filtered graph with character details.

<img src="portfolio-showcase/screenshots/relationship-graph.webp" alt="Character relationship graph with nodes, edges, and a detail panel" width="780">

**Continuity checking** — editorial feedback tied to a story issue.

<img src="portfolio-showcase/screenshots/editorial-review-2.webp" alt="Editorial review showing a continuity issue and scene verdict" width="780">

**Evidence-backed analysis** — answer with a chapter and passage reference.

<img src="portfolio-showcase/screenshots/manuscript-analysis-with-advisor.webp" alt="Manuscript advisor answer with a cited passage from Chapter 2" width="780">

**Notes workspace** — structured author notes alongside the manuscript.

<img src="portfolio-showcase/screenshots/notes-workspace.webp" alt="Author notes workspace with folders and editing controls" width="780">

## System architecture

The browser uses a Next.js 15 App Router frontend. Credentialed Axios requests pass through a same-origin `/api/v1` rewrite to FastAPI. The API applies authentication, Pydantic validation, and service-layer workflows. Async SQLAlchemy sessions use PostgreSQL; pgvector holds chunk and character embeddings. Redis is the Celery broker. File storage uses an S3-compatible abstraction with a local filesystem mode for development.

The five editable SVG diagrams are also available as PNG exports:

| View | Editable diagram | Rendered export |
| --- | --- | --- |
| System context | [System SVG](portfolio-showcase/diagrams/system.svg) | [PNG](portfolio-showcase/diagrams/system.png) |
| Upload and dispatch | [Ingestion SVG](portfolio-showcase/diagrams/ingestion.svg) | [PNG](portfolio-showcase/diagrams/ingestion.png) |
| Worker topology | [Workers SVG](portfolio-showcase/diagrams/workers.svg) | [PNG](portfolio-showcase/diagrams/workers.png) |
| AI and retrieval | [AI SVG](portfolio-showcase/diagrams/ai.svg) | [PNG](portfolio-showcase/diagrams/ai.png) |
| Deployment | [Deployment SVG](portfolio-showcase/diagrams/deployment.svg) | [PNG](portfolio-showcase/diagrams/deployment.png) |

See the [source-to-claim map](portfolio-showcase/EVIDENCE.md) and the broader [architecture notes](docs/ARCHITECTURE.md). Where documentation and source differ, the diagrams follow current source; for example, the worker launcher defines **five** roles and the database layer uses async `psycopg`.

## Technology stack

| Layer | Verified implementation |
| --- | --- |
| Web | Next.js 15, React 19, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| API | FastAPI, Pydantic, SQLAlchemy 2.x async sessions, Alembic |
| Data | PostgreSQL, pgvector, Redis, S3-compatible object storage |
| Background work | Celery, role-specific workers, Redis broker, Beat maintenance |
| AI | OpenAI extraction and embeddings, character resolution, hybrid vector and lexical search |
| Operations | Docker Compose, Nginx, Cloudflare API edge, Hetzner VPS, Vercel frontend, Sentry, GitHub Actions |

## Asynchronous processing and AI pipeline

1. The upload route validates size, file signature, structure, account allowance, and an active duplicate fingerprint.
2. The upload service stores the source and commits a `Book`, `BookProcessingRun`, and `TaskExecution` before dispatching work.
3. An extraction worker parses the manuscript and queues chapter work. Analysis and embedding tasks persist derived results.
4. Search embeds a question and filters `book_chunks` by book and chapter before using pgvector cosine similarity; hybrid search can combine lexical candidates.
5. Advisor and continuity features use bounded context and source references. Model output is validated and remains subject to author review.

The worker launcher maps **extraction**, **analysis**, **embedding**, **intelligence**, and **maintenance** to their own modules and queues; extraction and analysis also consume priority queues. Celery uses late acknowledgments, worker-loss rejection, prefetch one, task limits, and bounded child recycling. These controls require tasks to tolerate redelivery.

## Reliability and engineering challenges

- **Broker and database consistency:** PostgreSQL task executions and a dispatch outbox make pending work recoverable after publish failures. Workers claim executions under row locks and stable identities; maintenance reconciles stale dispatch.
- **Processing-state recovery:** the processing run tracks progress, pauses, and resume blockers; repair and retry paths reconcile incomplete books and chapters.
- **Worker memory:** role-specific task registration and a minimal exact-worker health ping reduce unnecessary imports. [The local memory audit](ops/production-memory-audit.md) reports exploratory Docker measurements and explicitly leaves VPS before/after gains unverified.
- **Observability:** request IDs pass into Celery headers; the API and workers configure Sentry with event scrubbing. Docker health checks probe API readiness and exact worker responsiveness.

## Testing and verification

The repository includes backend unit and integration tests, a synthetic story-intelligence evaluation corpus, frontend Vitest tests, Playwright E2E smoke tests, migration checks, security scans, and image checks in GitHub Actions. The portfolio video was checked for 4:35 duration, 1920×1080/30 fps H.264, AAC audio, and representative frame readability. This documentation and media change does not alter application behavior; it is not a fresh full CI run.

Backend tests should run in Docker Compose Local so the pinned application, PostgreSQL/pgvector, and Redis match the project setup:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests -v
```

Frontend checks:

```powershell
cd frontend
npm.cmd test
npm.cmd run test:e2e
```

The Playwright smoke suite starts a local Next dev server and mocks API responses. See [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml) for the full PR gate.

## Deployment architecture

The tracked production model serves Next.js from Vercel. Cloudflare fronts the API, which reaches Nginx and a Gunicorn-managed FastAPI container on a Hetzner VPS. Compose runs Redis with AOF, five Celery worker roles, and Beat; the database and S3-compatible storage are external dependencies. Supabase supports OAuth identity, and Sentry is wired into backend and worker error reporting. Release operations and migration safeguards live in [deploy.sh](deploy.sh), [VPS service notes](docs/hetzner-service-management.md), and [firewall/monitoring notes](ops/production-firewall-and-monitoring.md). The repository does not prove current external platform settings or ongoing service availability.

## Project status

LoreVia is presented here as an engineering portfolio project. The hosted application is planned for discontinuation; the repository, diagrams, synthetic screenshots, and reproducible presentation remain the durable showcase. The GitHub repository visibility and a public video destination could not be verified from this workspace, so no public availability is promised.

## Running locally

The backend and workers run with Docker Compose Local; the frontend runs separately with Node. Create `backend/.env.local` with local-only values and `frontend/.env.local` with the local API URL. Do not use production credentials or point local commands at a remote database.

The backend settings require a disposable local PostgreSQL URL, Redis broker credentials, local file storage, a JWT secret, and provider keys for any AI features you exercise. For local file storage, the repository uses `S3_ENDPOINT_URL=file:///app/storage` and a shared Docker volume. See [backend/app/core/config.py](backend/app/core/config.py) for the complete settings contract; Paddle checkout also needs its API key, webhook secret, and plan price IDs together.

<details>
<summary>Example local environment values</summary>

Create `backend/.env.local` with local dummy values and your own development-only AI key if you plan to run model-backed features:

```env
APP_NAME=LoreVia
DEBUG=true
API_V1_PREFIX=/api/v1
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lorevia
REDIS_PASSWORD=replace_local_redis_password
EDGE_PROXY_SECRET=replace_with_64_character_random_edge_secret
OPENAI_API_KEY=your_development_key_here
OPENAI_EXTRACT_MODEL=gpt-4o-mini
OPENAI_INTEL_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
S3_BUCKET=local-dev
S3_ENDPOINT_URL=file:///app/storage
AWS_ACCESS_KEY_ID=local-dev
AWS_SECRET_ACCESS_KEY=local-dev
JWT_SECRET=replace_with_a_long_random_secret
PADDLE_API_KEY=pdl_sandbox_key_here
PADDLE_WEBHOOK_SECRET=pdl_sandbox_webhook_secret_here
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

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=test_your_paddle_client_side_token_here
```

Keep both files out of version control. Compose Local supplies its own Redis broker URL and uses the disposable `lorevia_test` database for tests. Paddle checkout requires a valid matching sandbox configuration; placeholder IDs only illustrate the setting names.

</details>

```powershell
docker compose -f docker-compose-local.yml up --build -d
cd frontend
npm.cmd ci
npm.cmd run dev
```

The local API is at `http://localhost:8000`, API docs at `http://localhost:8000/docs`, Flower at `http://localhost:5555`, and the frontend at `http://localhost:3000`. Compose Local includes an explicit disposable migration/bootstrap service; it does not start the frontend or Beat. Stop the stack with `docker compose -f docker-compose-local.yml down` from the repository root. Avoid `down -v` unless you intend to discard local database and storage volumes.

## Repository structure

```text
backend/                 FastAPI, services, workers, migrations, and tests
frontend/                Next.js application and Playwright tests
ops/                     Nginx, Redis image, and VPS operations
docs/                    Architecture and operational decisions
portfolio-showcase/      Diagrams, screenshots, script, subtitles, previews, and local MP4
```

## License & Usage

This project is **not open source**. The code is provided for portfolio and showcase purposes only. Forking, cloning, or redistributing this repository (or its code) is not permitted and would violate the license. See the [LICENSE](./LICENSE) file for details.

Showcase repository: [Lorevia-showcase](https://github.com/madhavkant29/Lorevia-showcase)

