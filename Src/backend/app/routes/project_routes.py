"""Project CRUD routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain import models as m

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project(
    key: str,
    name: str,
    description: str,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("PO")),
) -> Dict[str, Any]:
    """Create a new project for the tenant."""

    tenant_id = user["tenant_id"]
    project = m.Project(key=key, name=name, description=description, tenant_id=tenant_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"project_id": project.id, "key": project.key}
