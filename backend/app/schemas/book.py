from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class BookUpload(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    genre: str | None = Field(None, max_length=100)
    author: str | None = Field(None, max_length=255)


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: str | None
    genre: str | None
    format: str
    status: str
    total_chapters: int | None
    created_at: datetime


class BookStatusOut(BaseModel):
    status: str
    total_chapters: int | None = None
    total_chunks: int | None = None
