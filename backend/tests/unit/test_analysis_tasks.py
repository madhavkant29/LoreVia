import json
from unittest.mock import MagicMock

import httpx
import pytest
from celery.exceptions import Retry as CeleryRetry
from fastapi import HTTPException
from httpx import Request, Response
from openai import APIConnectionError
from sqlalchemy.exc import OperationalError

from app.workers.tasks.analysis_tasks import _is_retryable_analysis_error, analyse_chapter_task


def _raise_after_closing_coro(exc: Exception):
    def raise_error(coro):
        coro.close()
        raise exc

    return raise_error


class TestIsRetryableAnalysisError:
    def test_timeout_connection_protocol_errors_are_retryable(self):
        assert _is_retryable_analysis_error(httpx.TimeoutException("timed out"))
        assert _is_retryable_analysis_error(httpx.ConnectError("connection failed"))
        assert _is_retryable_analysis_error(httpx.RemoteProtocolError("protocol error"))

    def test_http_429_and_5xx_status_are_retryable(self):
        req = Request("POST", "https://api.openai.com/v1/chat/completions")
        assert _is_retryable_analysis_error(
            httpx.HTTPStatusError("rate limited", request=req, response=Response(429))
        )
        assert _is_retryable_analysis_error(
            httpx.HTTPStatusError("server error", request=req, response=Response(503))
        )

    def test_http_400_is_not_retryable(self):
        req = Request("POST", "https://api.openai.com/v1/chat/completions")
        assert not _is_retryable_analysis_error(
            httpx.HTTPStatusError("bad request", request=req, response=Response(400))
        )

    def test_json_decode_error_is_not_retryable(self):
        assert not _is_retryable_analysis_error(json.JSONDecodeError("bad json", "{", 0))

    def test_generic_value_error_is_not_retryable(self):
        assert not _is_retryable_analysis_error(ValueError("something went wrong"))

    def test_retryable_message_markers(self):
        assert _is_retryable_analysis_error(Exception("rate_limit exceeded"))
        assert _is_retryable_analysis_error(Exception("connection reset by peer"))
        assert not _is_retryable_analysis_error(Exception("unknown failure"))

    def test_database_deadlock_is_retryable(self):
        error = OperationalError(
            "UPDATE books SET writer_workspace = '{}'",
            {},
            RuntimeError("deadlock detected"),
        )

        assert _is_retryable_analysis_error(error)

    def test_openai_connection_error_is_retryable(self):
        error = APIConnectionError(
            request=Request("POST", "https://api.openai.com/v1/chat/completions")
        )

        assert _is_retryable_analysis_error(error)


class TestAnalyseChapterTaskRetryFilter:
    def test_retryable_error_does_not_replay_started_analysis(self, monkeypatch):
        monkeypatch.setattr(
            "app.workers.tasks.analysis_tasks.run_worker_coro",
            MagicMock(side_effect=_raise_after_closing_coro(httpx.TimeoutException("timed out"))),
        )

        task = analyse_chapter_task.__wrapped__.__func__
        mock_self = MagicMock()
        mock_self.request.retries = 1
        mock_self.request.headers = None
        mock_self.retry.side_effect = CeleryRetry("should not be called")

        with pytest.raises(httpx.TimeoutException):
            task(mock_self, "ch-1", "text", "title")

        mock_self.retry.assert_not_called()

    def test_retryable_error_before_analysis_starts_can_retry(self, monkeypatch):
        monkeypatch.setattr(
            "app.workers.tasks.analysis_tasks.run_worker_coro",
            MagicMock(side_effect=_raise_after_closing_coro(httpx.TimeoutException("timed out"))),
        )

        task = analyse_chapter_task.__wrapped__.__func__
        mock_self = MagicMock()
        mock_self.request.retries = 1
        mock_self.request.headers = None
        mock_self.retry.side_effect = CeleryRetry("retry triggered")

        with pytest.raises(CeleryRetry):
            task(mock_self, "ch-1", "book-1", "title", is_reprocessing=True)

        mock_self.retry.assert_called_once_with(
            exc=mock_self.retry.call_args[1]["exc"], countdown=4
        )

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (
                HTTPException(429, "LLM usage token limit exceeded for the 5-hour window."),
                {"paused": "llm_usage_limit"},
            ),
            (
                HTTPException(429, "LLM capacity is temporarily busy. Retry shortly."),
                {"paused": "llm_capacity"},
            ),
        ],
    )
    def test_llm_control_errors_pause_without_task_retry(self, monkeypatch, error, expected):
        monkeypatch.setattr(
            "app.workers.tasks.analysis_tasks.run_worker_coro",
            MagicMock(side_effect=_raise_after_closing_coro(error)),
        )

        task = analyse_chapter_task.__wrapped__.__func__
        mock_self = MagicMock()
        mock_self.request.retries = 0
        mock_self.request.headers = None

        assert task(mock_self, "ch-1", "text", "title") == expected
        mock_self.retry.assert_not_called()

    def test_non_retryable_error_does_not_retry(self, monkeypatch):
        monkeypatch.setattr(
            "app.workers.tasks.analysis_tasks.run_worker_coro",
            MagicMock(
                side_effect=_raise_after_closing_coro(json.JSONDecodeError("bad json", "{", 0))
            ),
        )

        task = analyse_chapter_task.__wrapped__.__func__
        mock_self = MagicMock()
        mock_self.request.retries = 0
        mock_self.request.headers = None
        mock_self.retry.side_effect = CeleryRetry("should not be called")

        with pytest.raises(json.JSONDecodeError):
            task(mock_self, "ch-1", "text", "title")

        mock_self.retry.assert_not_called()

    def test_400_http_status_error_does_not_retry(self, monkeypatch):
        req = Request("POST", "https://api.openai.com/v1/chat/completions")
        bad_request_error = httpx.HTTPStatusError(
            "bad request", request=req, response=Response(400)
        )
        monkeypatch.setattr(
            "app.workers.tasks.analysis_tasks.run_worker_coro",
            MagicMock(side_effect=_raise_after_closing_coro(bad_request_error)),
        )

        task = analyse_chapter_task.__wrapped__.__func__
        mock_self = MagicMock()
        mock_self.request.retries = 0
        mock_self.request.headers = None
        mock_self.retry.side_effect = CeleryRetry("should not be called")

        with pytest.raises(httpx.HTTPStatusError):
            task(mock_self, "ch-1", "text", "title")

        mock_self.retry.assert_not_called()
