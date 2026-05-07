import time
import uuid
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

from app.api.v1.router import api_router
from app.core.config import allowed_hosts, cors_origins, settings
from app.core.database import engine
from app.core.events import on_shutdown, on_startup
from app.core.redis import get_redis
from app.utils.security_utils import apply_security_headers

if settings.SENTRY_DSN and not settings.DEBUG:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )

from app.utils.logging.errors import public_error_message, request_log_context, sanitize_validation_errors
from app.utils.logging.logger import configure_logging, get_logger

configure_logging()
log = get_logger("lorevia.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


app = FastAPI(
    title="LoreVia API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts(),
)


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
        
        from app.utils.request_context import set_request_id
        set_request_id(request_id)
        started_at = time.perf_counter()
        response_started = False

        async def send_with_headers(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = dict(message.get("headers", []))
                headers = apply_security_headers(
                    headers,
                    request_id=request_id,
                    include_hsts=not settings.DEBUG,
                )
                message["headers"] = list(headers.items())
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

app.add_middleware(SecurityHeadersMiddleware)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    log.warning(
        "http_exception",
        extra=request_log_context(
            request,
            status_code=exc.status_code,
            detail=exc.detail,
        ),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": public_error_message(exc.status_code)},
    )


@app.exception_handler(RequestValidationError)
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception(
        "unhandled_exception",
        extra=request_log_context(request, status_code=500),
    )
    return JSONResponse(status_code=500, content={"detail": public_error_message(500)})


@app.get("/health")
async def health():
    return {"status": "ok", "app": "LoreVia", "version": "2.0.0"}


@app.get("/ready")
async def ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        r = await get_redis()
        await r.ping()
    except Exception:
        log.exception("readiness_check_failed")
        return Response(status_code=503, content="not ready")
    return {"status": "ready"}
