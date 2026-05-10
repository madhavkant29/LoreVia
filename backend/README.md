# LoreVia Backend

FastAPI + Celery + PostgreSQL/pgvector + Redis

## Setup

```bash
cp .env.example .env       # fill in values
pip install -r requirements.txt
alembic upgrade heads     # run migrations for all active branches

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

## Cloudflare Tunnel (production origin security)

1. Go to Cloudflare Zero Trust → Tunnels → Create tunnel
2. Copy the tunnel token → set `CLOUDFLARE_TUNNEL_TOKEN` in .env
3. Deploy — `start.sh` starts cloudflared automatically alongside uvicorn

## Testing

```bash
docker compose -f ../docker-compose-local.yml exec -T api pytest tests -v
```

Preferred local test commands for this repo:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests -v
```

Notes:

- Prefer Docker Compose Local so tests run against the repo's pinned app image, Postgres, Redis, and extensions.
- Some backend tests are DB-backed and require a safe local test database plus required extensions such as `pgvector`.
- Backend tests are intended to pass in non-production environments; do not point them at production infrastructure.

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
| POST | /api/v1/intelligence/{id}/chat/{char_id} | Character chat |


## Targeted backend auth/security verification

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests\unit\test_auth_deps.py tests\unit\test_core_security.py tests\unit\test_security_utils.py tests\integration\test_security_headers.py -v
```
