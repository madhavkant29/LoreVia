"""Shared retry limits and backoff helpers.

Paid provider calls are intentionally capped more tightly than infrastructure
retries so a transient failure cannot multiply LLM or embedding spend.
"""

LLM_MAX_RETRIES = 1
LLM_MAX_ATTEMPTS = LLM_MAX_RETRIES + 1
NON_LLM_MAX_RETRIES = 6
RETRY_BACKOFF_BASE_SECONDS = 2
RETRY_BACKOFF_MAX_SECONDS = 60


def exponential_backoff_seconds(
    retry_index: int,
    *,
    base_seconds: int = RETRY_BACKOFF_BASE_SECONDS,
    max_seconds: int = RETRY_BACKOFF_MAX_SECONDS,
) -> int:
    """Return a bounded exponential delay for a zero-based retry index."""

    if retry_index < 0:
        raise ValueError("retry_index must be non-negative")
    if base_seconds <= 0:
        raise ValueError("base_seconds must be positive")
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    return min(max_seconds, base_seconds * (2**retry_index))
