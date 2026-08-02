from __future__ import annotations

_TASK_ENQUEUE_ERROR_TYPES: list[type[BaseException]] = [
    RuntimeError,
    OSError,
    TimeoutError,
]

try:  # pragma: no cover - import availability follows Celery/Kombu installation.
    from celery.exceptions import CeleryError
except ImportError:  # pragma: no cover
    CeleryError = None  # type: ignore[assignment]

try:  # pragma: no cover - import availability follows Celery/Kombu installation.
    from kombu.exceptions import KombuError
except ImportError:  # pragma: no cover
    KombuError = None  # type: ignore[assignment]

if CeleryError is not None:
    _TASK_ENQUEUE_ERROR_TYPES.append(CeleryError)
if KombuError is not None:
    _TASK_ENQUEUE_ERROR_TYPES.append(KombuError)

TASK_ENQUEUE_ERRORS = tuple(_TASK_ENQUEUE_ERROR_TYPES)
