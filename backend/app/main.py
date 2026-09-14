import asyncio
import re
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import cast

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import allowed_hosts, cors_middleware_options, settings
from app.core.events import on_shutdown, on_startup
from app.utils.exception_boundaries import HTTP_LAST_RESORT_EXCEPTIONS
from app.utils.logging.errors import (
    public_error_message,
    redact_sensitive_text,
    request_log_context,
    sanitize_validation_errors,
    scrub_sentry_event,
)
from app.utils.observability_metrics import begin_operation_metrics, finish_operation_metrics
from app.utils.release_utils import normalize_release_sha
from app.utils.security_utils import apply_security_headers
from app.utils.tunnel.cloudflare import CloudflareTunnelMiddleware

if settings.SENTRY_DSN and not settings.DEBUG:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            CeleryIntegration(),
        ],
        before_send=scrub_sentry_event,
        traces_sample_rate=settings.SENTRY_API_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_API_PROFILES_SAMPLE_RATE,
    )
from app.utils.logging.logger import configure_logging, get_logger

configure_logging()
log = get_logger("lorevia.http")


_CORS_OPTIONS = cors_middleware_options()
_CORS_ALLOW_ORIGINS = {str(origin) for origin in _CORS_OPTIONS.get("allow_origins", [])}
_CORS_ALLOW_CREDENTIALS = bool(_CORS_OPTIONS.get("allow_credentials"))
_PRIVATE_API_CACHE_CONTROL = b"private, no-store, no-cache, max-age=0, must-revalidate"
_CORS_ALLOW_ORIGIN_REGEX = (
    re.compile(str(pattern))
    if isinstance((pattern := _CORS_OPTIONS.get("allow_origin_regex")), str) and pattern
    else None
)
_OBSERVED_READ_PATH_MARKERS = (
    "/notifications",
    "/books",
    "/public",
    "/search",
    "/world-building",
    "/conversations",
    "/messages",
    "/stats",
    "/analytics",
    "/jobs",
)


def _is_observed_read_path(path: str) -> bool:
    return any(marker in path for marker in _OBSERVED_READ_PATH_MARKERS)


def _cors_failure_headers(origin: str | None) -> list[tuple[bytes, bytes]]:
    if not origin:
        return []
    if origin in _CORS_ALLOW_ORIGINS or (
        _CORS_ALLOW_ORIGIN_REGEX and _CORS_ALLOW_ORIGIN_REGEX.match(origin)
    ):
        headers: list[tuple[bytes, bytes]] = [
            (b"access-control-allow-origin", origin.encode()),
            (b"vary", b"Origin"),
        ]
        if _CORS_ALLOW_CREDENTIALS:
            headers.append((b"access-control-allow-credentials", b"true"))
        return headers
    return []


def _install_exception_handlers(target_app: FastAPI) -> None:
    @target_app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        log.warning(
            "http_exception",
            extra=request_log_context(
                request,
                status_code=exc.status_code,
                detail=exc.detail,
            ),
        )
        detail = public_error_message(exc.status_code)
        if (
            400 <= exc.status_code < 500
            and exc.status_code != 404
            and isinstance(exc.detail, str)
            and exc.detail
        ):
            detail = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
        )

    @target_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        raw_errors = cast(list[dict[str, object]], list(exc.errors()))
        log.warning(
            "request_validation_failed",
            extra=request_log_context(
                request,
                status_code=422,
                errors=sanitize_validation_errors(raw_errors),
            ),
        )
        detail = public_error_message(422)
        return JSONResponse(status_code=422, content={"detail": detail})

    @target_app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log.exception(
            "unhandled_exception",
            extra=request_log_context(request, status_code=500),
        )
        return JSONResponse(status_code=500, content={"detail": public_error_message(500)})


def _build_api_app() -> FastAPI:
    from app.api.v1.router import api_router

    api_app = FastAPI(
        title="LoreVia API",
        version="2.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url=None,
    )
    _install_exception_handlers(api_app)
    api_app.include_router(api_router)
    return api_app


class _LazyMountedApp:
    def __init__(self, factory: Callable[[], FastAPI]):
        self._factory = factory
        self._app: FastAPI | None = None
        self._lock = asyncio.Lock()

    async def ensure_app(self) -> FastAPI:
        if self._app is None:
            async with self._lock:
                if self._app is None:
                    self._app = self._factory()
        return self._app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        app = await self.ensure_app()
        await app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


app = FastAPI(
    title="LoreVia",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)
_install_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    **cors_middleware_options(),
)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts(),
    )

if settings.CLOUDFLARE_TUNNEL_TOKEN:
    app.add_middleware(CloudflareTunnelMiddleware)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware to avoid BaseHTTPMiddleware event loop issues."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ASGI headers are a list of [name, value] tuples, not a dict
        headers_list = scope.get("headers", [])
        request_id = None
        for name, value in headers_list:
            if name == b"x-request-id":
                request_id = value.decode()
                break
        request_origin = None
        for name, value in headers_list:
            if name == b"origin":
                request_origin = value.decode()
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        from app.utils.request_context import set_request_id, set_request_user_id

        set_request_id(request_id)
        set_request_user_id(None)
        started_at = time.perf_counter()
        metrics_token = begin_operation_metrics()
        response_started = False
        response_status = 500
        response_size_bytes = 0

        async def send_with_headers(message):
            nonlocal response_size_bytes, response_started, response_status
            if message["type"] == "http.response.start":
                response_started = True
                response_status = int(message.get("status") or 500)
                raw_headers: list[tuple[bytes, bytes]] = message.get("headers", [])
                is_api_response = (
                    str(scope.get("path") or "").startswith(f"{settings.API_V1_PREFIX}/")
                    or str(scope.get("path") or "") == settings.API_V1_PREFIX
                )
                has_cache_control = any(
                    name.lower() == b"cache-control" for name, _value in raw_headers
                )
                security_overrides = apply_security_headers(
                    {},
                    request_id=request_id,
                    include_hsts=not settings.DEBUG,
                )
                applied: set[bytes] = set()
                preserved: list[tuple[bytes, bytes]] = []
                set_cookie_name = b"set-cookie"
                for name, value in raw_headers:
                    lower = name.lower()
                    if lower == set_cookie_name:
                        preserved.append((name, value))
                        continue
                    if lower in security_overrides:
                        if lower not in applied:
                            preserved.append((lower, security_overrides[lower]))
                            applied.add(lower)
                        continue
                    preserved.append((name, value))
                for sec_name, sec_value in security_overrides.items():
                    if sec_name not in applied:
                        preserved.append((sec_name, sec_value))
                if is_api_response and not has_cache_control:
                    preserved.append((b"cache-control", _PRIVATE_API_CACHE_CONTROL))
                message["headers"] = preserved
            elif message["type"] == "http.response.body":
                response_size_bytes += len(message.get("body") or b"")
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except HTTP_LAST_RESORT_EXCEPTIONS:
            log.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": redact_sensitive_text(str(scope.get("path") or "")),
                },
            )
            # If response hasn't started, send a 500 error response
            if not response_started:
                failure_headers: list[list[bytes]] = [
                    [b"content-type", b"text/plain"],
                    [b"x-request-id", request_id.encode()],
                ]
                for header_name, header_value in _cors_failure_headers(request_origin):
                    failure_headers.append([header_name, header_value])
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": failure_headers,
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"Internal Server Error",
                    }
                )
            else:
                raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        path = str(scope.get("path") or "")
        operation_metrics = finish_operation_metrics(metrics_token)
        if (
            settings.DEBUG
            or duration_ms >= settings.SLOW_REQUEST_LOG_MS
            or _is_observed_read_path(path)
        ):
            log.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": redact_sensitive_text(path),
                    "status_code": response_status,
                    "duration_ms": duration_ms,
                    "response_size_bytes": response_size_bytes,
                    **operation_metrics,
                },
            )
        set_request_id(None)
        set_request_user_id(None)


app.add_middleware(SecurityHeadersMiddleware)
_lazy_api_app = _LazyMountedApp(_build_api_app)
app.mount(settings.API_V1_PREFIX, _lazy_api_app)


def _openapi_schema() -> dict:
    if _lazy_api_app._app is None:
        _lazy_api_app._app = _lazy_api_app._factory()
    return _lazy_api_app._app.openapi()


app.openapi = _openapi_schema  # type: ignore[method-assign]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "LoreVia",
        "version": "2.0.0",
        "release_sha": normalize_release_sha(settings.RELEASE_SHA),
    }


@app.get("/ready")
async def ready():
    from app.core.database import engine
    from app.core.redis import get_redis
    from app.utils.schema_utils import assert_core_runtime_schema_compatible

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await assert_core_runtime_schema_compatible(conn)
            await conn.execute(text("SELECT '[0,0,0]'::vector"))
        r = await get_redis()
        await r.ping()
    except HTTP_LAST_RESORT_EXCEPTIONS:
        log.warning("readiness_check_failed", exc_info=True)
        return Response(status_code=503, content="not ready")
    return {"status": "ready"}
