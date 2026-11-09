"""Real Celery/Redis worker probes, enabled only in the disposable CI environment."""

from __future__ import annotations

import importlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit

import pytest
from celery import Celery

from app.workers.celery_app import celery_app
from app.workers.worker_launcher import WORKER_ROLES

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or os.environ.get("RUN_CELERY_LIVE_TESTS") != "1",
    reason="Requires the disposable Linux CI Redis service and explicit opt-in",
)


def test_worker_registration_and_health_against_live_redis(monkeypatch):
    broker_url = os.environ.get("CELERY_LIVE_BROKER_URL") or "redis://127.0.0.1:6379/15"
    parsed_broker = urlsplit(broker_url)
    assert parsed_broker.scheme == "redis"
    assert parsed_broker.hostname in {"localhost", "127.0.0.1", "redis"}
    assert parsed_broker.path == "/15", "Live worker test must use disposable Redis DB 15"
    wrong_password_url = urlunsplit(
        parsed_broker._replace(
            netloc=f":wrong@{parsed_broker.hostname}:{parsed_broker.port or 6379}"
        )
    )
    # Celery gives CELERY_BROKER_URL precedence over its broker constructor
    # argument. Keep the controller on the same disposable DB as subprocesses.
    monkeypatch.setenv("REDIS_URL", broker_url)
    monkeypatch.setenv("CELERY_BROKER_URL", broker_url)
    controller = Celery("lorevia", broker=broker_url)
    for role_name, role in WORKER_ROLES.items():
        worker_env = os.environ.copy()
        worker_env.update(
            REDIS_URL=broker_url,
            CELERY_BROKER_URL=broker_url,
            CELERY_RESULT_BACKEND="",
            EXTRACTION_WORKER_CONCURRENCY="1",
        )
        worker_log = tempfile.TemporaryFile()
        worker = subprocess.Popen(
            [sys.executable, "-m", "app.workers.worker_launcher", role_name],
            env=worker_env,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        probe_env = None
        try:
            deadline = time.monotonic() + 60
            worker_name = None
            replies = {}
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    worker_log.seek(0)
                    raise AssertionError(
                        f"{role_name} exited during startup: "
                        f"{worker_log.read()[-4000:].decode(errors='replace')}"
                    )
                replies = controller.control.inspect(timeout=5).ping() or {}
                worker_name = next(
                    (name for name in replies if name.startswith(f"worker-{role_name}@")),
                    None,
                )
                if worker_name:
                    break
                time.sleep(0.2)
            if worker_name is None:
                worker_log.seek(0)
                raise AssertionError(
                    f"{role_name} did not respond to control ping; replies={replies!r}; "
                    f"{worker_log.read()[-4000:].decode(errors='replace')}"
                )

            for module_name in role.task_modules:
                importlib.import_module(module_name)
            expected_tasks = {
                task.name
                for task in celery_app.tasks.values()
                if task.__module__ in role.task_modules
            }
            registered = controller.control.inspect(
                destination=[worker_name], timeout=5
            ).registered()
            registered_names = {entry.split(" [", 1)[0] for entry in registered[worker_name]}
            assert expected_tasks <= registered_names

            probe_env = worker_env | {"HOSTNAME": worker_name.split("@", 1)[1]}
            command = [sys.executable, "-m", "app.workers.healthcheck", role_name]
            probe = subprocess.run(command, env=probe_env, capture_output=True, timeout=15)
            assert probe.returncode == 0, probe.stderr.decode(errors="replace")

            if role_name == "maintenance":
                spool_command = (
                    'python -c "import os,tempfile; '
                    "f=tempfile.TemporaryFile(dir=os.environ['MANUSCRIPT_EXPORT_SPOOL_DIRECTORY']); "
                    'f.close()" && python -m app.workers.healthcheck maintenance'
                )
                with tempfile.TemporaryDirectory() as spool_directory:
                    spool_env = probe_env | {"MANUSCRIPT_EXPORT_SPOOL_DIRECTORY": spool_directory}
                    assert (
                        subprocess.run(
                            ["sh", "-ec", spool_command],
                            env=spool_env,
                            capture_output=True,
                            timeout=15,
                        ).returncode
                        == 0
                    )
                    assert (
                        subprocess.run(
                            ["sh", "-ec", spool_command],
                            env=spool_env
                            | {"MANUSCRIPT_EXPORT_SPOOL_DIRECTORY": spool_directory + "/missing"},
                            capture_output=True,
                            timeout=15,
                        ).returncode
                        != 0
                    )

            if role_name == "extraction":
                wrong_identity = subprocess.run(
                    command,
                    env=probe_env | {"HOSTNAME": "wrong-worker-host"},
                    capture_output=True,
                    timeout=15,
                )
                assert wrong_identity.returncode == 1

                wrong_password = subprocess.run(
                    command,
                    env=probe_env | {"CELERY_BROKER_URL": wrong_password_url},
                    capture_output=True,
                    timeout=15,
                )
                assert wrong_password.returncode == 1

                os.kill(worker.pid, signal.SIGSTOP)
                try:
                    unresponsive = subprocess.run(
                        command, env=probe_env, capture_output=True, timeout=15
                    )
                    assert unresponsive.returncode == 1
                finally:
                    os.kill(worker.pid, signal.SIGCONT)
        finally:
            worker.terminate()
            try:
                worker.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(worker.pid, signal.SIGKILL)
                worker.wait(timeout=5)
            worker_log.close()
        if probe_env is not None:
            after_shutdown = subprocess.run(
                [sys.executable, "-m", "app.workers.healthcheck", role_name],
                env=probe_env,
                capture_output=True,
                timeout=15,
            )
            assert after_shutdown.returncode == 1
