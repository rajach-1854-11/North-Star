"""SQLAlchemy ORM models for the North Star domain."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Tenant(Base):
    """Tenant metadata for multi-tenant isolation."""

    __tablename__ = "tenant"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class User(Base):
    """Platform user with authentication credentials."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False)


class Project(Base):
    """Project requiring staffing and onboarding."""

    __tablename__ = "project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False)


class Developer(Base):
    """Developer profile linked to a platform user."""

    __tablename__ = "developer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False)


class Assignment(Base):
    """Join table tracking developers assigned to projects."""

    __tablename__ = "assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(ForeignKey("developer.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")

    __table_args__ = (UniqueConstraint("developer_id", "project_id", name="uq_dev_proj"),)


class Skill(Base):
    """Hierarchical skill taxonomy nodes."""

    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("skill.id"), nullable=True)
    path_cache: Mapped[str] = mapped_column(String, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    parent = relationship("Skill", remote_side=[id])

    __table_args__ = (UniqueConstraint("path_cache", name="uq_skill_path"),)


class ProjectSkill(Base):
    """Target skills required for a project."""

    __tablename__ = "project_skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.id"), index=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (UniqueConstraint("project_id", "skill_id", name="uq_proj_skill"),)


class DeveloperSkill(Base):
    """Skills extracted for developers along with scores and confidence."""

    __tablename__ = "developer_skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(ForeignKey("developer.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    evidence_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("developer_id", "skill_id", name="uq_dev_skill"),
        Index("idx_devskill_dev_skill", "developer_id", "skill_id"),
    )


class DeveloperIdentity(Base):
    """External identity bindings for developers (e.g., GitHub)."""

    __tablename__ = "developer_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(ForeignKey("developer.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_login: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    email_lower: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_login", name="uq_identity_provider_login"),
        UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_user"),
        UniqueConstraint("provider", "email_lower", name="uq_identity_provider_email"),
        Index("idx_identity_provider_login", "provider", "provider_login"),
    )

    # NOTE: the column is named "metadata" in the database; we expose it to Python as
    # "metadata_json" to avoid clashing with SQLAlchemy's reserved Declarative attribute.


class RepositoryMapping(Base):
    """Repository-to-tenant/project mapping for contextual attribution."""

    __tablename__ = "repository_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="github")
    repo_full_name: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("provider", "repo_full_name", name="uq_repo_provider_fullname"),
        Index("idx_repo_provider_fullname", "provider", "repo_full_name"),
    )

    # See DeveloperIdentity for naming notes on the metadata column.


class IntegrationEventLog(Base):
    """Idempotency ledger for processed integration events."""

    __tablename__ = "integration_event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    delivery_key: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str | None] = mapped_column(String, nullable=True)
    entity: Mapped[str | None] = mapped_column(String, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "delivery_key", name="uq_event_provider_delivery"),
        Index("idx_event_provider_delivery", "provider", "delivery_key"),
    )

    # See DeveloperIdentity for naming notes on the metadata column.


class AttributionWorkflow(Base):
    """Tracks correlation between GitHub PRs and Jira issues prior to skill attribution."""

    __tablename__ = "attribution_workflow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, default="github", nullable=False)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True, index=True)
    repo_full_name: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jira_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    developer_id: Mapped[int | None] = mapped_column(ForeignKey("developer.id"), nullable=True, index=True)
    assertions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    pending_assertion_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    pr_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pr_merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jira_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_cycles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approvals_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    major_rework_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nit_comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    peer_review_credit: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    time_to_merge_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    last_payload_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "repo_full_name", "pr_number", name="uq_workflow_repo_pr"),
        UniqueConstraint("tenant_id", "jira_key", name="uq_workflow_jira"),
        Index("idx_workflow_repo_pr", "repo_full_name", "pr_number"),
    )


class PeerReviewCredit(Base):
    """Tracks peer review contributions to avoid double-counting bonuses."""

    __tablename__ = "peer_review_credit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    reviewer_developer_id: Mapped[int] = mapped_column(ForeignKey("developer.id"), nullable=False, index=True)
    repo_full_name: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_value: Mapped[float] = mapped_column(Float, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "reviewer_developer_id",
            "repo_full_name",
            "pr_number",
            name="uq_peer_credit_once_per_pr",
        ),
        Index("idx_peer_credit_window", "reviewer_developer_id", "window_end"),
    )


class AttributionTriage(Base):
    """Records unmatched identity or context events for manual review."""

    __tablename__ = "attribution_triage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    delivery_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_triage_provider_delivery", "provider", "delivery_key"),
    )


class AuditLog(Base):
    """Audit trail of authenticated requests."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String)
    args_hash: Mapped[str] = mapped_column(String)
    result_code: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String, index=True)
    trace_id: Mapped[str] = mapped_column(String, index=True)


class Event(Base):
    """Domain events emitted by integrations."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    developer_id: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ChatThread(Base):
    """Persistent conversation thread for user chat history."""

    __tablename__ = "chat_thread"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class ChatMessageLog(Base):
    """Individual chat turn stored within a thread."""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("chat_thread.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class ToolExecution(Base):
    """Record of planner tool invocations."""

    __tablename__ = "tool_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    tool: Mapped[str] = mapped_column(String)
    actor_user_id: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True)
    status: Mapped[str] = mapped_column(String)
    request_id: Mapped[str] = mapped_column(String)


class RouterStats(Base):
    """Bandit statistics for the hybrid router."""

    __tablename__ = "router_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    arm: Mapped[str] = mapped_column(String, nullable=False)
    pulls: Mapped[int] = mapped_column(Integer, default=0)
    reward_sum: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (UniqueConstraint("tenant_id", "arm", name="uq_router_stats_tenant_arm"),)


class TenantMapperWeights(Base):
    """Stored weights for contrastive A→B mapper per tenant."""

    __tablename__ = "tenant_mapper_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class ABMapEdge(Base):
    """Contrastive mapping edges between projects for ramp planning."""

    __tablename__ = "abmap_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    from_project: Mapped[str] = mapped_column(String, nullable=False)
    to_project: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        Index("idx_abmap_tenant_projects", "tenant_id", "from_project", "to_project"),
    )


class EvalRun(Base):
    """Historical evaluation runs capturing metric snapshots."""

    __tablename__ = "eval_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
