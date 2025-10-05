"""Project-related port functions enforcing tenancy and RBAC."""

from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import ProjectResp


def _to_project_resp(project: m.Project) -> ProjectResp:
    return ProjectResp(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
    )


def create_project(
    db: Session,
    *,
    tenant_id: str,
    key: str,
    name: str,
    description: Optional[str] = None,
) -> ProjectResp:
    """Create a new project scoped to *tenant_id* and return its schema."""

    project = m.Project(key=key, name=name, description=description, tenant_id=tenant_id)
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project key already exists") from exc

    db.refresh(project)
    return _to_project_resp(project)


def get_project_by_key(db: Session, *, tenant_id: str, key: str) -> ProjectResp:
    """Return a single project by key within the caller's tenant."""

    project = (
        db.query(m.Project)
        .filter(m.Project.key == key, m.Project.tenant_id == tenant_id)
        .one_or_none()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_project_resp(project)


def list_projects(db: Session, *, tenant_id: str) -> List[ProjectResp]:
    """Return all projects for the provided tenant ordered by key."""

    projects = (
        db.query(m.Project)
        .filter(m.Project.tenant_id == tenant_id)
        .order_by(m.Project.key.asc())
        .all()
    )
    return [_to_project_resp(project) for project in projects]