from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "lorevia",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks.extraction_tasks",
        "app.workers.tasks.analysis_tasks",
        "app.workers.tasks.embedding_tasks",
        "app.workers.tasks.intelligence_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "extraction_tasks.*": {"queue": "extraction"},
        "analysis_tasks.*":   {"queue": "analysis"},
        "embedding_tasks.*":  {"queue": "embedding"},
        "intelligence_tasks.*": {"queue": "intelligence"},
    },
    task_default_retry_delay=30,
    task_max_retries=3,
)
