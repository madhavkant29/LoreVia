import json
import logging
from datetime import UTC, datetime

from app.utils.request_context import get_request_id
from app.utils.logging.errors import scrub_sensitive_data

_STANDARD_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            record.request_id = request_id
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_sensitive_data(record.getMessage()),
            "module": record.module,
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exc"] = scrub_sensitive_data(self.formatException(record.exc_info))

        if record.stack_info:
            payload["stack"] = scrub_sensitive_data(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key in payload or key.startswith("_"):
                continue
            if value is not None:
                payload[key] = scrub_sensitive_data(value, key=key)

        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_lorevia_json_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestContextFilter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy.engine"):
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers.clear()
        named_logger.propagate = True
        named_logger.setLevel(level)

    logging.captureWarnings(True)
    root._lorevia_json_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger
