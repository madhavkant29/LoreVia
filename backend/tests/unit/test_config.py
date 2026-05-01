from app.core.config import cors_origins


def test_cors_origins_include_localhost_and_loopback(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.settings.BACKEND_CORS_ORIGINS",
        "https://getlorevia.com,http://localhost:3000,http://127.0.0.1:3000",
        raising=False,
    )

    assert cors_origins() == [
        "https://getlorevia.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
