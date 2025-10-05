from __future__ import annotations

import logging
from typing import Any

from worker.services.jira_processor import JiraEventProcessor

logger = logging.getLogger(__name__)


def handle_jira_event(payload: dict[str, Any]) -> None:
    processor = JiraEventProcessor(payload)
    logger.info(
        "jira_handler.processing",
        extra={"event": processor.event, "delivery": processor.delivery_key},
    )
    processor.process()
