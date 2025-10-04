"""Background handler for GitHub webhook events."""

from __future__ import annotations

import logging
from typing import Any

from worker.handlers.skill_extractor import extract_skills_and_write


logger = logging.getLogger(__name__)


def handle_github_event(payload: dict[str, Any]) -> None:
    """Dispatch a GitHub webhook payload to the skill extractor."""

    event = payload.get("event", "unknown")
    body = payload.get("payload", {})
    repo = body.get("repository", {}).get("full_name", "unknown")
    logger.info("github_handler processing webhook", extra={"event": event, "repo": repo})
    extract_skills_and_write(event, body)
