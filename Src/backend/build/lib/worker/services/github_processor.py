from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.domain import models as m
from app.instrumentation.metrics import increment, observe
from app.services import compute_skill_delta

from worker.handlers import skill_extractor
from worker.services.autoprovision import provision_developer
from worker.services.database import session_scope
from worker.services.idempotency import check_idempotency, record_idempotency
from worker.services.identity import IdentityMatch, candidate_emails, normalize_email, resolve_identity
from worker.services.peer_credit import record_peer_credit
from worker.services.repository import resolve_repository_context
from worker.services.scoring.modifiers import ReviewSignal
from worker.services.triage import record_triage
from worker.services.workflow import (
    append_evidence,
    assign_assertions,
    get_or_create_workflow,
    mark_baseline_applied,
)


logger = logging.getLogger(__name__)

JIRA_KEY_RE = re.compile(r"[A-Z]{2,10}-\d+")


@dataclass
class EventEnvelope:
    provider: str
    delivery_key: str
    action: str | None
    entity: str | None
    payload: dict[str, Any]


class GitHubEventProcessor:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.event = payload.get("event", "unknown")
        self.body = payload.get("payload", {}) or {}
        self.provider = "github"
        self.delivery_key = payload.get("delivery", self.body.get("delivery")) or self.body.get("delivery_guid") or ""

    def process(self) -> None:
        with session_scope() as session:
            if not self.delivery_key:
                self.delivery_key = self._build_delivery_id()
            if check_idempotency(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
            ):
                logger.info(
                    "github.event.duplicate",
                    extra={"delivery": self.delivery_key, "event": self.event},
                )
                return

            dispatch_map = {
                "push": self._handle_push,
                "pull_request": self._handle_pull_request,
                "pull_request_review": self._handle_pull_request_review,
                "pull_request_review_comment": self._handle_pull_request_review_comment,
            }

            handler = dispatch_map.get(self.event)
            status = "skipped" if handler is None else "processed"
            increment("github.event", event=self.event, status="received")

            try:
                if handler is not None:
                    handler(session)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "github.event.error",
                    extra={"delivery": self.delivery_key, "event": self.event},
                )
                increment("github.event", event=self.event, status="error")
                record_idempotency(
                    session,
                    provider=self.provider,
                    delivery_key=self.delivery_key,
                    action=self.event,
                    entity=None,
                    tenant_id=None,
                    status="error",
                    metadata={"error": str(exc)},
                )
                raise
            else:
                if handler is not None:
                    increment("github.event", event=self.event, status="processed")
                record_idempotency(
                    session,
                    provider=self.provider,
                    delivery_key=self.delivery_key,
                    action=self.event,
                    entity=None,
                    tenant_id=self.body.get("tenant_id"),
                    status=status,
                    metadata={"repo": self._repo_full_name()},
                )

    def _build_delivery_id(self) -> str:
        guid = self.body.get("delivery_guid")
        if isinstance(guid, str) and guid:
            return guid
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"{self.event}:{timestamp}"

    def _repo_full_name(self) -> str | None:
        repo = self.body.get("repository")
        if isinstance(repo, dict):
            full_name = repo.get("full_name")
            if isinstance(full_name, str):
                return full_name
        return None

    def _detect_jira_key(self, pr: dict[str, Any]) -> str | None:
        title = pr.get("title")
        head_ref = pr.get("head", {}).get("ref") if isinstance(pr.get("head"), dict) else None
        body = pr.get("body")
        for candidate in (title, head_ref, body):
            if isinstance(candidate, str):
                match = JIRA_KEY_RE.search(candidate)
                if match:
                    return match.group(0)
        return None

    def _resolve_context(
        self,
        session: Session,
        *,
        identity_payload: dict[str, Any],
    ) -> tuple[Optional[IdentityMatch], Optional[m.RepositoryMapping]]:
        identity = resolve_identity(session, provider=self.provider, payload=identity_payload)
        repo_full_name = self._repo_full_name()
        mapping = None
        if repo_full_name:
            mapping = resolve_repository_context(
                session,
                provider=self.provider,
                repo_full_name=repo_full_name,
            )
        if identity is None and mapping is not None and settings.auto_provision_dev_from_gh:
            emails = list(candidate_emails(identity_payload))
            email = emails[0] if emails else None
            login_value = _extract_login(identity_payload)
            provisioned = provision_developer(
                session,
                tenant_id=mapping.tenant_id,
                login=login_value,
                email=email,
            )
            if provisioned:
                identity = IdentityMatch(
                    developer_id=provisioned.developer_id,
                    tenant_id=provisioned.tenant_id,
                    source="autoprovision",
                )
        increment(
            "github.repo_context",
            status="resolved" if mapping is not None else "missing",
            delivery=self.delivery_key,
            repo=self._repo_full_name(),
        )
        increment(
            "github.identity",
            status="matched" if identity is not None else "missing",
            source=(identity.source if identity else None),
            delivery=self.delivery_key,
        )
        logger.info(
            "github.context.resolve",
            extra={
                "delivery": self.delivery_key,
                "repo": self._repo_full_name(),
                "tenant_id": getattr(mapping, "tenant_id", None),
                "project_id": getattr(mapping, "project_id", None),
                "developer_id": getattr(identity, "developer_id", None),
                "identity_source": getattr(identity, "source", None),
            },
        )
        return identity, mapping

    def _handle_push(self, session: Session) -> None:
        repo_full_name = self._repo_full_name()
        identity, mapping = self._resolve_context(session, identity_payload=self.body)
        if mapping is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_repo_mapping",
                payload=self.body,
            )
            return

        if identity is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_identity",
                payload=self.body,
            )
            return

        jira_keys = self._extract_jira_keys_from_commits() or [None]
        pr_number = self.body.get("head_commit", {}).get("pr_number")
        for key in jira_keys:
            workflow = get_or_create_workflow(
                session,
                tenant_id=mapping.tenant_id,
                repo_full_name=repo_full_name or "unknown",
                pr_number=pr_number,
                jira_key=key,
            )
            workflow.developer_id = identity.developer_id
            append_evidence(workflow, f"push:{self.delivery_key}", self.body)
            assertions = skill_extractor.generate_skill_assertions(self.event, self.body)
            if assertions:
                assign_assertions(workflow, assertions)

    def _extract_jira_keys_from_commits(self) -> list[str]:
        commits = self.body.get("commits", [])
        keys: list[str] = []
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            message = commit.get("message")
            if isinstance(message, str):
                keys.extend(JIRA_KEY_RE.findall(message))
        head_message = self.body.get("head_commit", {}).get("message")
        if isinstance(head_message, str):
            keys.extend(JIRA_KEY_RE.findall(head_message))
        return list(dict.fromkeys(keys))

    def _handle_pull_request(self, session: Session) -> None:
        pr = self.body.get("pull_request", {})
        if not isinstance(pr, dict):
            return
        repo_full_name = self._repo_full_name()
        identity_payload = {
            "sender": self.body.get("sender"),
            "user": pr.get("user"),
        }
        identity, mapping = self._resolve_context(session, identity_payload=identity_payload)

        if mapping is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_repo_mapping",
                payload=self.body,
            )
            return

        pr_number = pr.get("number")
        jira_key = self._detect_jira_key(pr)
        if identity is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_identity",
                payload=self.body,
            )
            return
        workflow = get_or_create_workflow(
            session,
            tenant_id=mapping.tenant_id,
            repo_full_name=repo_full_name or "unknown",
            pr_number=pr_number,
            jira_key=jira_key,
        )
        workflow.developer_id = identity.developer_id
        workflow.project_id = mapping.project_id
        workflow.pr_created_at = _parse_datetime(pr.get("created_at"))
        if pr.get("merged_at"):
            workflow.pr_merged_at = _parse_datetime(pr.get("merged_at"))
        workflow.last_payload_snapshot = self.body
        if jira_key:
            workflow.jira_key = jira_key
        append_evidence(workflow, f"pr:{self.delivery_key}", self.body)
        assertions = skill_extractor.generate_skill_assertions(self.event, self.body)
        if assertions:
            assign_assertions(workflow, assertions)
        if pr.get("merged"):
            workflow.pr_merged_at = _parse_datetime(pr.get("merged_at")) or datetime.now(timezone.utc)
            self._attempt_finalize(session, workflow, mapping)

    def _handle_pull_request_review(self, session: Session) -> None:
        review = self.body.get("review", {})
        pr = self.body.get("pull_request", {})
        repo_full_name = self._repo_full_name()
        if not isinstance(pr, dict) or not isinstance(review, dict):
            return
        identity_payload = {
            "sender": self.body.get("sender"),
            "user": review.get("user"),
        }
        identity, mapping = self._resolve_context(session, identity_payload=identity_payload)
        if mapping is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_repo_mapping",
                payload=self.body,
            )
            return
        workflow = get_or_create_workflow(
            session,
            tenant_id=mapping.tenant_id,
            repo_full_name=repo_full_name or "unknown",
            pr_number=pr.get("number"),
            jira_key=self._detect_jira_key(pr),
        )
        append_evidence(workflow, f"review:{self.delivery_key}", review)
        state = review.get("state", "").lower()
        if state == "approved":
            workflow.approvals_count += 1
        elif state == "changes_requested":
            workflow.review_cycles += 1
            workflow.major_rework_requested = True
        else:
            workflow.nit_comment_count += 1

        if identity and workflow.developer_id and identity.developer_id != workflow.developer_id:
            credit = record_peer_credit(
                session,
                tenant_id=mapping.tenant_id,
                reviewer_developer_id=identity.developer_id,
                repo_full_name=repo_full_name or "unknown",
                pr_number=pr.get("number") or 0,
                submitted_at=_parse_datetime(review.get("submitted_at")) or datetime.now(timezone.utc),
                evidence={"review_id": review.get("id")},
            )
            if credit:
                credits = dict(workflow.peer_review_credit or {})
                key = str(identity.developer_id)
                credits[key] = credits.get(key, 0.0) + credit
                workflow.peer_review_credit = credits

        self._attempt_finalize(session, workflow, mapping)

    def _handle_pull_request_review_comment(self, session: Session) -> None:
        comment = self.body.get("comment", {})
        pr = self.body.get("pull_request", {})
        repo_full_name = self._repo_full_name()
        if not isinstance(comment, dict) or not isinstance(pr, dict):
            return
        identity_payload = {
            "sender": self.body.get("sender"),
            "user": comment.get("user"),
        }
        identity, mapping = self._resolve_context(session, identity_payload=identity_payload)

        if mapping is None:
            record_triage(
                session,
                provider=self.provider,
                delivery_key=self.delivery_key,
                reason="missing_repo_mapping",
                payload=self.body,
            )
            return

        workflow = get_or_create_workflow(
            session,
            tenant_id=mapping.tenant_id,
            repo_full_name=repo_full_name or "unknown",
            pr_number=pr.get("number"),
            jira_key=self._detect_jira_key(pr),
        )
        append_evidence(workflow, f"review_comment:{self.delivery_key}", comment)
        workflow.nit_comment_count += 1

        self._attempt_finalize(session, workflow, mapping)

    def _attempt_finalize(
        self,
        session: Session,
        workflow: m.AttributionWorkflow,
        mapping: m.RepositoryMapping,
    ) -> None:
        finalize_workflow(
            session=session,
            workflow=workflow,
            mapping=mapping,
            delivery_key=self.delivery_key,
        )


def finalize_workflow(
    *,
    session: Session,
    workflow: m.AttributionWorkflow,
    mapping: m.RepositoryMapping,
    delivery_key: str,
) -> None:
    if workflow.developer_id is None:
        record_triage(
            session,
            provider="github",
            delivery_key=delivery_key,
            reason="missing_developer_on_finalize",
            payload={"workflow_id": workflow.id},
        )
        return
    if workflow.pr_merged_at is None or workflow.jira_done_at is None:
        reason = "missing_pr_merge" if workflow.pr_merged_at is None else "missing_jira_done"
        logger.info(
            "skill.finalize.pending",
            extra={
                "workflow_id": workflow.id,
                "reason": reason,
                "delivery": delivery_key,
            },
        )
        return
    if workflow.baseline_applied_at is not None:
        logger.info(
            "skill.finalize.skipped",
            extra={
                "workflow_id": workflow.id,
                "reason": "already_applied",
                "delivery": delivery_key,
            },
        )
        return

    correlation = f"{mapping.repo_full_name}#" + (
        str(workflow.pr_number)
        if workflow.pr_number is not None
        else (workflow.jira_key or "n/a")
    )
    workflow.correlation_key = correlation

    review_signals = [
        ReviewSignal(
            changes_requested=workflow.major_rework_requested,
            approved=bool(workflow.approvals_count),
            nit_comment=workflow.nit_comment_count > 0,
            submitted_at=workflow.pr_merged_at,
        )
    ]
    peer_credit_total = (
        sum(workflow.peer_review_credit.values()) if workflow.peer_review_credit else 0.0
    )
    time_to_merge = _time_to_merge_seconds(workflow.pr_created_at, workflow.pr_merged_at)
    workflow.time_to_merge_seconds = time_to_merge
    if workflow.major_rework_requested:
        increment("skill.review_penalty", type="major_rework", delivery=delivery_key)
    if workflow.review_cycles > 1:
        increment(
            "skill.review_penalty",
            type="additional_cycle",
            cycles=workflow.review_cycles - 1,
            delivery=delivery_key,
        )
    if workflow.nit_comment_count > 0:
        increment("skill.review_penalty", type="nit_comment", delivery=delivery_key)
    if workflow.approvals_count and workflow.review_cycles == 0:
        increment("skill.review_bonus", type="first_review", delivery=delivery_key)
    if peer_credit_total > 0:
        increment("skill.review_bonus", type="peer_credit", delivery=delivery_key)
    result = compute_skill_delta(
        pr_created_at=workflow.pr_created_at,
        pr_merged_at=workflow.pr_merged_at,
        jira_done_at=workflow.jira_done_at,
        already_applied=False,
        review_signals=review_signals,
        review_cycles=workflow.review_cycles,
        approvals_count=workflow.approvals_count,
        major_rework_requested=workflow.major_rework_requested,
        time_to_merge_seconds=time_to_merge,
        peer_credit_total=peer_credit_total,
        baseline_default=settings.skill_baseline_increment,
    )
    if result.baseline_delta is None:
        return

    logger.info(
        "skill.modifiers.applied",
        extra={
            "workflow_id": workflow.id,
            "delivery": delivery_key,
            "baseline": result.baseline_delta,
            "final_delta": result.final_delta,
            "review_cycles": workflow.review_cycles,
            "approvals": workflow.approvals_count,
            "major_rework": workflow.major_rework_requested,
            "nit_comments": workflow.nit_comment_count,
            "peer_credit_total": peer_credit_total,
            "time_to_merge_seconds": time_to_merge,
        },
    )

    for assertion in workflow.assertions or []:
        skill_id = skill_extractor.ensure_skill(session, assertion.get("path", []))
        if skill_id is None:
            continue
        evidence = f"repo={mapping.repo_full_name},pr={workflow.pr_number},jira={workflow.jira_key}"
        skill_extractor.apply_skill_delta(
            session,
            developer_id=workflow.developer_id,
            skill_id=skill_id,
            project_id=mapping.project_id,
            delta=result.final_delta,
            confidence=float(
                assertion.get("confidence", settings.skill_confidence_default)
            ),
            evidence_ref=evidence,
        )

    mark_baseline_applied(workflow, result.final_delta)
    logger.info(
        "skill.finalized",
        extra={
            "workflow_id": workflow.id,
            "developer_id": workflow.developer_id,
            "tenant_id": workflow.tenant_id,
            "correlation": correlation,
            "delta": result.final_delta,
            "peer_credit": peer_credit_total,
            "time_to_merge_seconds": time_to_merge,
        },
    )
    increment("skill.finalized", tenant_id=workflow.tenant_id)
    observe(
        "skill.delta",
        value=result.final_delta,
        tenant_id=workflow.tenant_id,
        developer_id=workflow.developer_id,
    )
    if time_to_merge is not None:
        observe(
            "skill.time_to_merge",
            value=float(time_to_merge),
            tenant_id=workflow.tenant_id,
        )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _time_to_merge_seconds(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    delta = end - start
    return int(delta.total_seconds())


__all__ = ["GitHubEventProcessor", "finalize_workflow"]


def _extract_login(payload: dict[str, Any]) -> str | None:
    for key in ("sender", "user", "pusher", "author", "committer"):
        entity = payload.get(key)
        if isinstance(entity, dict):
            login = entity.get("login") or entity.get("username") or entity.get("name")
            if isinstance(login, str) and login.strip():
                return login.strip()
    return None
