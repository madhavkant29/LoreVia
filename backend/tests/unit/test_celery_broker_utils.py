import ssl

from app.utils.celery_broker_utils import normalize_celery_redis_url


def test_normalize_celery_redis_url_keeps_plain_redis_unchanged():
    assert normalize_celery_redis_url("redis://:pw@redis:6379/0") == (
        "redis://:pw@redis:6379/0",
        {},
    )


def test_normalize_celery_redis_url_moves_tls_verification_into_broker_options():
    assert normalize_celery_redis_url(
        "rediss://:pw@redis:6379/0?ssl_cert_reqs=optional&socket_timeout=2"
    ) == (
        "rediss://:pw@redis:6379/0?socket_timeout=2",
        {"ssl_cert_reqs": ssl.CERT_OPTIONAL},
    )


def test_normalize_celery_redis_url_defaults_unknown_tls_mode_to_required():
    assert normalize_celery_redis_url("rediss://:pw@redis:6379/0?ssl_cert_reqs=invalid") == (
        "rediss://:pw@redis:6379/0",
        {"ssl_cert_reqs": ssl.CERT_REQUIRED},
    )
