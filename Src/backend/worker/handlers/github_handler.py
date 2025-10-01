"""Background handler for GitHub webhook events."""

from __future__ import annotations

from typing import Any

from worker.handlers.skill_extractor import extract_skills_and_write


def handle_github_event(payload: dict[str, Any]) -> None:
    """Dispatch a GitHub webhook payload to the skill extractor."""

    event = payload.get("event", "unknown")
    body = payload.get("payload", {})
    extract_skills_and_write(event, body)
