# Walkthrough claim map

This map records the source used for each architecture claim. It is a source audit, not a claim that a production deployment is currently running.

| Topic | Repository evidence | Used in |
| --- | --- | --- |
| Next.js App Router, React, client libraries | `frontend/package.json`, `frontend/src/app/`, `frontend/src/lib/api/client.ts`, `frontend/next.config.js` | Overview, frontend/API |
| Authentication and CSRF | `backend/app/api/v1/routes/auth.py`, `frontend/src/lib/api/auth.ts`, `backend/app/utils/auth_csrf.py` | Frontend/API |
| Request validation, upload limits, duplicate check | `backend/app/api/v1/routes/books/imports.py`, `backend/app/services/book_upload_service.py` | Upload |
| Book, processing run, task execution, and post-commit dispatch | `backend/app/services/book_upload_service.py`, `backend/app/models/operations.py`, `backend/app/services/task_execution_service.py` | Upload/recovery |
| Async SQLAlchemy and schema history | `backend/app/core/database.py`, `backend/app/db/migrations/` | API/data |
| Five worker roles and queue registration | `backend/app/workers/worker_launcher.py`, `backend/app/workers/queues/queues.py`, `docker-compose.yml` | Worker topology |
| Celery broker, acknowledgments, limits, Beat | `backend/app/workers/celery_app.py` | Worker topology/reliability |
| Parsing, chapter dispatch, analysis | `backend/app/services/extraction_book_processing_service.py`, `backend/app/services/extraction_chapter_analysis_dispatch_service.py`, `backend/app/workers/tasks/` | Ingestion/AI |
| Character evidence and identity | `backend/app/engine/character/extractor.py`, `backend/app/engine/character/deduplicator.py`, `backend/app/models/character.py` | AI |
| Embeddings, pgvector, hybrid retrieval, chapter gate | `backend/app/engine/embeddings/embedder.py`, `backend/app/engine/search/semantic.py`, `backend/app/models/intelligence.py`, `backend/app/db/migrations/versions/20260620_replace_vector_indexes_hnsw.py` | Retrieval |
| Cited answers and advisor context | `backend/app/schemas/intelligence.py`, `backend/app/utils/advisor_chat_utils.py` | Retrieval |
| Outbox reconciliation, locked claims, retry status | `backend/app/services/task_execution_service.py`, `backend/app/services/pipeline_state_service.py`, `backend/app/workers/tasks/maintenance_tasks.py` | Recovery |
| Minimal exact-worker health probe | `backend/app/workers/healthcheck.py`, `ops/production-memory-audit.md` | Reliability |
| Sentry and request context | `backend/app/main.py`, `backend/app/workers/celery_app.py` | Operations |
| Vercel → Cloudflare → Hetzner/Nginx/API deployment model | `frontend/next.config.js`, `docker-compose.yml`, `ops/production-firewall-and-monitoring.md`, `docs/ARCHITECTURE.md` | Deployment |
| Supabase OAuth, S3-compatible storage | `backend/app/api/v1/routes/auth.py`, `backend/app/core/storage.py`, `backend/app/core/config.py` | Deployment |
| Test and image gates | `.github/workflows/ci-cd.yml`, `.github/workflows/database-migrations.yml` | Verification |

## Deliberate limits

- No production throughput, user-count, or latency claim is made.
- The memory audit's measurements are local and exploratory; no VPS before/after gain is claimed.
- The deployment diagram represents tracked configuration and documentation, not a live topology probe.
- The codebase uses five worker roles and async `psycopg`. An older sentence in `docs/ARCHITECTURE.md` says four roles and mentions `asyncpg`; the source takes precedence here.
- GitHub repository visibility and Release hosting could not be checked from this workspace.
