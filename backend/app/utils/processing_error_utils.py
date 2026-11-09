"""User-facing processing failure messages.

Raw exception text stays in ``TaskExecution.error_detail`` and structured logs.
The values produced here are the only failure text written into a book's
``writer_workspace`` where authors can read them, so they must never contain
file paths, identifiers, tokens, or provider internals.
"""

from __future__ import annotations

import re
from typing import Final

LLM_CAPACITY_MESSAGE: Final = "AI processing capacity is temporarily busy. Retrying shortly."
LLM_BUDGET_MESSAGE: Final = "AI processing budget reached. Review your plan before continuing."
LLM_TOKEN_LIMIT_MESSAGE: Final = (
    "Token allowance reached. Processing will resume when the window refreshes."
)
MONTHLY_PROCESSED_WORDS_MESSAGE: Final = (
    "Monthly processed-word allowance reached. Continue after your plan window resets."
)

GENERIC_PROCESSING_FAILURE: Final = (
    "Processing stopped before it finished. Retry to continue, and contact "
    "support if it keeps failing."
)

_BUDGET_FAILURE: Final = (
    "This account has used its free analysis allowance. Upgrade your plan to "
    "keep processing this manuscript."
)

_LEGACY_DOC_FAILURE: Final = (
    "This looks like an older .doc file. Save it as a .docx document and try again."
)

_UNREADABLE_FILE_FAILURE: Final = (
    "We couldn't read this manuscript file. Check that it opens correctly, then upload it again."
)

_EMPTY_TEXT_FAILURE: Final = (
    "We couldn't find readable text in this manuscript. Check the file contents and try again."
)

_SAFE_MESSAGES: Final = frozenset(
    {
        LLM_BUDGET_MESSAGE,
        LLM_CAPACITY_MESSAGE,
        LLM_TOKEN_LIMIT_MESSAGE,
        MONTHLY_PROCESSED_WORDS_MESSAGE,
        GENERIC_PROCESSING_FAILURE,
        _BUDGET_FAILURE,
        _LEGACY_DOC_FAILURE,
        _UNREADABLE_FILE_FAILURE,
        _EMPTY_TEXT_FAILURE,
        "Something went wrong. Please try again.",
    }
)

_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(r"legacy \.doc|\.doc files require", re.IGNORECASE),
        _LEGACY_DOC_FAILURE,
    ),
    (
        re.compile(
            r"missing_chapter_payload|no importable manuscript content|"
            r"empty file|uploaded file is empty|contains no readable text",
            re.IGNORECASE,
        ),
        _EMPTY_TEXT_FAILURE,
    ),
    (
        re.compile(r"budget_exhausted|insufficient_remaining_budget|token budget", re.IGNORECASE),
        _BUDGET_FAILURE,
    ),
    (
        re.compile(
            r"not a valid|invalid (pdf|epub|docx|zip)|badzipfile|unsupported|"
            r"failed to parse|parse error|corrupt|incomplete pdf|"
            r"package not found|keyerror|emptyfileerror|filedataerror",
            re.IGNORECASE,
        ),
        _UNREADABLE_FILE_FAILURE,
    ),
)


def friendly_processing_error(error: str | None) -> str:
    """Map a raw processing error into an author-safe, actionable message."""
    text = " ".join(str(error or "").split())
    if not text:
        return GENERIC_PROCESSING_FAILURE
    if text in _SAFE_MESSAGES:
        return text
    for pattern, message in _PATTERNS:
        if pattern.search(text):
            return message
    return GENERIC_PROCESSING_FAILURE
