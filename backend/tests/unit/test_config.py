from app.core.config import (
    LOCALHOST_CORS_ORIGIN_REGEX,
    Settings,
    cors_middleware_options,
    cors_origins,
    settings,
)


def test_gemini_defaults_use_current_stable_model():
    assert Settings.model_fields["GEMINI_EXTRACT_MODEL"].default == "gemini-2.5-flash"
    assert Settings.model_fields["GEMINI_INTEL_MODEL"].default == "gemini-2.5-flash"


def test_latency_rollout_and_sentry_sampling_defaults_are_safe():
    assert Settings.model_fields["CURSOR_PAGE_APIS_ENABLED"].default is True
    assert Settings.model_fields["WORLD_ANALYSIS_SNAPSHOTS_ENABLED"].default is True
    assert Settings.model_fields["INDEXED_SEARCH_ENABLED"].default is True
    assert Settings.model_fields["READER_EVENTS_V2_ENABLED"].default is True
    assert Settings.model_fields["DIRECT_PUBLIC_ASSETS_ENABLED"].default is False
    assert Settings.model_fields["PUBLIC_ASSET_BASE_URL"].default is None
    assert Settings.model_fields["PUBLIC_ASSET_CACHE_MAX_AGE_SECONDS"].default == 60
    assert Settings.model_fields["MANUSCRIPT_EXPORT_SPOOL_DIRECTORY"].default is None
    assert (
        Settings.model_fields["SENTRY_WORKER_TRACES_SAMPLE_RATE"].default
        < Settings.model_fields["SENTRY_API_TRACES_SAMPLE_RATE"].default
    )
    assert (
        Settings.model_fields["SENTRY_WORKER_PROFILES_SAMPLE_RATE"].default
        < Settings.model_fields["SENTRY_API_PROFILES_SAMPLE_RATE"].default
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


def test_production_configuration_rejects_unsafe_auth_cors_and_billing(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "DATABASE_SQL_ECHO", True)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET", None)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET_FILE", None)
    monkeypatch.setattr(settings, "JWT_SECRET", "short")
    monkeypatch.setattr(settings, "APP_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "*")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(settings, "GEMINI_EXTRACT_MODEL", "gemini-1.5-flash")
    monkeypatch.setattr(settings, "GEMINI_INTEL_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(settings, "PADDLE_API_KEY", None)
    monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", None)
    monkeypatch.setattr(settings, "PADDLE_DEFAULT_CHECKOUT_URL", None)
    monkeypatch.setattr(settings, "PADDLE_AUTHOR_MONTHLY_PRICE_ID", None)
    monkeypatch.setattr(settings, "PADDLE_AUTHOR_ANNUAL_PRICE_ID", None)
    monkeypatch.setattr(settings, "PADDLE_ARCHITECT_MONTHLY_PRICE_ID", None)
    monkeypatch.setattr(settings, "PADDLE_ARCHITECT_ANNUAL_PRICE_ID", None)

    errors = settings.production_configuration_errors()

    assert "DEBUG must be false" in errors
    assert "DATABASE_SQL_ECHO must be false" in errors
    assert any(error.startswith("EDGE_PROXY_SECRET must contain") for error in errors)
    assert "JWT_SECRET must contain at least 32 characters" in errors
    assert "APP_URL must be an absolute HTTPS URL" in errors
    assert "BACKEND_CORS_ORIGINS may contain only absolute HTTPS origins" in errors
    assert "ALLOWED_HOSTS must be explicit and cannot contain a wildcard" in errors
    assert "REDIS_URL must include a host and password" in errors
    assert "GEMINI_EXTRACT_MODEL references a retired Gemini model" in errors
    assert "GEMINI_INTEL_MODEL references a retired Gemini model" in errors
    assert any(error.startswith("Paddle billing configuration is incomplete") for error in errors)


def test_production_configuration_accepts_hardened_vps_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "DATABASE_SQL_ECHO", False)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET", "e" * 48)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET_FILE", None)
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 48)
    monkeypatch.setattr(settings, "APP_URL", "https://getlorevia.com")
    monkeypatch.setattr(
        settings,
        "BACKEND_CORS_ORIGINS",
        "https://getlorevia.com,https://www.getlorevia.com",
    )
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "api.getlorevia.com,127.0.0.1")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://:secret@redis:6379/0")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://storage.example.com")
    monkeypatch.setattr(settings, "PADDLE_API_KEY", "api-key")
    monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(
        settings,
        "PADDLE_DEFAULT_CHECKOUT_URL",
        "https://getlorevia.com/checkout",
    )
    monkeypatch.setattr(settings, "PADDLE_AUTHOR_MONTHLY_PRICE_ID", "pri-author-month")
    monkeypatch.setattr(settings, "PADDLE_AUTHOR_ANNUAL_PRICE_ID", "pri-author-year")
    monkeypatch.setattr(settings, "PADDLE_ARCHITECT_MONTHLY_PRICE_ID", "pri-architect-month")
    monkeypatch.setattr(settings, "PADDLE_ARCHITECT_ANNUAL_PRICE_ID", "pri-architect-year")

    assert settings.production_configuration_errors() == []


def test_production_configuration_requires_https_public_asset_origin(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(settings, "DIRECT_PUBLIC_ASSETS_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_ASSET_BASE_URL", "http://localhost:9000")

    assert any(
        error.startswith("PUBLIC_ASSET_BASE_URL must be an absolute HTTPS URL")
        for error in settings.production_configuration_errors()
    )


def test_edge_proxy_secret_can_be_loaded_from_a_secret_file(tmp_path, monkeypatch):
    secret_file = tmp_path / "edge-proxy-secret"
    secret_file.write_text("f" * 48 + "\n", encoding="utf-8")
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET", None)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET_FILE", str(secret_file))

    assert settings.resolved_edge_proxy_secret() == "f" * 48


def test_edge_proxy_secret_file_errors_do_not_expose_the_path(monkeypatch):
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET", None)
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET_FILE", "missing-secret-file")

    assert settings.resolved_edge_proxy_secret() == ""


def test_production_configuration_rejects_edge_proxy_placeholder(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(
        settings,
        "EDGE_PROXY_SECRET",
        "replace_with_64_character_random_edge_secret",
    )
    monkeypatch.setattr(settings, "EDGE_PROXY_SECRET_FILE", None)

    assert any(
        error.startswith("EDGE_PROXY_SECRET must contain")
        for error in settings.production_configuration_errors()
    )


def test_architect_daily_advisor_and_scan_limits_are_exact():
    assert settings.AUTHOR_ADVISOR_PER_DAY == 30
    assert settings.ARCHITECT_ADVISOR_PER_DAY == 60
    assert settings.AUTHOR_HIGH_COST_TURNS_PER_DAY == 30
    assert settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY == 60
    assert settings.AUTHOR_PREDICTION_PER_DAY == 30
    assert settings.ARCHITECT_PREDICTION_PER_DAY == 60


def test_architect_advisor_period_limits_are_at_least_twice_author_limits():
    assert settings.ARCHITECT_ADVISOR_PER_WEEK >= settings.AUTHOR_ADVISOR_PER_WEEK * 2
    assert settings.ARCHITECT_ADVISOR_PER_MONTH >= settings.AUTHOR_ADVISOR_PER_MONTH * 2


def test_architect_limits_are_at_least_two_and_a_half_times_author_limits():
    paired_limits = (
        (settings.AUTHOR_LLM_TOKENS_5H, settings.ARCHITECT_LLM_TOKENS_5H),
        (settings.AUTHOR_LLM_TOKENS_WEEK, settings.ARCHITECT_LLM_TOKENS_WEEK),
        (settings.AUTHOR_LLM_TOKENS_MONTH, settings.ARCHITECT_LLM_TOKENS_MONTH),
        (
            settings.AUTHOR_MANUAL_REPROCESS_TOKENS_5H,
            settings.ARCHITECT_MANUAL_REPROCESS_TOKENS_5H,
        ),
        (
            settings.AUTHOR_MANUAL_REPROCESS_TOKENS_WEEK,
            settings.ARCHITECT_MANUAL_REPROCESS_TOKENS_WEEK,
        ),
        (
            settings.AUTHOR_MANUAL_REPROCESS_TOKENS_MONTH,
            settings.ARCHITECT_MANUAL_REPROCESS_TOKENS_MONTH,
        ),
        (settings.AUTHOR_ACTIVE_WORD_LIMIT, settings.ARCHITECT_ACTIVE_WORD_LIMIT),
        (
            settings.AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT,
            settings.ARCHITECT_MONTHLY_PROCESSED_WORD_LIMIT,
        ),
        (
            settings.AUTHOR_SOURCE_STORAGE_LIMIT_BYTES,
            settings.ARCHITECT_SOURCE_STORAGE_LIMIT_BYTES,
        ),
        (
            settings.AUTHOR_CONTINUITY_PER_MINUTE,
            settings.ARCHITECT_CONTINUITY_PER_MINUTE,
        ),
        (
            settings.AUTHOR_LLM_PROVIDER_COST_LIMIT_USD,
            settings.ARCHITECT_LLM_PROVIDER_COST_LIMIT_USD,
        ),
        (
            settings.AUTHOR_LLM_RESERVATION_CEILING_USD,
            settings.ARCHITECT_LLM_RESERVATION_CEILING_USD,
        ),
        (
            settings.AUTHOR_LLM_PROCESSING_RESERVE_USD,
            settings.ARCHITECT_LLM_PROCESSING_RESERVE_USD,
        ),
    )

    assert all(architect * 2 >= author * 5 for author, architect in paired_limits)
