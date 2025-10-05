"""Assignment management ports with tenant enforcement."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import AssignmentListResp, AssignmentResp


def _ensure_same_tenant(obj: object | None, tenant_id: str, *, not_found: str) -> object:
    if obj is None or getattr(obj, "tenant_id", None) != tenant_id:
        raise HTTPException(status_code=404, detail=not_found)
    return obj


def _to_assignment_resp(assignment: m.Assignment) -> AssignmentResp:
    return AssignmentResp(
        id=assignment.id,
        developer_id=assignment.developer_id,
        project_id=assignment.project_id,
        role=assignment.role,
        status=assignment.status,
    )


def create_assignment(
    db: Session,
    *,
    tenant_id: str,
    developer_id: int,
    project_id: int,
    role: Optional[str],
    start_date: Optional[date],
) -> AssignmentResp:
    """Create a new assignment ensuring tenant coherence."""

    developer = _ensure_same_tenant(db.get(m.Developer, developer_id), tenant_id, not_found="Developer not found")
    project = _ensure_same_tenant(db.get(m.Project, project_id), tenant_id, not_found="Project not found")

    assignment = m.Assignment(
        developer_id=developer.id,
        project_id=project.id,
        role=role,
        start_date=start_date,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Assignment already exists for developer and project") from exc

    db.refresh(assignment)
    return _to_assignment_resp(assignment)


def update_assignment(
    db: Session,
    *,
    tenant_id: str,
    assignment_id: int,
    role: Optional[str],
    status: Optional[str],
    end_date: Optional[date],
) -> AssignmentResp:
    """Update fields on an assignment while enforcing tenant boundaries."""

    assignment = db.get(m.Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    developer = _ensure_same_tenant(db.get(m.Developer, assignment.developer_id), tenant_id, not_found="Developer not found")
    project = _ensure_same_tenant(db.get(m.Project, assignment.project_id), tenant_id, not_found="Project not found")
    _ = developer, project  # suppress unused warnings

    if role is not None:
        assignment.role = role
    if status is not None:
        assignment.status = status
    if end_date is not None:
        assignment.end_date = end_date

    db.commit()
    db.refresh(assignment)
    return _to_assignment_resp(assignment)


def list_assignments_for_project(db: Session, *, tenant_id: str, project_id: int) -> AssignmentListResp:
    """List assignments for the supplied project within the tenant."""

    project = _ensure_same_tenant(db.get(m.Project, project_id), tenant_id, not_found="Project not found")
    del project  # suppress unused

    rows: Iterable[m.Assignment] = (
        db.query(m.Assignment)
        .join(m.Developer, m.Developer.id == m.Assignment.developer_id)
        .filter(m.Assignment.project_id == project_id, m.Developer.tenant_id == tenant_id)
        .order_by(m.Assignment.id.asc())
        .all()
    )
    return AssignmentListResp(assignments=[_to_assignment_resp(row) for row in rows])
