"""Helpers for patching split route modules in unit tests.

These helpers keep test monkeypatch propagation out of production route package
initializers. Tests that exercise package-level compatibility imports can patch
the package facade and the concrete child route modules explicitly.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

ROUTE_PATCH_MODULES: dict[str, tuple[str, ...]] = {
    "app.api.v1.routes.advisor": (
        "app.api.v1.routes.advisor.chat",
        "app.api.v1.routes.advisor.editing",
        "app.api.v1.routes.advisor.reports",
        "app.api.v1.routes.advisor.suggestions",
        "app.api.v1.routes.advisor.synopsis",
        "app.api.v1.routes.advisor.voice",
        "app.api.v1.routes.advisor.jobs",
    ),
    "app.api.v1.routes.books": (
        "app.api.v1.routes.books.characters",
        "app.api.v1.routes.books.character_aliases",
        "app.api.v1.routes.books.character_exports",
        "app.api.v1.routes.books.character_identity",
        "app.api.v1.routes.books.character_reprocess",
        "app.api.v1.routes.books.bootstrap",
        "app.api.v1.routes.books.core",
        "app.api.v1.routes.books.events",
        "app.api.v1.routes.books.exports",
        "app.api.v1.routes.books.imports",
        "app.api.v1.routes.books.intelligence",
        "app.api.v1.routes.books.lifecycle",
        "app.api.v1.routes.books.notes",
        "app.api.v1.routes.books.publish",
        "app.api.v1.routes.books.series",
        "app.services.character_alias_service",
        "app.services.character_identity_action_service",
        "app.services.book_upload_service",
        "app.services.character_listing_service",
        "app.services.character_merge_service",
        "app.services.character_mutation_service",
        "app.services.character_partition_service",
        "app.services.character_reprocess_service",
        "app.services.character_relationship_service",
        "app.services.character_review_action_service",
        "app.services.character_share_service",
        "app.services.manuscript_import_service",
        "app.services.manuscript_reprocess_service",
    ),
    "app.api.v1.routes.public": (
        "app.api.v1.routes.public_forum",
        "app.api.v1.routes.public_catalog",
        "app.api.v1.routes.public_shared",
    ),
    "app.api.v1.routes.reader": (
        "app.api.v1.routes.reader.chapters",
        "app.api.v1.routes.reader.core",
        "app.api.v1.routes.reader.events",
        "app.api.v1.routes.reader.graph",
        "app.api.v1.routes.reader.memory",
        "app.api.v1.routes.reader.progress",
        "app.api.v1.routes.reader.search",
        "app.api.v1.routes.reader.timeline",
    ),
}


def patch_route_dependency(
    monkeypatch: Any,
    route_package: ModuleType,
    name: str,
    value: Any,
    *,
    raising: bool = True,
) -> None:
    """Patch a dependency on a route package and concrete child modules.

    Production route packages no longer mutate child modules through custom
    ``ModuleType.__setattr__`` hooks. Tests that still call package-reexported
    endpoint functions use this helper while they are being moved to direct
    child-module imports.
    """

    patched = False
    for module in _route_modules(route_package):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value, raising=raising)
            patched = True
        if (
            route_package.__name__ == "app.api.v1.routes.advisor"
            and name == "advisor_suggestions"
            and hasattr(module, "_suggestions_advisor_suggestions")
        ):
            monkeypatch.setattr(
                module,
                "_suggestions_advisor_suggestions",
                value,
                raising=raising,
            )
            patched = True

    if not patched and raising:
        monkeypatch.setattr(route_package, name, value, raising=raising)
    elif not patched:
        monkeypatch.setattr(route_package, name, value, raising=False)


def _route_modules(route_package: ModuleType) -> list[ModuleType]:
    return [
        route_package,
        *[
            importlib.import_module(module_name)
            for module_name in ROUTE_PATCH_MODULES.get(route_package.__name__, ())
        ],
    ]
