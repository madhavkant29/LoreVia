import pytest

from app.utils.retry_utils import LLM_MAX_ATTEMPTS, LLM_MAX_RETRIES, exponential_backoff_seconds


def test_llm_retry_limit_means_two_total_attempts() -> None:
    assert LLM_MAX_RETRIES == 1
    assert LLM_MAX_ATTEMPTS == 2


@pytest.mark.parametrize(
    ("retry_index", "expected"),
    [(0, 2), (1, 4), (2, 8), (3, 16), (4, 32), (5, 60), (6, 60)],
)
def test_exponential_backoff_seconds_is_bounded(retry_index: int, expected: int) -> None:
    assert exponential_backoff_seconds(retry_index) == expected


@pytest.mark.parametrize("retry_index", [-1, -10])
def test_exponential_backoff_seconds_rejects_negative_indexes(retry_index: int) -> None:
    with pytest.raises(ValueError, match="retry_index"):
        exponential_backoff_seconds(retry_index)
