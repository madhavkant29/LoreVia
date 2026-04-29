from pydantic import BaseModel


class RateLimitOverrideBody(BaseModel):
    search_per_hour: int | None = None
    summary_per_hour: int | None = None
    chat_per_day: int | None = None
    api_per_minute: int | None = None


class UpdateUserTierBody(BaseModel):
    tier: str
