"""Redis-backed idempotency helpers used for webhook processing."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Protocol

import redis

from app.config import settings
from app.utils.hashing import hash_json

logger = logging.getLogger(__name__)


class SupportsSetNx(Protocol):
    """Protocol describing the redis-py interface required for idempotency."""

    def set(self, name: str, value: str, *, nx: bool, ex: int) -> bool:  # pragma: no cover - protocol
        """Set a key if it does not exist, expiring after *ex* seconds."""


if settings.redis_url:
    _redis_client: SupportsSetNx | None = redis.from_url(settings.redis_url)
else:
    logger.warning("Redis URL not configured; idempotency will operate in no-op mode")
    _redis_client = None


def acquire_once(key: str, ttl_seconds: int = 600) -> bool:
    """Return ``True`` if *key* is acquired for the first time within ``ttl_seconds``."""

    if not _redis_client:
        return True
    namespaced = f"idem:{key}"
    timestamp = str(int(time.time()))
    return bool(_redis_client.set(namespaced, timestamp, nx=True, ex=ttl_seconds))


def idempotent_call(key_factory: Callable[[], str], ttl_seconds: int = 600) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator applying :func:`acquire_once` using a lazily computed key."""

    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        def _inner(*args: Any, **kwargs: Any) -> Any:
            key = key_factory()
            if not acquire_once(key, ttl_seconds):
                return {"status": "duplicate_ignored", "idempotency_key": key}
            return fn(*args, **kwargs)

        return _inner

    return _wrap


def request_key(headers: dict[str, str], body_bytes: bytes | None = None, *, prefix: str = "req") -> str:
    """Generate a deterministic idempotency key from HTTP headers and body."""

    lowered = {key.lower(): value for key, value in headers.items()}

    def _first_present(*candidates: str) -> str | None:
        for candidate in candidates:
            direct = headers.get(candidate)
            if direct:
                return direct
            lower = lowered.get(candidate.lower())
            if lower:
                return lower
        return None

    idem = _first_present("X-Idempotency-Key", "Idempotency-Key")
    if idem:
        return f"{prefix}:{idem}"

    request_id = _first_present("X-Request-Id")
    if request_id:
        return f"{prefix}:{request_id}"

    delivery = _first_present("X-GitHub-Delivery")
    if delivery:
        return f"{prefix}:github:{delivery}"

    jira_delivery = _first_present("X-Atlassian-Webhook-Identifier", "X-Atlassian-Request-Id")
    if jira_delivery:
        return f"{prefix}:jira:{jira_delivery}"

    subset = {
        key: value
        for key, value in headers.items()
        if key.lower() in {"user-agent", "content-type"}
    }
    digest = hash_json(
        {
            "headers": subset,
            "body": (body_bytes.decode("utf-8", "ignore") if body_bytes else "")[:4096],
        },
        algo="sha256",
        namespace="idempotency",
    )
    return f"{prefix}:hash:{digest}"
