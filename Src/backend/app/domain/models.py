"""SQLAlchemy ORM models for the North Star domain."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
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
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    evidence_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("developer_id", "skill_id", name="uq_dev_skill"),
        Index("idx_devskill_dev_skill", "developer_id", "skill_id"),
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
