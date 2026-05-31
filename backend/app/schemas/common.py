from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool
