from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid


class BookUpload(BaseModel):
    title: str
    genre: str | None = None
    author: str | None = None


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
