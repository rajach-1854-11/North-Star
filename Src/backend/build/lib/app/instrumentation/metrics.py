from __future__ import annotations

from loguru import logger


def increment(metric: str, **labels: object) -> None:
    logger.bind(metric=metric, **labels).info("metric.increment")


def observe(metric: str, value: float, **labels: object) -> None:
    logger.bind(metric=metric, value=value, **labels).info("metric.observe")
