"""Phase 3 intelligence tasks."""
import asyncio
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="intelligence_tasks.generate_wiki",
                 queue="intelligence", max_retries=2)
def generate_wiki_task(self, book_id: str):
    """Generate auto-wiki for all chapters of a book. Phase 3."""
    # Placeholder — implemented in Phase 3
    pass
