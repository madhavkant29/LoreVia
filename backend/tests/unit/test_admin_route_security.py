import inspect

from fastapi.params import Depends

from app.api.deps.auth import require_admin_step_up
from app.api.v1.routes import admin_billing, admin_public


def _dependency_functions(endpoint) -> set[object]:
    dependencies: set[object] = set()
    for parameter in inspect.signature(endpoint).parameters.values():
        default = parameter.default
        if isinstance(default, Depends) and default.dependency is not None:
            dependencies.add(default.dependency)
    return dependencies


def test_sensitive_admin_mutations_require_step_up():
    assert require_admin_step_up in _dependency_functions(admin_public.review_public_share)
    assert require_admin_step_up in _dependency_functions(admin_billing.upsert_rate_limit_override)
