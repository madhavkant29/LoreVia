from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
