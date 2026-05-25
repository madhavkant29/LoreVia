from app.core import database


def test_effective_pool_settings_uses_local_debug_fallback(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 1, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 0, raising=False)

    assert database._effective_pool_settings() == (5, 5)


def test_effective_pool_settings_preserves_explicit_values(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 3, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 1, raising=False)

    assert database._effective_pool_settings() == (3, 1)
