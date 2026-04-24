import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sentry_sdk
from celery import Celery, signals
from sentry_sdk.integrations.celery import CeleryIntegration

from app.core.config import settings
from app.utils.request_context import get_request_id, set_request_id


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


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )


class RequestContextTask(Celery.Task):
    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None, link=None, link_error=None, **options):
        headers = dict(options.get("headers") or {})
        if "request_id" not in headers:
            request_id = get_request_id()
            if request_id:
                headers["request_id"] = request_id
        options["headers"] = headers
        return super().apply_async(
            args=args,
            kwargs=kwargs,
            task_id=task_id,
            producer=producer,
            link=link,
            link_error=link_error,
            **options,
        )


celery_app = Celery(
    "lorevia",
    broker=redis_url,
    backend=redis_url,
    task_cls=RequestContextTask,
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
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
    task_routes={
        "extraction_tasks.*": {"queue": "extraction"},
        "analysis_tasks.*":   {"queue": "analysis"},
        "embedding_tasks.*":  {"queue": "embedding"},
        "intelligence_tasks.*": {"queue": "intelligence"},
    },
    task_annotations={
        # Single-worker MVP guardrails:
        # - extraction is heavy/long-running → rate limit + generous timeouts
        # - intelligence is user-facing → tight timeouts + higher rate
        "extraction_tasks.*": {
            "rate_limit": "2/m",
            "soft_time_limit": 20 * 60,
            "time_limit": 25 * 60,
        },
        "analysis_tasks.*": {
            "soft_time_limit": 10 * 60,
            "time_limit": 15 * 60,
        },
        "embedding_tasks.*": {
            "rate_limit": "30/m",
            "soft_time_limit": 5 * 60,
            "time_limit": 10 * 60,
        },
        "intelligence_tasks.*": {
            "rate_limit": "60/m",
            "soft_time_limit": 60,
            "time_limit": 120,
        },
    },
    task_default_retry_delay=30,
    task_max_retries=3,
)

if redis_ssl_options:
    celery_app.conf.broker_use_ssl = redis_ssl_options
    celery_app.conf.redis_backend_use_ssl = redis_ssl_options


@signals.before_task_publish.connect
def _task_prerun_set_request_id(sender=None, headers=None, body=None, **kwargs):
    try:
        request_id = (headers or {}).get("request_id")
        set_request_id(request_id)
        if request_id and settings.SENTRY_DSN:
            sentry_sdk.set_tag("request_id", request_id)
    except Exception:
        # never block task execution on observability
        return


@signals.after_task_publish.connect
def _task_postrun_clear_request_id(sender=None, headers=None, body=None, **kwargs):
    try:
        set_request_id(None)
    except Exception:
        return
