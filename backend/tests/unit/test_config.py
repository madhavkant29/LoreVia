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


def test_load_env_file_allows_dotenv_local_to_override_repo_defaults(tmp_path, monkeypatch):
    from app.core.config import _load_env_file
    import os

    monkeypatch.delenv("LOREVIA_TEST_OVERRIDE", raising=False)

    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text("LOREVIA_TEST_OVERRIDE=base\n", encoding="utf-8")
    local_env.write_text("LOREVIA_TEST_OVERRIDE=local\n", encoding="utf-8")

    _load_env_file(base_env)
    _load_env_file(local_env, override_loaded_values=True)

    assert os.environ["LOREVIA_TEST_OVERRIDE"] == "local"
