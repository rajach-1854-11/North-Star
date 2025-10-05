"""Project CRUD routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import ProjectResp
from app.ports.projects import create_project as create_project_port

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResp)
def create_project(
    key: str,
    name: str,
    description: str,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO")),
) -> ProjectResp:
    """Create a new project for the tenant."""

    tenant_id = user["tenant_id"]
    return create_project_port(
        db,
        tenant_id=tenant_id,
        key=key,
        name=name,
        description=description,
    )
