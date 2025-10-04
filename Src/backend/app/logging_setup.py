"""Centralised logging configuration for the FastAPI application."""

from __future__ import annotations

import sys
import time
from typing import Any

from loguru import logger

from app.config import settings


def _inject_defaults(record: dict[str, Any]) -> None:
    """Guarantee required ``extra`` keys exist for the log formatter."""

    extra = record.setdefault("extra", {})
    extra.setdefault("req", "")
    extra.setdefault("route", "")
    extra.setdefault("tenant", "")


def setup_logging() -> None:
    """Configure Loguru with structured JSON-friendly output."""

    logger.remove()
    logger.configure(extra={"req": "", "route": "", "tenant": ""}, patcher=_inject_defaults)
    fmt = (
        "{time:YYYY-MM-DDTHH:mm:ss.SSS} | {level} | "
        "req={extra[req]} | route={extra[route]} | tenant={extra[tenant]} | msg={message}"
    )
    level = (settings.log_level or "INFO").upper()
    logger.add(
        sys.stdout,
        format=fmt,
        level=level,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )


class RequestLogger:
    """Utility to trace request lifecycle with consistent fields."""

    def __init__(self, logger_instance: Any) -> None:
        self.log = logger_instance

    def request_start(self, request_id: str, route: str, tenant: str) -> float:
        """Record the start of a request and return a monotonic timestamp."""

        self.log.bind(req=request_id, route=route, tenant=tenant).info("START")
        return time.perf_counter()

    def request_end(self, started_at: float, request_id: str, route: str, tenant: str, status: int) -> None:
        """Emit a completion log entry with duration in milliseconds."""

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        self.log.bind(req=request_id, route=route, tenant=tenant).info(
            f"END status={status} ms={elapsed_ms:.1f}"
        )
