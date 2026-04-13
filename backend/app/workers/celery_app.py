import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from celery import Celery
from app.core.config import settings


def _normalize_celery_redis_url(raw_url: str) -> tuple[str, dict]:
    if not raw_url.startswith("rediss://"):
        return raw_url, {}

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    cert_reqs = (query.pop("ssl_cert_reqs", "required") or "required").lower()
    normalized_url = urlunsplit(parts._replace(query=urlencode(query)))

    ssl_options = {
        "required": ssl.CERT_REQUIRED,
        "optional": ssl.CERT_OPTIONAL,
        "none": ssl.CERT_NONE,
        "cert_required": ssl.CERT_REQUIRED,
        "cert_optional": ssl.CERT_OPTIONAL,
        "cert_none": ssl.CERT_NONE,
    }
    return normalized_url, {"ssl_cert_reqs": ssl_options.get(cert_reqs, ssl.CERT_REQUIRED)}


redis_url, redis_ssl_options = _normalize_celery_redis_url(settings.REDIS_URL)

celery_app = Celery(
    "lorevia",
    broker=redis_url,
    backend=redis_url,
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

if redis_ssl_options:
    celery_app.conf.broker_use_ssl = redis_ssl_options
    celery_app.conf.redis_backend_use_ssl = redis_ssl_options
