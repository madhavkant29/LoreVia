import os
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ORIGINAL_ENV_KEYS = frozenset(os.environ.keys())


def _load_env_file(path: str | Path = ".env", *, override_loaded_values: bool = False) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in _ORIGINAL_ENV_KEYS:
            continue
        if not override_loaded_values and key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_BASE_DIR = Path(__file__).resolve().parents[2]
_load_env_file(_BASE_DIR / ".env")
_load_env_file(_BASE_DIR / ".env.local", override_loaded_values=True)
LOCALHOST_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
EDGE_PROXY_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
EDGE_PROXY_SECRET_PLACEHOLDERS = frozenset(
    {
        "replace_with_64_character_random_edge_secret",
        "replace_with_a_random_edge_proxy_secret",
    }
)


def cors_origins_for_value(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseSettings):
    APP_NAME: str = "LoreVia"
    RELEASE_SHA: str = "unknown"
    DEPLOYMENT_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = (
        "https://getlorevia.com,https://www.getlorevia.com,https://api.getlorevia.com"
    )
    ALLOWED_HOSTS: str = "getlorevia.com,www.getlorevia.com,api.getlorevia.com,localhost,127.0.0.1"
    SLOW_REQUEST_LOG_MS: int = 800

    # Additive rollout controls. These default on for the already-migrated
    # contracts; public object delivery remains opt-in until assets exist.
    CURSOR_PAGE_APIS_ENABLED: bool = True
    WORLD_ANALYSIS_SNAPSHOTS_ENABLED: bool = True
    INDEXED_SEARCH_ENABLED: bool = True
    READER_EVENTS_V2_ENABLED: bool = True
    DIRECT_PUBLIC_ASSETS_ENABLED: bool = False
    PUBLIC_ASSET_BASE_URL: str | None = None
    PUBLIC_ASSET_CACHE_MAX_AGE_SECONDS: int = Field(default=60, ge=0, le=3600)

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_POOL_TIMEOUT_SECONDS: int = 10
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(default=120_000, ge=1_000, le=3_600_000)
    DATABASE_IDLE_TRANSACTION_TIMEOUT_MS: int = Field(default=60_000, ge=1_000, le=3_600_000)
    DATABASE_SLOW_QUERY_LOG_MS: int = Field(default=1_000, ge=1, le=3_600_000)
    DATABASE_SQL_ECHO: bool = False

    # Redis
    REDIS_URL: str
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_IGNORE_RESULT: bool = False
    CELERY_RESULT_EXPIRES_SECONDS: int = 3600
    CELERY_BROKER_VISIBILITY_TIMEOUT_SECONDS: int = 7200
    REDIS_TTL_CHARACTER_PROFILE: int = 3600  # 1 hr
    REDIS_TTL_SUMMARY: int = 604800  # 7 days
    REDIS_TTL_GRAPH: int = 3600  # 1 hr
    REDIS_TTL_SEARCH: int = 3600  # 1 hr
    REDIS_TTL_RECALL: int = 86400  # 24 hrs
    REDIS_TTL_SESSION: int = 86400
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 1.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 1.0
    REDIS_CACHE_OPERATION_TIMEOUT_SECONDS: float = 0.5

    # Bound fan-out for request/worker storage reads.  Keeping this modest
    # prevents a large export or preview from consuming the shared executor.
    STORAGE_IO_CONCURRENCY: int = Field(default=4, ge=1, le=32)
    MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_CHAPTERS: int = Field(default=25, ge=1, le=10_000)
    MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_WORDS: int = Field(default=100_000, ge=1, le=100_000_000)
    MANUSCRIPT_EXPORT_ARTIFACT_TTL_SECONDS: int = Field(
        default=24 * 60 * 60, ge=300, le=30 * 24 * 60 * 60
    )
    MANUSCRIPT_EXPORT_SPOOL_MAX_MEMORY_BYTES: int = Field(
        default=8 * 1024 * 1024, ge=1024 * 1024, le=256 * 1024 * 1024
    )
    MANUSCRIPT_EXPORT_SPOOL_DIRECTORY: str | None = None
    # Storage (Cloudflare R2 — PDFs/EPUBs only)
    S3_BUCKET: str
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    # AI — two models, cost discipline
    OPENAI_API_KEY: str
    OPENAI_EXTRACT_MODEL: str = "gpt-4o-mini"  # extraction, summaries
    OPENAI_INTEL_MODEL: str = "gpt-4o-mini"  # chat, predictions #revert to gpt-4o-mini for now, gpt-4o is too costly and not significantly better for our use case
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBED_DIM: int = 1536
    OPENAI_ENCODING_MODEL: str = "gpt-4o-mini"  # tiktoken encoding for token counting
    ANTHROPIC_API_KEY: str | None = None  # Reserved; no Anthropic runtime integration exists.
    GEMINI_API_KEY: str | None = None
    GEMINI_EXTRACT_MODEL: str = "gemini-2.5-flash"
    GEMINI_INTEL_MODEL: str = "gemini-2.5-flash"
    GEMINI_REQUEST_TIMEOUT_SECONDS: int = Field(default=60, ge=5, le=300)

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 30
    AUTH_COOKIE_DOMAIN: str | None = None
    EDGE_PROXY_SECRET: str | None = None
    EDGE_PROXY_SECRET_FILE: str | None = None

    # Paddle
    PADDLE_API_KEY: str | None = None
    PADDLE_WEBHOOK_SECRET: str | None = None
    PADDLE_WEBHOOK_TOLERANCE_SECONDS: int = 300
    PADDLE_DEFAULT_CHECKOUT_URL: str | None = None
    PADDLE_AUTHOR_MONTHLY_PRICE_ID: str | None = None
    PADDLE_AUTHOR_ANNUAL_PRICE_ID: str | None = None
    PADDLE_ARCHITECT_MONTHLY_PRICE_ID: str | None = None
    PADDLE_ARCHITECT_ANNUAL_PRICE_ID: str | None = None
    # Legacy names kept so existing Pro/Power environments still resolve into
    # the current Author/Architect three-tier catalog.
    PADDLE_PRO_MONTHLY_PRICE_ID: str | None = None
    PADDLE_PRO_ANNUAL_PRICE_ID: str | None = None
    PADDLE_POWER_MONTHLY_PRICE_ID: str | None = None
    PADDLE_POWER_ANNUAL_PRICE_ID: str | None = None
    APP_URL: str = "https://getlorevia.com"

    # Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "support@mail.getlorevia.com"
    SUPPORT_EMAIL: str = "support@getlorevia.com"
    PRIVACY_DELETION_EMAIL: str = "support@mail.getlorevia.com"
    DATA_DELETION_GRACE_DAYS: int = 30
    LEGAL_EMAIL: str = "legal@getlorevia.com"
    BUSINESS_MAILING_ADDRESS: str = ""
    EMAIL_PREFERENCES_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60
    EMAIL_UNSUBSCRIBE_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60
    INTERNAL_JOB_SECRET: str | None = None

    # Public demo / sharing
    PUBLIC_MODE_ENABLED: bool = True
    PUBLIC_FORUM_STATUS: str = "public"

    # Beta reads
    BETA_READ_MIN_WINDOW_DAYS: int = 3
    BETA_READ_MAX_WINDOW_DAYS: int = 7
    BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY: bool = False
    BETA_READ_ALLOW_LATE_FEEDBACK: bool = False
    BETA_READ_MISSED_PENALTY_THRESHOLD: int = 3
    BETA_READ_PENALTY_ENABLED: bool = True
    BETA_READ_PENALTY_TYPE: str = "warning"
    BETA_READ_PENALTY_AMOUNT: int = 0
    # Monitoring
    SENTRY_DSN: str | None = None
    SENTRY_API_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0.0, le=1.0)
    SENTRY_API_PROFILES_SAMPLE_RATE: float = Field(default=0.1, ge=0.0, le=1.0)
    SENTRY_WORKER_TRACES_SAMPLE_RATE: float = Field(default=0.05, ge=0.0, le=1.0)
    SENTRY_WORKER_PROFILES_SAMPLE_RATE: float = Field(default=0.01, ge=0.0, le=1.0)

    # Supabase OAuth
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None

    # Processing
    LAZY_PROCESS_INITIAL_CHAPTERS: int = 2
    CHUNK_TARGET_TOKENS: int = 650
    CHUNK_MAX_TOKENS: int = 900
    CHUNK_MIN_TOKENS: int = 260
    CHUNK_OVERLAP_TOKENS: int = 120
    CHUNK_OVERLAP_RATIO: float = 0.07
    EXTRACTION_BATCH_MAX_TOKENS: int = 7000
    EXTRACTION_BATCH_MAX_CHUNKS: int = 6
    EXTRACTION_EMBED_BATCH_SIZE: int = 24
    EXTRACTION_EMBED_CONCURRENCY: int = 2
    PROCESSING_PIPELINE_VERSION: str = "2026-06"
    EXTRACTION_WORKER_CONCURRENCY: int = Field(default=2, ge=1, le=64)
    ANALYSIS_WORKER_CONCURRENCY: int = Field(default=1, ge=1, le=64)
    EMBEDDING_WORKER_CONCURRENCY: int = Field(default=1, ge=1, le=64)
    INTELLIGENCE_WORKER_CONCURRENCY: int = Field(default=1, ge=1, le=64)
    MAINTENANCE_WORKER_CONCURRENCY: int = Field(default=1, ge=1, le=64)
    LLM_CHAT_RPM_LIMIT: int = 60
    LLM_CHAT_TPM_LIMIT: int = 500_000
    LLM_EMBEDDING_RPM_LIMIT: int = 120
    LLM_EMBEDDING_TPM_LIMIT: int = 1_000_000
    LLM_MAX_CONCURRENT_CALLS_PER_USER: int = 4
    LLM_PROCESSING_SLOT_WAIT_SECONDS: float = Field(default=15.0, ge=0.0, le=60.0)
    AUTHOR_LLM_PROVIDER_COST_LIMIT_USD: float = 4.00
    AUTHOR_LLM_RESERVATION_CEILING_USD: float = 3.80
    AUTHOR_LLM_PROCESSING_RESERVE_USD: float = 2.50
    ARCHITECT_LLM_PROVIDER_COST_LIMIT_USD: float = 10.00
    ARCHITECT_LLM_RESERVATION_CEILING_USD: float = 9.50
    ARCHITECT_LLM_PROCESSING_RESERVE_USD: float = 6.25
    LLM_PROVIDER_BREAKER_FAILURES: int = 5
    LLM_PROVIDER_BREAKER_WINDOW_SECONDS: int = 30
    LLM_PROVIDER_BREAKER_INITIAL_COOLDOWN_SECONDS: int = 60
    LLM_PROVIDER_BREAKER_MAX_COOLDOWN_SECONDS: int = 15 * 60
    MONTHLY_WORKER_INFRA_COST_USD: float = 19.99
    STORAGE_COST_PER_GB_MONTH_USD: float = 0.015
    DEDUP_SIMILARITY_THRESHOLD: float = 0.88
    INGESTION_CHAPTER_UPLOAD_CONCURRENCY: int = 4
    INGESTION_CHAPTER_DISPATCH_WINDOW: int = 3
    INGESTION_CHAPTER_DISPATCH_DELAY_SECONDS: int = 1
    SEARCH_SIMILARITY_THRESHOLD: float = 0.65
    SEARCH_MAX_CONTEXT_CHUNKS: int = 3
    READER_SEARCH_SIMILARITY_THRESHOLD: float = 0.55
    READER_SEARCH_CANDIDATE_CHUNKS: int = 10
    READER_SEARCH_RETURN_CHUNKS: int = 4
    ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD: float = 0.28
    ADVISOR_GENERAL_SEARCH_CHUNKS: int = 8
    ADVISOR_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD: float = 0.22
    ADVISOR_CONTINUITY_SEARCH_CHUNKS: int = 12
    SERIES_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD: float = 0.22
    SERIES_CONTINUITY_SEARCH_CANDIDATE_CHUNKS: int = 10
    SERIES_CONTINUITY_SEARCH_RETURN_CHUNKS: int = 6
    PASSWORD_RESET_TOKEN_TTL_SECONDS: int = 1800
    PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS: int = 120
    EMAIL_VERIFICATION_TOKEN_TTL_SECONDS: int = 86400
    # Tier limits
    FREE_MAX_BOOKS: int = 0
    AUTHOR_MAX_UPLOADS: int = 15
    BOOK_UPLOAD_MAX_BYTES: int = 100 * 1024 * 1024
    COVER_UPLOAD_MAX_BYTES: int = 5 * 1024 * 1024
    MANUSCRIPT_IMPORT_MAX_BYTES: int = 20 * 1024 * 1024
    MANUSCRIPT_IMPORT_MAX_FILES: int = 20
    MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES: int = 60 * 1024 * 1024
    MANUSCRIPT_IMPORT_ASYNC_THRESHOLD_BYTES: int = 1024 * 1024
    MANUSCRIPT_IMPORT_INLINE_PROCESSING_MAX_CHAPTERS: int = 1
    WORLD_BUILDING_UPLOAD_MAX_BYTES: int = 20 * 1024 * 1024
    WORLD_BUILDING_UPLOAD_MAX_FILES: int = 20
    WORLD_BUILDING_UPLOAD_MAX_TOTAL_BYTES: int = 60 * 1024 * 1024
    VAULT_IMPORT_MAX_BYTES: int = 25 * 1024 * 1024
    UPLOAD_ARCHIVE_MAX_ENTRIES: int = 500
    UPLOAD_ARCHIVE_MAX_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024
    UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO: int = 100
    WORKSPACE_REGEX_MAX_PATTERN_LENGTH: int = 200
    FREE_TOTAL_TOKEN_BUDGET: int = 150000
    FREE_SEARCH_PER_DAY: int = 0
    FREE_SUMMARY_PER_HOUR: int = 0
    FREE_PREDICTION_PER_DAY: int = 1
    FREE_RECALL_PER_DAY: int = 0
    AUTHOR_PREDICTION_PER_DAY: int = 30
    ARCHITECT_PREDICTION_PER_DAY: int = 60
    TRIAL_HIGH_COST_TURNS_PER_DAY: int = 20
    AUTHOR_HIGH_COST_TURNS_PER_DAY: int = 30
    ARCHITECT_HIGH_COST_TURNS_PER_DAY: int = 60
    FREE_ADVISOR_PER_DAY: int = 0
    FREE_ADVISOR_PER_WEEK: int = 1
    FREE_ADVISOR_PER_MONTH: int = 4
    TRIAL_AUTHOR_ADVISOR_PER_DAY: int = 20
    AUTHOR_ADVISOR_PER_DAY: int = 30
    AUTHOR_ADVISOR_PER_WEEK: int = 210
    AUTHOR_ADVISOR_PER_MONTH: int = 900
    ARCHITECT_ADVISOR_PER_DAY: int = 60
    ARCHITECT_ADVISOR_PER_WEEK: int = 420
    ARCHITECT_ADVISOR_PER_MONTH: int = 1800
    FREE_LLM_TOKENS_5H: int = 25000
    FREE_LLM_TOKENS_WEEK: int = 75000
    FREE_LLM_TOKENS_MONTH: int = 250000
    AUTHOR_LLM_TOKENS_5H: int = 12_000_000
    AUTHOR_LLM_TOKENS_WEEK: int = 12_000_000
    AUTHOR_LLM_TOKENS_MONTH: int = 12_000_000
    ARCHITECT_LLM_TOKENS_5H: int = 30_000_000
    ARCHITECT_LLM_TOKENS_WEEK: int = 30_000_000
    ARCHITECT_LLM_TOKENS_MONTH: int = 30_000_000
    FREE_MANUAL_REPROCESS_TOKENS_5H: int = 25000
    FREE_MANUAL_REPROCESS_TOKENS_WEEK: int = 75000
    FREE_MANUAL_REPROCESS_TOKENS_MONTH: int = 250000
    AUTHOR_MANUAL_REPROCESS_TOKENS_5H: int = 12_000_000
    AUTHOR_MANUAL_REPROCESS_TOKENS_WEEK: int = 12_000_000
    AUTHOR_MANUAL_REPROCESS_TOKENS_MONTH: int = 12_000_000
    ARCHITECT_MANUAL_REPROCESS_TOKENS_5H: int = 30_000_000
    ARCHITECT_MANUAL_REPROCESS_TOKENS_WEEK: int = 30_000_000
    ARCHITECT_MANUAL_REPROCESS_TOKENS_MONTH: int = 30_000_000
    PROCESSING_ALLOWANCES_MODE: str = "enforce"
    AUTHOR_ACTIVE_WORD_LIMIT: int = 2_000_000
    ARCHITECT_ACTIVE_WORD_LIMIT: int = 8_000_000
    AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT: int = 1_000_000
    ARCHITECT_MONTHLY_PROCESSED_WORD_LIMIT: int = 4_000_000
    AUTHOR_SOURCE_STORAGE_LIMIT_BYTES: int = 5 * 1024 * 1024 * 1024
    ARCHITECT_SOURCE_STORAGE_LIMIT_BYTES: int = 25 * 1024 * 1024 * 1024
    FREE_CONTINUITY_PER_DAY: int = 0
    FREE_CONTINUITY_PER_MINUTE: int = 0
    AUTHOR_CONTINUITY_PER_MINUTE: int = 20
    ARCHITECT_CONTINUITY_PER_MINUTE: int = 50
    DEVICE_TRIAL_ENFORCEMENT_ENABLED: bool = True
    DEVICE_TRIAL_MAX_ACCOUNTS: int = 2

    # User help.
    SUPPORT_ASSISTANT_ENABLED: bool = True

    # Cloudflare Tunnel
    CLOUDFLARE_TUNNEL_TOKEN: str | None = None  # Option 1 security

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    def production_configuration_errors(self) -> list[str]:
        if self.DEPLOYMENT_ENV != "production":
            return []

        errors: list[str] = []
        if self.DEBUG:
            errors.append("DEBUG must be false")
        if self.DATABASE_SQL_ECHO:
            errors.append("DATABASE_SQL_ECHO must be false")
        edge_proxy_secret = self.resolved_edge_proxy_secret()
        if (
            not EDGE_PROXY_SECRET_PATTERN.fullmatch(edge_proxy_secret)
            or edge_proxy_secret.casefold() in EDGE_PROXY_SECRET_PLACEHOLDERS
        ):
            errors.append(
                "EDGE_PROXY_SECRET must contain 32-128 URL-safe characters, "
                "provided directly or through EDGE_PROXY_SECRET_FILE"
            )
        if len(self.JWT_SECRET.strip()) < 32:
            errors.append("JWT_SECRET must contain at least 32 characters")

        app_url = urlsplit(self.APP_URL)
        if app_url.scheme != "https" or not app_url.hostname:
            errors.append("APP_URL must be an absolute HTTPS URL")
        elif app_url.hostname in {"localhost", "127.0.0.1", "::1"}:
            errors.append("APP_URL cannot use a loopback host")

        origins = cors_origins_for_value(self.BACKEND_CORS_ORIGINS)
        if not origins:
            errors.append("BACKEND_CORS_ORIGINS must contain at least one HTTPS origin")
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname:
                errors.append("BACKEND_CORS_ORIGINS may contain only absolute HTTPS origins")
                break
            if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                errors.append("BACKEND_CORS_ORIGINS cannot contain loopback hosts")
                break

        hosts = [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]
        if not hosts or "*" in hosts:
            errors.append("ALLOWED_HOSTS must be explicit and cannot contain a wildcard")

        redis_url = urlsplit(self.REDIS_URL)
        if not redis_url.hostname or not redis_url.password:
            errors.append("REDIS_URL must include a host and password")

        if self.S3_ENDPOINT_URL:
            storage_url = urlsplit(self.S3_ENDPOINT_URL)
            if storage_url.scheme != "https" or not storage_url.hostname:
                errors.append("S3_ENDPOINT_URL must be an absolute HTTPS URL")

        if self.DIRECT_PUBLIC_ASSETS_ENABLED:
            public_asset_url = urlsplit(str(self.PUBLIC_ASSET_BASE_URL or ""))
            if public_asset_url.scheme != "https" or not public_asset_url.hostname:
                errors.append(
                    "PUBLIC_ASSET_BASE_URL must be an absolute HTTPS URL when "
                    "DIRECT_PUBLIC_ASSETS_ENABLED is true"
                )
            elif public_asset_url.hostname in {"localhost", "127.0.0.1", "::1"}:
                errors.append("PUBLIC_ASSET_BASE_URL cannot use a loopback host")

        if self.GEMINI_API_KEY:
            for field_name, model in (
                ("GEMINI_EXTRACT_MODEL", self.GEMINI_EXTRACT_MODEL),
                ("GEMINI_INTEL_MODEL", self.GEMINI_INTEL_MODEL),
            ):
                normalized_model = model.strip().lower()
                if normalized_model.startswith(("gemini-1.", "gemini-2.0")):
                    errors.append(f"{field_name} references a retired Gemini model")

        paddle_required = {
            "PADDLE_API_KEY": self.PADDLE_API_KEY,
            "PADDLE_WEBHOOK_SECRET": self.PADDLE_WEBHOOK_SECRET,
            "PADDLE_DEFAULT_CHECKOUT_URL": self.PADDLE_DEFAULT_CHECKOUT_URL,
            "PADDLE_AUTHOR_MONTHLY_PRICE_ID": self.PADDLE_AUTHOR_MONTHLY_PRICE_ID,
            "PADDLE_AUTHOR_ANNUAL_PRICE_ID": self.PADDLE_AUTHOR_ANNUAL_PRICE_ID,
            "PADDLE_ARCHITECT_MONTHLY_PRICE_ID": self.PADDLE_ARCHITECT_MONTHLY_PRICE_ID,
            "PADDLE_ARCHITECT_ANNUAL_PRICE_ID": self.PADDLE_ARCHITECT_ANNUAL_PRICE_ID,
        }
        missing_paddle = [name for name, value in paddle_required.items() if not value]
        if missing_paddle:
            errors.append(
                "Paddle billing configuration is incomplete: " + ", ".join(missing_paddle)
            )
        elif not str(self.PADDLE_DEFAULT_CHECKOUT_URL).startswith("https://"):
            errors.append("PADDLE_DEFAULT_CHECKOUT_URL must use HTTPS")
        return errors

    def resolved_edge_proxy_secret(self) -> str:
        direct_value = str(self.EDGE_PROXY_SECRET or "").strip()
        if direct_value:
            return direct_value
        secret_file = str(self.EDGE_PROXY_SECRET_FILE or "").strip()
        if not secret_file:
            return ""
        try:
            return Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        errors = self.production_configuration_errors()
        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self


# Pydantic Settings resolves required values from environment variables at runtime.
settings = Settings()  # pyright: ignore[reportCallIssue]


def cors_origins() -> list[str]:
    return cors_origins_for_value(settings.BACKEND_CORS_ORIGINS)


def cors_middleware_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "allow_origins": cors_origins(),
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-CSRF-Token",
            "X-Admin-CSRF-Token",
        ],
    }
    if settings.DEBUG:
        options["allow_origin_regex"] = LOCALHOST_CORS_ORIGIN_REGEX
    return options


def allowed_hosts() -> list[str]:
    return [host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()]


def is_local_mode() -> bool:
    # Derive ONLY from the explicit DEBUG flag — never from APP_URL.
    # APP_URL can be misconfigured in production, which previously caused
    # every user to silently receive Pro access.
    return settings.DEBUG


def effective_tier(tier: str) -> str:
    if settings.DEBUG:
        return "architect"
    normalized = (tier or "free").strip().lower()
    return {
        "reader": "free",
        "collaborator": "free",
        "pro": "author",
        "power": "architect",
    }.get(normalized, normalized)
