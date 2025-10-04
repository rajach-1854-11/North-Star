from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as m

from worker.services.database import session_scope
from worker.services.idempotency import check_idempotency, record_idempotency
from worker.services.repository import resolve_repository_context
from app.instrumentation.metrics import increment
from worker.services.triage import record_triage
from worker.services.github_processor import finalize_workflow, _parse_datetime

logger = logging.getLogger(__name__)

DONE_STATES = {"done", "resolved", "closed"}


class JiraEventProcessor:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.event = payload.get("webhookEvent")
        self.delivery_key = payload.get("id") or payload.get("timestamp") or ""

    def process(self) -> None:
        with session_scope() as session:
            if check_idempotency(
                session,
                provider="jira",
                delivery_key=self.delivery_key,
            ):
                increment("jira.event", event=self.event, status="duplicate")
                logger.info(
                    "jira.event.duplicate",
                    extra={"delivery": self.delivery_key, "event": self.event},
                )
                return
            try:
                self._handle_issue_transition(session)
            except Exception as exc:  # noqa: BLE001
                increment("jira.event", event=self.event, status="error")
                record_idempotency(
                    session,
                    provider="jira",
                    delivery_key=self.delivery_key,
                    action=self.event,
                    entity="issue",
                    tenant_id=None,
                    status="error",
                    metadata={"error": str(exc)},
                )
                raise
            else:
                increment("jira.event", event=self.event, status="processed")
                record_idempotency(
                    session,
                    provider="jira",
                    delivery_key=self.delivery_key,
                    action=self.event,
                    entity="issue",
                    tenant_id=None,
                    status="processed",
                    metadata={"jira_key": self._jira_key()},
                )

    def _jira_key(self) -> str | None:
        issue = self.payload.get("issue")
        if isinstance(issue, dict):
            key = issue.get("key")
            if isinstance(key, str):
                return key
        return None

    def _handle_issue_transition(self, session: Session) -> None:
        issue = self.payload.get("issue")
        if not isinstance(issue, dict):
            return
        key = issue.get("key")
        if not isinstance(key, str):
            return

        status = issue.get("fields", {}).get("status", {}) if isinstance(issue.get("fields"), dict) else None
        status_name = None
        if isinstance(status, dict):
            status_name = status.get("name")
        if not status_name or status_name.lower() not in DONE_STATES:
            return

        stmt = select(m.AttributionWorkflow).where(m.AttributionWorkflow.jira_key == key)
        workflow = session.execute(stmt).scalar_one_or_none()
        if workflow is None:
            record_triage(
                session,
                provider="jira",
                delivery_key=self.delivery_key,
                reason="workflow_missing",
                payload=self.payload,
            )
            return

        workflow.jira_done_at = _parse_datetime(issue.get("fields", {}).get("resolutiondate")) or datetime.now(timezone.utc)

        repo_mapping = resolve_repository_context(
            session,
            provider="github",
            repo_full_name=workflow.repo_full_name,
        )
        if repo_mapping is None:
            record_triage(
                session,
                provider="jira",
                delivery_key=self.delivery_key,
                reason="repo_mapping_missing",
                payload={"workflow_id": workflow.id},
            )
            return

        finalize_workflow(
            session=session,
            workflow=workflow,
            mapping=repo_mapping,
            delivery_key=self.delivery_key,
        )
