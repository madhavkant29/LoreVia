from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "LoreVia"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

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
    OPENAI_INTEL_MODEL: str = "gpt-4o"           # chat, predictions
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBED_DIM: int = 1536
    ANTHROPIC_API_KEY: str | None = None         # fallback

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@lorevia.app"

    # Monitoring
    SENTRY_DSN: str | None = None

    # Processing
    LAZY_PROCESS_INITIAL_CHAPTERS: int = 3
    CHUNK_MAX_TOKENS: int = 1500
    CHUNK_OVERLAP_TOKENS: int = 100
    DEDUP_SIMILARITY_THRESHOLD: float = 0.88
    SEARCH_SIMILARITY_THRESHOLD: float = 0.65

    # Tier limits
    FREE_MAX_BOOKS: int = 2
    FREE_SEARCH_PER_HOUR: int = 20
    FREE_SUMMARY_PER_HOUR: int = 30
    FREE_CHAT_PER_DAY: int = 10
    PRO_CHAT_PER_DAY: int = 100

    # Cloudflare Tunnel
    CLOUDFLARE_TUNNEL_TOKEN: str | None = None   # Option 1 security

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
