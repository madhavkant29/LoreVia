import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import allowed_hosts, cors_origins, settings
from app.core.database import engine
from app.core.events import on_shutdown, on_startup
from app.core.redis import get_redis

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )

from app.utils.logging.logger import get_logger

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

        request_id = scope.get("headers", {}).get(b"x-request-id") or str(uuid.uuid4())
        from app.utils.request_context import set_request_id
        set_request_id(request_id)
        started_at = time.perf_counter()

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"x-request-id"] = request_id.encode()
                headers[b"x-frame-options"] = b"DENY"
                headers[b"x-content-type-options"] = b"nosniff"
                headers[b"referrer-policy"] = b"strict-origin-when-cross-origin"
                headers[b"permissions-policy"] = b"camera=(), microphone=(), geolocation=()"
                headers[b"content-security-policy"] = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                if not settings.DEBUG:
                    headers[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains; preload"
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
        return Response(status_code=503, content="not ready")
    return {"status": "ready"}
