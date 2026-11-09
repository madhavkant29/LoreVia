"""Check Celery's real loader in a fresh process for every worker role."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from app.workers.celery_app import celery_app
from app.workers.worker_launcher import WORKER_ROLES

TASK_DIRECTORY = Path(__file__).resolve().parents[2] / "app" / "workers" / "tasks"
REGISTRY_PROBE = """
import json
import sys
from app.workers.celery_app import celery_app
from app.workers.worker_launcher import WORKER_ROLES
celery_app.conf.include = WORKER_ROLES[sys.argv[1]].task_modules
celery_app.loader.import_default_modules()
print(json.dumps(sorted(name for name in celery_app.tasks if not name.startswith('celery.'))))
"""


def declared_tasks() -> dict[str, tuple[str, str]]:
    declarations = {}
    for path in TASK_DIRECTORY.glob("*_tasks.py"):
        module = f"app.workers.tasks.{path.stem}"
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name):
                    continue
                if (decorator.func.value.id, decorator.func.attr) != ("celery_app", "task"):
                    continue
                options = {keyword.arg: keyword.value for keyword in decorator.keywords}
                name = ast.literal_eval(options["name"])
                queue = ast.literal_eval(options["queue"])
                assert name not in declarations, f"Duplicate Celery task name: {name}"
                declarations[name] = (module, queue)
    return declarations


def registered_tasks_for_role(role_name: str) -> set[str]:
    result = subprocess.run(
        [sys.executable, "-c", REGISTRY_PROBE, role_name],
        cwd=TASK_DIRECTORY.parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return set(json.loads(result.stdout))


def test_every_declared_task_is_registered_by_a_worker_consuming_its_queue():
    declarations = declared_tasks()
    assert declarations
    registrations = {role: registered_tasks_for_role(role) for role in WORKER_ROLES}

    for task_name, (module, queue) in declarations.items():
        consumers = [
            role_name for role_name, role in WORKER_ROLES.items() if queue in role.queues.split(",")
        ]
        assert consumers, f"No worker consumes {queue} for {task_name}"
        for role_name in consumers:
            assert module in WORKER_ROLES[role_name].task_modules
            assert task_name in registrations[role_name], (task_name, role_name)

    assert "maintenance_tasks.repair_processing_books" in registrations["intelligence"]
    assert "intelligence_tasks.review_voice_chapter" in registrations["intelligence"]


def test_declared_tasks_keep_their_default_and_priority_queue_routes():
    declarations = declared_tasks()
    for module, _queue in set(declarations.values()):
        __import__(module)

    for task_name, (_module, queue) in declarations.items():
        task = celery_app.tasks[task_name]
        options = celery_app.amqp.router.route(task._get_exec_options(), task_name, (), {})
        assert options["queue"].name == queue

    for task_name, queue in (
        ("extraction_tasks.process_chapter", "extraction_priority"),
        ("analysis_tasks.analyse_chapter", "analysis_priority"),
    ):
        options = celery_app.amqp.router.route({"queue": queue}, task_name, (), {})
        assert options["queue"].name == queue


def test_every_beat_entry_is_registered_in_a_fresh_process():
    registered = registered_tasks_for_role("maintenance")
    assert {entry["task"] for entry in celery_app.conf.beat_schedule.values()} <= registered
