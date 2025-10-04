from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from datetime import timezone, datetime

from app.domain import models as m
from app.instrumentation.metrics import increment

logger = logging.getLogger(__name__)


def get_or_create_workflow(
    session: Session,
    *,
    tenant_id: str,
    repo_full_name: str,
    pr_number: int | None,
    jira_key: str | None,
) -> m.AttributionWorkflow:
    stmt = select(m.AttributionWorkflow).where(
        m.AttributionWorkflow.tenant_id == tenant_id,
        m.AttributionWorkflow.repo_full_name == repo_full_name,
    )
    if pr_number is not None and jira_key:
        stmt = stmt.where(
            or_(
                m.AttributionWorkflow.pr_number == pr_number,
                m.AttributionWorkflow.jira_key == jira_key,
            )
        )
    elif pr_number is not None:
        stmt = stmt.where(m.AttributionWorkflow.pr_number == pr_number)
    elif jira_key is not None:
        stmt = stmt.where(m.AttributionWorkflow.jira_key == jira_key)

    workflow = session.execute(stmt).scalar_one_or_none()
    if workflow is None:
        workflow = m.AttributionWorkflow(
            tenant_id=tenant_id,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            jira_key=jira_key,
        )
        session.add(workflow)
        session.flush()
        increment("workflow.lifecycle", action="created", tenant_id=tenant_id)
    else:
        if pr_number is not None and workflow.pr_number != pr_number:
            workflow.pr_number = pr_number
        if jira_key and workflow.jira_key != jira_key:
            workflow.jira_key = jira_key
        increment("workflow.lifecycle", action="reused", tenant_id=tenant_id)
    return workflow


def assign_assertions(workflow: m.AttributionWorkflow, assertions: Iterable[dict[str, object]]) -> None:
    workflow.assertions = list(assertions)


def append_evidence(workflow: m.AttributionWorkflow, key: str, value: object) -> None:
    evidence = dict(workflow.evidence or {})
    evidence[key] = value
    workflow.evidence = evidence


def mark_baseline_applied(workflow: m.AttributionWorkflow, delta: float) -> None:
    workflow.baseline_applied_at = datetime.now(timezone.utc)
    workflow.baseline_delta = delta
