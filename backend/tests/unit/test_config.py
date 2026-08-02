from app.core.config import (
    LOCALHOST_CORS_ORIGIN_REGEX,
    cors_middleware_options,
    cors_origins,
    settings,
)


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


def test_load_env_file_allows_dotenv_local_to_override_repo_defaults(tmp_path, monkeypatch):
    import os

    from app.core.config import _load_env_file

    monkeypatch.delenv("LoreVia_TEST_OVERRIDE", raising=False)

    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text("LoreVia_TEST_OVERRIDE=base\n", encoding="utf-8")
    local_env.write_text("LoreVia_TEST_OVERRIDE=local\n", encoding="utf-8")

    _load_env_file(base_env)
    _load_env_file(local_env, override_loaded_values=True)

    assert os.environ["LoreVia_TEST_OVERRIDE"] == "local"


def test_cors_middleware_options_only_allow_localhost_regex_in_debug(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DEBUG", True, raising=False)
    monkeypatch.setattr(
        "app.core.config.settings.BACKEND_CORS_ORIGINS",
        "https://getlorevia.com",
        raising=False,
    )

    options = cors_middleware_options()

    assert options["allow_origins"] == ["https://getlorevia.com"]
    assert options["allow_origin_regex"] == LOCALHOST_CORS_ORIGIN_REGEX
    assert "X-CSRF-Token" in options["allow_headers"]
    assert "X-Admin-CSRF-Token" in options["allow_headers"]


def test_cors_middleware_options_exclude_localhost_regex_in_production(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)
    monkeypatch.setattr(
        "app.core.config.settings.BACKEND_CORS_ORIGINS",
        "https://getlorevia.com",
        raising=False,
    )

    options = cors_middleware_options()

    assert options["allow_origins"] == ["https://getlorevia.com"]
    assert "allow_origin_regex" not in options
    assert "X-CSRF-Token" in options["allow_headers"]
    assert "X-Admin-CSRF-Token" in options["allow_headers"]


def test_public_forum_status_defaults_to_public():
    assert settings.PUBLIC_FORUM_STATUS == "public"
