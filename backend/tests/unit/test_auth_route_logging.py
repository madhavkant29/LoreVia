import pytest
from fastapi import Response
from fastapi import HTTPException

from app.api.v1.routes.auth import oauth_supabase
from app.schemas.auth import SupabaseOAuthBody


@pytest.mark.asyncio
async def test_supabase_oauth_failure_does_not_log_response_body(monkeypatch, caplog):
    class FakeResponse:
        status_code = 401
        text = "error: invalid token secret=top-secret-value"

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return FakeResponse()

    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_URL", "https://supabase.example.com", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.settings.SUPABASE_SERVICE_KEY", "service-key", raising=False)
    monkeypatch.setattr("app.api.v1.routes.auth.httpx.AsyncClient", FakeAsyncClient)

    body = SupabaseOAuthBody(token="user-token", accepted_terms=True, device_id="device-logging-1234567890")
    response = Response()

    with caplog.at_level("WARNING", logger="lorevia.auth"):
        with pytest.raises(HTTPException) as exc_info:
            await oauth_supabase(body=body, response=response, db=object(), _=None)

    assert exc_info.value.status_code == 401
    assert "top-secret-value" not in caplog.text
    assert "Supabase OAuth verification failed" in caplog.text
