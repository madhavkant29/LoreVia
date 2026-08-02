# LoreVia Backend

FastAPI + Celery + PostgreSQL/pgvector + Redis

## Setup

```bash
cp .env.example .env       # fill in values
pip install -r requirements.txt
alembic upgrade head      # run migrations to the current repo head

# API
uvicorn app.main:app --reload

# Workers (in separate terminals)
# Default multi-worker layout
celery -A app.workers.celery_app worker -Q intelligence -c 1 --loglevel=info
celery -A app.workers.celery_app worker -Q analysis,analysis_priority,embedding -c 2 --loglevel=info
celery -A app.workers.celery_app worker -Q extraction,extraction_priority -c 4 --loglevel=info

# Cost-saving fallback
celery -A app.workers.celery_app worker -Q intelligence,analysis,analysis_priority,embedding,extraction,extraction_priority -c 4 -Ofair --loglevel=info

# Monitor
celery -A app.workers.celery_app flower --port=5555
```

## Production web server

Production containers start the API with Gunicorn using Uvicorn workers via `start.sh`.
Use plain `uvicorn app.main:app --reload` only for direct local development outside Docker.

## Testing

```bash
docker compose -f ../docker-compose-local.yml exec -T api pytest tests -v
```

Preferred local test commands for this repo:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests -v
```

Read-only local preflight before backend verification:

```powershell
docker compose -f docker-compose-local.yml exec -T api python scripts/preflight_local.py
```

Disposable local migration gate:

```powershell
docker compose -f docker-compose-local.yml exec -T api python scripts/verify_migrations_temp_db.py
```

By default this verifies the current head can upgrade, downgrade to its immediate
parent, and upgrade again. Use `--downgrade-target base` only when intentionally
checking the full historical downgrade path.

Notes:

- Prefer Docker Compose Local so tests run against the repo's pinned app image, Postgres, Redis, and extensions.
- Some backend tests are DB-backed and require a safe local test database plus required extensions such as `pgvector`.
- Local Docker Compose now reserves `lorevia` for the running app and `lorevia_test` for pytest via `TEST_DATABASE_URL`.
- Backend tests are intended to pass in non-production environments; do not point them at production infrastructure.
- Use `scripts/schema_drift_audit.sql` against dev or prod when you need a quick schema/head consistency check.

## Key endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/v1/auth/register | Register |
| POST | /api/v1/books/upload | Upload PDF/EPUB |
| GET | /api/v1/reader/{id}/context?q=X&chapter=N | Smart tap |
| GET | /api/v1/reader/{id}/summary/{n}?mode=short | Chapter summary |
| GET | /api/v1/reader/{id}/relationships?chapter=N | Relationship graph |
| GET | /api/v1/reader/{id}/search?q=X&chapter=N | Semantic search |
| GET | /api/v1/reader/{id}/recall | Memory recall |


## Targeted backend auth/security verification

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests\unit\test_auth_deps.py tests\unit\test_core_security.py tests\unit\test_security_utils.py tests\integration\test_security_headers.py -v
```

## Retrieval tuning workflow

Use the non-production retrieval tools from the repo root:

```powershell
docker compose -f docker-compose-local.yml exec -T api python scripts/evaluate_retrieval.py --cases scripts/retrieval_eval_cases.sample.json
docker compose -f docker-compose-local.yml exec -T api python scripts/rebuild_book_chunks.py --book-id <book-uuid>
docker compose -f docker-compose-local.yml exec -T api python scripts/rebuild_book_chunks.py --book-id <book-uuid> --apply --confirm-apply REBUILD_BOOK_CHUNKS
```

Recommended comparison order:

1. Run the eval harness on the baseline case file.
2. Rebuild chunks for the target manuscript with the current chunking settings.
3. Run the eval harness again and compare `Recall@5`, `MRR@5`, and average retrieved context count.
