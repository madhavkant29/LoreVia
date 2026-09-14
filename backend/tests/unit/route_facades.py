"""Test-only lazy facades for split route packages.

Production route package initializers should only compose routers. Some legacy
unit tests still exercise endpoint functions through the old package-level
surface while they are being migrated to concrete child modules. These facades
keep that compatibility in tests instead of production imports.
"""

from __future__ import annotations

import importlib
from typing import Any

from tests.unit.route_patch_helpers import ROUTE_PATCH_MODULES


class RouteFacade:
    def __init__(
        self,
        package_name: str,
        *,
        support_modules: tuple[str, ...] = (),
        explicit: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "__name__", package_name)
        object.__setattr__(
            self, "_module_names", (*ROUTE_PATCH_MODULES.get(package_name, ()), *support_modules)
        )
        object.__setattr__(self, "_explicit", dict(explicit or {}))

    def __getattr__(self, name: str) -> Any:
        if name in self._explicit:
            value = self._explicit[name]
            setattr(self, name, value)
            return value
        for module_name in self._module_names:
            module = importlib.import_module(module_name)
            if hasattr(module, name):
                value = getattr(module, name)
                setattr(self, name, value)
                return value
        raise AttributeError(f"{self.__name__!r} test facade has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name.startswith("_") or name == "__name__":
            return
        for module_name in ROUTE_PATCH_MODULES.get(self.__name__, ()):
            module = importlib.import_module(module_name)
            if hasattr(module, name):
                setattr(module, name, value)
            if (
                self.__name__ == "app.api.v1.routes.advisor"
                and name == "advisor_suggestions"
                and hasattr(module, "_suggestions_advisor_suggestions")
            ):
                setattr(module, "_suggestions_advisor_suggestions", value)


books = RouteFacade(
    "app.api.v1.routes.books",
    support_modules=(
        "app.api.deps.subscription",
        "app.core.redis",
        "app.core.security",
        "app.services.editor_project_service",
        "app.services.manuscript_import_request_service",
        "app.services.pipeline_state_service",
        "app.utils.advisor_utils",
        "app.utils.billing_utils",
        "app.utils.books.chapter_versions",
        "app.utils.books.character_cards",
        "app.utils.books.collaboration_access",
        "app.utils.books.consistency_reports",
        "app.utils.books.imports",
        "app.utils.books.manuscript",
        "app.utils.books.normalization",
        "app.utils.books.notes",
        "app.utils.books.planning",
        "app.utils.books.scene_metadata",
        "app.utils.books.scene_ordering",
        "app.utils.books.scene_records",
        "app.utils.books.scene_sync",
        "app.utils.books.serialization",
        "app.utils.books.series_bible",
        "app.utils.books.story_health",
        "app.utils.books.vault",
        "app.utils.books.vault_relations",
        "app.utils.books.vault_storage",
        "app.utils.books.writer_workspace",
        "app.utils.characters.duplicates",
        "app.utils.characters.governance",
        "app.utils.characters.manual",
        "app.utils.characters.merging",
        "app.utils.characters.partitioning",
        "app.utils.characters.presentation",
        "app.utils.characters.review",
        "app.utils.characters.serialization",
        "app.utils.characters.text",
        "app.utils.reader_utils",
        "app.utils.tag_utils",
        "app.utils.user_utils",
        "app.workers.consumers.extraction_consumer",
        "app.workers.tasks.analysis_tasks",
        "app.workers.tasks.extraction_tasks",
        "app.engine.character.consolidator",
        "app.schemas.books",
        "app.utils.export_utils",
        "app.utils.llm_usage_utils",
        "app.utils.notification_utils",
        "app.utils.queue_utils",
    ),
    explicit={"storage": importlib.import_module("app.core.storage")},
)

advisor = RouteFacade(
    "app.api.v1.routes.advisor",
    support_modules=(
        "app.core.config",
        "app.core.redis",
        "app.core.storage",
        "app.engine.search.semantic",
        "app.services.advisor_jobs_service",
        "app.utils.advisor_utils",
        "app.utils.books.continuity",
        "app.utils.intelligence_utils",
        "app.utils.llm_usage_utils",
        "app.workers.tasks.intelligence_tasks",
    ),
)

reader = RouteFacade(
    "app.api.v1.routes.reader",
    support_modules=(
        "app.core.config",
        "app.core.redis",
        "app.core.security",
        "app.core.storage",
        "app.engine.analysis.recall",
        "app.engine.character.consolidator",
        "app.engine.search.semantic",
        "app.services.chapter_recovery_service",
        "app.services.summary_service",
        "app.utils.beta_read_utils",
        "app.utils.billing_utils",
        "app.utils.books.collaboration_access",
        "app.utils.characters.manual",
        "app.utils.characters.serialization",
        "app.utils.queue_utils",
        "app.utils.reader_utils",
        "app.utils.tag_utils",
    ),
)

public = RouteFacade(
    "app.api.v1.routes.public",
    support_modules=(
        "app.api.deps.auth",
        "app.api.v1.routes.public_catalog",
        "app.api.v1.routes.public_forum",
        "app.api.v1.routes.public_shared",
        "app.core.database",
        "app.core.redis",
        "app.core.storage",
        "app.models.book",
        "app.models.user",
        "app.schemas.public",
        "app.services.public_publish_service",
        "app.utils.books.manuscript",
        "app.utils.compliance.copyright_check",
        "app.utils.public.analytics",
        "app.utils.public.catalog",
        "app.utils.public.content",
        "app.utils.public.forum_engagement",
        "app.utils.public.forum_foundation",
        "app.utils.public.forum_posts",
        "app.utils.public.profiles",
        "app.utils.public.ranking_core",
        "app.utils.public.ranking_service",
        "app.utils.public.requests",
        "app.utils.public.serialization",
        "app.utils.public_utils",
    ),
)
