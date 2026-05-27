import asyncio
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import cast

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import allowed_hosts, cors_middleware_options, settings
from app.core.events import on_shutdown, on_startup
from app.utils.logging.errors import public_error_message, request_log_context, scrub_sentry_event, sanitize_validation_errors
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
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )
from app.utils.logging.logger import configure_logging, get_logger

configure_logging()
log = get_logger("lorevia.http")


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
        if 400 <= exc.status_code < 500 and exc.status_code != 404 and isinstance(exc.detail, str) and exc.detail:
            detail = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
        )

    @target_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        log.warning(
            "request_validation_failed",
            extra=request_log_context(
                request,
                status_code=422,
                errors=sanitize_validation_errors(cast(list[dict[str, object]], list(exc.errors()))),
            ),
        )
        return JSONResponse(status_code=422, content={"detail": public_error_message(422)})

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
        if not request_id:
            request_id = str(uuid.uuid4())
        
        from app.utils.request_context import set_request_id, set_request_user_id
        set_request_id(request_id)
        set_request_user_id(None)
        started_at = time.perf_counter()
        response_started = False

        async def send_with_headers(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                raw_headers: list[tuple[bytes, bytes]] = message.get("headers", [])
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
                message["headers"] = preserved
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            log.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                },
            )
            # If response hasn't started, send a 500 error response
            if not response_started:
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        [b"content-type", b"text/plain"],
                        [b"x-request-id", request_id.encode()],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Internal Server Error",
                })
            else:
                raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if settings.DEBUG or duration_ms >= 1200:
            log.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "duration_ms": duration_ms,
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
    return {"status": "ok", "app": "LoreVia", "version": "2.0.0"}


@app.get("/ready")
async def ready():
    from app.core.database import engine
    from app.core.redis import get_redis

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        r = await get_redis()
        await r.ping()
    except Exception:
        log.exception("readiness_check_failed")
        return Response(status_code=503, content="not ready")
    return {"status": "ready"}
