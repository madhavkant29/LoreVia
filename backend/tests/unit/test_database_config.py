from app.core import database


def test_effective_pool_settings_respects_env_overrides(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 10, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 8, raising=False)

    assert database._effective_pool_settings() == (10, 8)


def test_effective_pool_settings_preserves_explicit_values(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 3, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 2, raising=False)

    assert database._effective_pool_settings() == (3, 2)
