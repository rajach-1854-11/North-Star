"""Staffing recommendation routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import StaffResp
from app.domain import models as m
from app.ports.staffing import recommend_staff as recommend_staff_port

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/recommend", response_model=StaffResp)
def recommend(
    project_id: int | None = None,
    project_key: str | None = None,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA")),
) -> StaffResp:
    """Return ranked developer candidates for the project."""

    resolved_project_id = project_id

    if resolved_project_id is None:
        if not project_key:
            raise HTTPException(status_code=400, detail="Provide project_id or project_key")

        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Missing tenant context")

        project = (
            db.query(m.Project)
            .filter(m.Project.key == project_key, m.Project.tenant_id == tenant_id)
            .one_or_none()
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        resolved_project_id = project.id

    return recommend_staff_port(db, user_claims=user, project_id=resolved_project_id)
