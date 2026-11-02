"""Structured JSON logs to stdout. Never pass complaint text, passwords, tokens or API keys to the logger."""
import json
import logging
import sys
from datetime import datetime, timezone

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
               "level": record.levelname, "logger": record.name, "event": record.getMessage()}
        out.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger("resolveai")
    if not any(getattr(h, "_resolveai", False) for h in root.handlers):  # idempotent across Streamlit reruns
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        h._resolveai = True
        root.addHandler(h)
        root.propagate = False
    root.setLevel(level)
    return root
