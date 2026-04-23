from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "LoreVia"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = "https://getlorevia.com,https://www.getlorevia.com,https://api.getlorevia.com,http://localhost:3000"
    ALLOWED_HOSTS: str = "getlorevia.com,www.getlorevia.com,api.getlorevia.com,localhost,127.0.0.1"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800
    DATABASE_SQL_ECHO: bool = False

    # Redis
    REDIS_URL: str
    REDIS_TTL_CHARACTER_PROFILE: int = 3600      # 1 hr
    REDIS_TTL_SUMMARY: int = 604800              # 7 days
    REDIS_TTL_GRAPH: int = 3600                  # 1 hr
    REDIS_TTL_SEARCH: int = 3600                 # 1 hr
    REDIS_TTL_RECALL: int = 86400                # 24 hrs
    REDIS_TTL_SESSION: int = 86400

    # Storage (Cloudflare R2 — PDFs/EPUBs only)
    S3_BUCKET: str
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    # AI — two models, cost discipline
    OPENAI_API_KEY: str
    OPENAI_EXTRACT_MODEL: str = "gpt-4o-mini"    # extraction, summaries
    OPENAI_INTEL_MODEL: str = "gpt-4o-mini"           # chat, predictions #revert to gpt-4o-mini for now, gpt-4o is too costly and not significantly better for our use case
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBED_DIM: int = 1536
    ANTHROPIC_API_KEY: str | None = None         # fallback
    GEMINI_API_KEY: str | None = None
    GEMINI_EXTRACT_MODEL: str = "gemini-1.5-flash"
    GEMINI_INTEL_MODEL: str = "gemini-1.5-flash"

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Paddle
    PADDLE_API_KEY: str | None = None
    PADDLE_WEBHOOK_SECRET: str | None = None
    PADDLE_DEFAULT_CHECKOUT_URL: str | None = None
    PADDLE_PRO_MONTHLY_PRICE_ID: str | None = None
    PADDLE_PRO_ANNUAL_PRICE_ID: str | None = None
    PADDLE_POWER_MONTHLY_PRICE_ID: str | None = None
    PADDLE_POWER_ANNUAL_PRICE_ID: str | None = None
    APP_URL: str = "http://localhost:3000"

    # Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "support@mail.getlorevia.com"
    SUPPORT_EMAIL: str = "support@getlorevia.com"
    LEGAL_EMAIL: str = "legal@getlorevia.com"

    # Monitoring
    SENTRY_DSN: str | None = None

    # Supabase OAuth
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None

    # Processing
    LAZY_PROCESS_INITIAL_CHAPTERS: int = 1
    CHUNK_TARGET_TOKENS: int = 900
    CHUNK_MAX_TOKENS: int = 1200
    CHUNK_MIN_TOKENS: int = 260
    CHUNK_OVERLAP_TOKENS: int = 80
    CHUNK_OVERLAP_RATIO: float = 0.07
    EXTRACTION_BATCH_MAX_TOKENS: int = 5000
    EXTRACTION_BATCH_MAX_CHUNKS: int = 4
    DEDUP_SIMILARITY_THRESHOLD: float = 0.88
    SEARCH_SIMILARITY_THRESHOLD: float = 0.65
    SEARCH_MAX_CONTEXT_CHUNKS: int = 3
    PASSWORD_RESET_TOKEN_TTL_SECONDS: int = 1800

    # Tier limits
    FREE_MAX_BOOKS: int = 2
    FREE_TOTAL_TOKEN_BUDGET: int = 250000
    FREE_SEARCH_PER_HOUR: int = 20
    FREE_SUMMARY_PER_HOUR: int = 30
    FREE_CHAT_PER_DAY: int = 10
    PRO_CHAT_PER_DAY: int = 100
    FREE_ADVISOR_PER_DAY: int = 20
    FREE_ADVISOR_PER_WEEK: int = 80
    FREE_ADVISOR_PER_MONTH: int = 240
    PRO_ADVISOR_PER_DAY: int = 80
    PRO_ADVISOR_PER_WEEK: int = 320
    PRO_ADVISOR_PER_MONTH: int = 960
    POWER_ADVISOR_PER_DAY: int = 200
    POWER_ADVISOR_PER_WEEK: int = 800
    POWER_ADVISOR_PER_MONTH: int = 2400
    FREE_CONTINUITY_PER_MINUTE: int = 6
    PRO_CONTINUITY_PER_MINUTE: int = 20
    POWER_CONTINUITY_PER_MINUTE: int = 40

    # Cloudflare Tunnel
    CLOUDFLARE_TUNNEL_TOKEN: str | None = None   # Option 1 security

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()  # type: ignore[call-arg]


def cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


def allowed_hosts() -> list[str]:
    return [host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()]


def is_local_mode() -> bool:
    app_url = (settings.APP_URL or "").lower()
    return settings.DEBUG or "localhost" in app_url or "127.0.0.1" in app_url


def effective_tier(tier: str) -> str:
    if is_local_mode():
        return "pro"
    return tier
