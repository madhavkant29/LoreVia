import ssl
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sentry_sdk
from celery import Celery, Task, signals
from celery.schedules import crontab
from sentry_sdk.integrations.celery import CeleryIntegration

from app.core.config import settings
from app.core.database import engine
from app.core.redis import close_all_redis_clients
from app.utils.request_context import get_request_id, set_request_id, set_request_user_id
from app.utils.worker_async_utils import close_worker_loop, get_worker_loop, has_worker_loop
from app.workers.queues.queues import TASK_QUEUES


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


def _coerce_optional_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None
    cleaned = raw_url.strip()
    return cleaned or None


def _resolve_celery_redis_settings() -> tuple[str, dict, str | None, dict]:
    broker_source = _coerce_optional_url(settings.CELERY_BROKER_URL) or settings.REDIS_URL
    broker_url, broker_ssl_options = _normalize_celery_redis_url(broker_source)

    configured_backend = _coerce_optional_url(settings.CELERY_RESULT_BACKEND)
    backend_source = broker_source if settings.CELERY_RESULT_BACKEND is None else configured_backend
    if backend_source is None:
        return broker_url, broker_ssl_options, None, {}

    backend_url, backend_ssl_options = _normalize_celery_redis_url(backend_source)
    return broker_url, broker_ssl_options, backend_url, backend_ssl_options


redis_url, redis_ssl_options, result_backend_url, result_backend_ssl_options = _resolve_celery_redis_settings()


if settings.SENTRY_DSN and not settings.DEBUG:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )


class RequestContextTask(Task):
    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None, link=None, link_error=None, **options):
        headers = dict(options.get("headers") or {})
        if "request_id" not in headers:
            request_id = get_request_id()
            if request_id:
                headers["request_id"] = request_id
        headers.setdefault("enqueued_at", str(time.time()))
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
    backend=result_backend_url,
    task_cls=RequestContextTask,
    include=[
        "app.workers.tasks.extraction_tasks",
        "app.workers.tasks.analysis_tasks",
        "app.workers.tasks.embedding_tasks",
        "app.workers.tasks.intelligence_tasks",
        "app.workers.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_queues=TASK_QUEUES,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=settings.CELERY_TASK_IGNORE_RESULT,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": settings.CELERY_BROKER_VISIBILITY_TIMEOUT_SECONDS,
    },
    task_routes={
        "extraction_tasks.*": {"queue": "extraction"},
        "analysis_tasks.*":   {"queue": "analysis"},
        "embedding_tasks.*":  {"queue": "embedding"},
        "intelligence_tasks.*": {"queue": "intelligence"},
        "maintenance_tasks.*": {"queue": "intelligence"},
    },
    task_annotations={
        # Queue-specific guardrails:
        # - extraction is heavy/long-running; use generous timeouts
        # - intelligence is user-facing; keep tighter limits
        "extraction_tasks.process_book": {
            "soft_time_limit": 20 * 60,
            "time_limit": 25 * 60,
        },
        "extraction_tasks.process_chapter": {
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
        "maintenance_tasks.*": {
            "soft_time_limit": 5 * 60,
            "time_limit": 10 * 60,
        },
    },
    result_expires=settings.CELERY_RESULT_EXPIRES_SECONDS if result_backend_url else None,
    beat_schedule={
        "maintenance-send-due-trial-emails-hourly": {
            "task": "maintenance_tasks.send_due_trial_emails",
            "schedule": crontab(minute=0),
            "kwargs": {"limit": 100},
        },
        "maintenance-process-beta-reads-every-15-minutes": {
            "task": "maintenance_tasks.process_beta_reads",
            "schedule": crontab(minute="*/15"),
            "kwargs": {"limit": 100},
        },
    },
    task_default_retry_delay=30,
    task_max_retries=3,
)

if redis_ssl_options:
    celery_app.conf.broker_use_ssl = redis_ssl_options
if result_backend_ssl_options:
    celery_app.conf.redis_backend_use_ssl = result_backend_ssl_options


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
        set_request_user_id(None)
    except Exception:
        return


@signals.worker_process_init.connect
def _worker_process_init(**kwargs):
    try:
        get_worker_loop()
    except Exception:
        return


@signals.worker_process_shutdown.connect
def _worker_process_shutdown(**kwargs):
    if not has_worker_loop():
        return
    try:
        loop = get_worker_loop()
        loop.run_until_complete(_shutdown_worker_async_resources())
    except Exception:
        return
    finally:
        close_worker_loop()


async def _shutdown_worker_async_resources() -> None:
    await close_all_redis_clients()
    await engine.dispose()
