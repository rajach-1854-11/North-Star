"""Entry-point for the background worker process."""

from __future__ import annotations

import logging
import os

import redis
from rq import Connection, Queue, Worker
from rq.worker import SimpleWorker
from rq.timeouts import TimerDeathPenalty

from app.config import settings

logger = logging.getLogger(__name__)


class WindowsSimpleWorker(SimpleWorker):
    death_penalty_class = TimerDeathPenalty


def main() -> None:
    """Run an RQ worker bound to the configured Redis instance."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

    if settings.queue_mode == "direct" or not settings.redis_url:
        logger.error("Queue mode 'direct' does not support the standalone worker")
        raise SystemExit(1)

    redis_conn = redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        queues = [Queue(name) for name in ("events",)]
        worker_cls = Worker if hasattr(os, "fork") else WindowsSimpleWorker
        worker = worker_cls(queues, connection=redis_conn)
        logger.info("Starting RQ worker", extra={"worker_class": worker_cls.__name__})
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
