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
celery -A app.workers.celery_app worker -Q analysis,embedding -c 2 --loglevel=info
celery -A app.workers.celery_app worker -Q extraction -c 4 --loglevel=info

# Cost-saving fallback
celery -A app.workers.celery_app worker -Q intelligence,analysis,embedding,extraction -c 4 -Ofair --loglevel=info

# Monitor
celery -A app.workers.celery_app flower --port=5555
```

## Cloudflare Tunnel (production origin security)

1. Go to Cloudflare Zero Trust → Tunnels → Create tunnel
2. Copy the tunnel token → set `CLOUDFLARE_TUNNEL_TOKEN` in .env
3. Deploy — `start.sh` starts cloudflared automatically alongside uvicorn

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

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


## to run backend tests -->
```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v  

 ```
