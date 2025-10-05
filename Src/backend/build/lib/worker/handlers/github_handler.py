"""Background handler for GitHub webhook events."""

from __future__ import annotations

import logging
from typing import Any

from worker.services.github_processor import GitHubEventProcessor

logger = logging.getLogger(__name__)


def handle_github_event(payload: dict[str, Any]) -> None:
    """Dispatch a GitHub webhook payload to the GitHub processor."""

    processor = GitHubEventProcessor(payload)
    logger.info(
        "github_handler.processing",
        extra={
            "event": processor.event,
            "delivery": processor.delivery_key,
            "repo": processor.body.get("repository", {}).get("full_name", "unknown"),
        },
    )
    processor.process()
