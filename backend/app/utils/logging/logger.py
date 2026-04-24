import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            **({"request_id": getattr(record, "request_id")} if getattr(record, "request_id", None) else {}),
            **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
        })


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JSONFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
