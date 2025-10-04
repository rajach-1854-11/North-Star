"""Queue abstraction for background jobs with optional Redis backing."""

from __future__ import annotations

from typing import Any, Callable, Protocol

import redis
import rq

from app.config import settings


class QueueProtocol(Protocol):
    """Minimal interface required for enqueueing background jobs."""

    def enqueue(self, fn: Callable[..., Any], payload: dict[str, Any], *, job_timeout: int) -> Any:
        """Schedule *fn* with the given *payload*."""


def _build_queue() -> QueueProtocol:
    """Create a queue implementation based on configuration."""

    if settings.queue_mode == "direct" or not settings.redis_url:
        class _DirectQueue:
            def enqueue(self, fn: Callable[..., Any], payload: dict[str, Any], *, job_timeout: int) -> Any:  # noqa: D401
                """Execute jobs immediately in-process (development helper)."""

                return fn(payload)

        return _DirectQueue()

    redis_client = redis.from_url(settings.redis_url)
    return rq.Queue("events", connection=redis_client)


queue: QueueProtocol = _build_queue()


def enqueue_github_event(payload: dict[str, Any]) -> None:
    """Enqueue handling of a GitHub webhook payload."""

    from worker.handlers.github_handler import handle_github_event

    queue.enqueue(handle_github_event, payload, job_timeout=300)
