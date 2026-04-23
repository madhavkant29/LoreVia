from pydantic import BaseModel


class PublicChapterIn(BaseModel):
    title: str
    text: str
    description: str | None = None


class PublicBookManualIn(BaseModel):
    title: str
    author: str | None = None
    genre: str | None = None
    description: str | None = None
    chapters: list[PublicChapterIn]
