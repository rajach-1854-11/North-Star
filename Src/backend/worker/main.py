"""Entry-point for the background worker process."""

from __future__ import annotations

import logging

import redis
from rq import Connection, Queue, Worker

from app.config import settings

logger = logging.getLogger(__name__)


def main() -> None:
    """Run an RQ worker bound to the configured Redis instance."""

    if settings.queue_mode == "direct" or not settings.redis_url:
        logger.error("Queue mode 'direct' does not support the standalone worker")
        raise SystemExit(1)

    redis_conn = redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        worker = Worker([Queue(name) for name in ("events",)])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
