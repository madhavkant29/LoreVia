from __future__ import annotations

from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError

ADVISOR_STREAM_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    OSError,
    TimeoutError,
    OpenAIError,
    SQLAlchemyError,
)

ADVISOR_CONTENT_READ_ERRORS = (
    RuntimeError,
    ValueError,
    UnicodeError,
    OSError,
)
