import ssl
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.workers import healthcheck
from app.workers.worker_launcher import WORKER_ROLES


def test_healthcheck_import_stays_independent_of_application_and_task_modules():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.workers.healthcheck; "
            "print('\\n'.join(name for name in sys.modules "
            "if name == 'sqlalchemy' or name == 'app.core.database' "
            "or name.startswith('app.workers.tasks'))) ",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert result.stdout.strip() == ""


def test_healthcheck_roles_match_worker_launcher():
    assert healthcheck.WORKER_ROLES == set(WORKER_ROLES)


def test_healthcheck_broker_settings_uses_same_redis_fallback_as_celery_app():
    assert healthcheck.healthcheck_broker_settings(
        {"CELERY_BROKER_URL": "  ", "REDIS_URL": "redis://:pw@redis:6379/0"}
    ) == ("redis://:pw@redis:6379/0", {})


def test_healthcheck_broker_settings_rejects_missing_broker():
    with pytest.raises(ValueError, match="required"):
        healthcheck.healthcheck_broker_settings({})


def test_healthcheck_accepts_only_the_target_workers_pong(monkeypatch):
    monkeypatch.setenv("HOSTNAME", "container-123")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:pw@redis:6379/0")
    ping = Mock(return_value={"worker-extraction@container-123": {"ok": "pong"}})
    inspect = Mock(return_value=SimpleNamespace(ping=ping))
    app = SimpleNamespace(conf=SimpleNamespace(), control=SimpleNamespace(inspect=inspect))
    factory = Mock(return_value=app)
    monkeypatch.setattr(healthcheck, "Celery", factory)

    assert healthcheck.main(["extraction"]) == 0
    factory.assert_called_once_with("lorevia", broker="redis://:pw@redis:6379/0")
    inspect.assert_called_once_with(
        destination=["worker-extraction@container-123"],
        timeout=healthcheck.PING_TIMEOUT_SECONDS,
    )


def test_healthcheck_uses_tls_verification_for_rediss_broker(monkeypatch):
    monkeypatch.setenv("HOSTNAME", "container-123")
    monkeypatch.setenv("CELERY_BROKER_URL", "rediss://:pw@redis:6379/0")
    app = SimpleNamespace(
        conf=SimpleNamespace(broker_use_ssl=None),
        control=SimpleNamespace(
            inspect=lambda **kwargs: SimpleNamespace(
                ping=lambda: {"worker-extraction@container-123": {"ok": "pong"}}
            )
        ),
    )
    monkeypatch.setattr(healthcheck, "Celery", lambda *args, **kwargs: app)

    assert healthcheck.main(["extraction"]) == 0
    assert app.conf.broker_use_ssl == {"ssl_cert_reqs": ssl.CERT_REQUIRED}


@pytest.mark.parametrize(
    "reply",
    [
        None,
        {},
        {"worker-analysis@container-123": {"ok": "pong"}},
        {"worker-extraction@container-123": {"ok": "error"}},
    ],
)
def test_healthcheck_rejects_missing_wrong_or_failed_worker_reply(monkeypatch, reply):
    monkeypatch.setenv("HOSTNAME", "container-123")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:pw@redis:6379/0")
    app = SimpleNamespace(
        conf=SimpleNamespace(),
        control=SimpleNamespace(inspect=lambda **kwargs: SimpleNamespace(ping=lambda: reply)),
    )
    monkeypatch.setattr(healthcheck, "Celery", lambda *args, **kwargs: app)

    assert healthcheck.main(["extraction"]) == 1


def test_healthcheck_rejects_broker_failure(monkeypatch):
    monkeypatch.setenv("HOSTNAME", "container-123")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:pw@redis:6379/0")
    app = SimpleNamespace(
        conf=SimpleNamespace(),
        control=SimpleNamespace(inspect=Mock(side_effect=ConnectionError("broker unavailable"))),
    )
    monkeypatch.setattr(healthcheck, "Celery", lambda *args, **kwargs: app)

    assert healthcheck.main(["extraction"]) == 1


def test_healthcheck_rejects_unknown_role_or_missing_hostname(monkeypatch):
    monkeypatch.delenv("HOSTNAME", raising=False)
    assert healthcheck.main(["unknown"]) == 2
    assert healthcheck.main(["extraction"]) == 2
