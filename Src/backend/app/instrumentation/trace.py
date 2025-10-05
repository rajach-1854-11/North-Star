from __future__ import annotations

import json
import random
import traceback
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Dict

from loguru import logger

from app.config import settings

_request_id_ctx: ContextVar[str | None] = ContextVar("trace_request_id", default=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _rand() -> float:
    return random.random()


def push_request_id(request_id: str) -> Token[str | None]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def _coerce(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _coerce(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce(item) for item in value]
    return str(value)


def _emit(payload: Dict[str, Any], *, force: bool = False) -> None:
    if not settings.trace_mode:
        return
    sample = max(0.0, min(float(settings.trace_sampling or 0.0), 1.0))
    if not force:
        if sample <= 0.0:
            return
        if sample < 1.0 and _rand() > sample:
            return
    payload.setdefault("ts", _now_iso())
    payload.setdefault("evt", "trace")
    payload.setdefault("request_id", get_request_id() or "")
    try:
        logger.info(
            json.dumps(payload, default=_coerce, ensure_ascii=False, separators=(",", ":"))
        )
    except TypeError:
        safe_payload = {key: _coerce(val) for key, val in payload.items()}
        logger.info(json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":")))


def tracepoint(name: str, **fields: Any) -> None:
    payload = {"name": name}
    payload.update({key: _coerce(value) for key, value in fields.items()})
    _emit(payload)


def trace_exception(name: str, exc: Exception, **fields: Any) -> None:
    data = {
        "name": name,
        "exception": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        data["exception"]["status_code"] = status_code
    stack = traceback.format_exception_only(exc.__class__, exc)
    data["exception"]["stack"] = [line.strip() for line in stack if line.strip()][:4]
    data.update({key: _coerce(value) for key, value in fields.items()})
    _emit(data, force=True)


@contextmanager
def request_id_context(request_id: str):
    token = push_request_id(request_id)
    try:
        yield
    finally:
        reset_request_id(token)
