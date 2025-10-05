"""Read-only project routes."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import ProjectResp
from app.ports.projects import get_project_by_key, list_projects

router = APIRouter(prefix="/projects", tags=["projects-read"])


@router.get("", response_model=List[ProjectResp])
def list_tenant_projects(
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA", "Dev")),
) -> List[ProjectResp]:
    """Return all projects for the caller's tenant."""

    tenant_id = user["tenant_id"]
    return list_projects(db, tenant_id=tenant_id)


@router.get("/{key}", response_model=ProjectResp)
def get_project(
    key: str,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA", "Dev")),
) -> ProjectResp:
    """Return a single project referenced by key."""

    tenant_id = user["tenant_id"]
    return get_project_by_key(db, tenant_id=tenant_id, key=key)
