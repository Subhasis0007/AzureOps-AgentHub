from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_INCIDENT_ID: ContextVar[str | None] = ContextVar("incident_id", default=None)


class ACRGEJsonFormatter(jsonlogger.JsonFormatter):
    """Structured JSON formatter with consistent context fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)
        log_record.setdefault("module", record.module)
        log_record.setdefault("function", record.funcName)
        log_record.setdefault("line", record.lineno)
        request_id = _REQUEST_ID.get()
        incident_id = _INCIDENT_ID.get()
        if request_id:
            log_record.setdefault("request_id", request_id)
        if incident_id:
            log_record.setdefault("incident_id", incident_id)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _REQUEST_ID.get()
        record.incident_id = _INCIDENT_ID.get()
        return True


def set_log_context(*, request_id: str | None = None, incident_id: str | None = None) -> None:
    if request_id is not None:
        _REQUEST_ID.set(request_id)
    if incident_id is not None:
        _INCIDENT_ID.set(incident_id)


def clear_log_context() -> None:
    _REQUEST_ID.set(None)
    _INCIDENT_ID.set(None)


def configure_logging(log_level: str = "INFO", *, json_logs: bool = True) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())

    formatter: logging.Formatter
    if json_logs:
        formatter = ACRGEJsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s "
            "incident_id=%(incident_id)s %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
