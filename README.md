# LoreVia

AI-powered reading companion for novels.

**Backend:** FastAPI + Celery + PostgreSQL/pgvector + Redis  
**Frontend:** Next.js 15

## Quick start

```bash
# Backend
cd backend && cp .env.example .env  # fill in values
pip install -r requirements.txt
uvicorn app.main:app --reload

# Workers
celery -A app.workers.celery_app worker -Q extraction,analysis,embedding -c 2

# Frontend
cd frontend && npm install && npm run dev
```
