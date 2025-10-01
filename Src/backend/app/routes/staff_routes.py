"""Staffing recommendation routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application.staffing_service import rank_candidates
from app.deps import get_db, require_role
from app.domain import models as m
from app.domain.schemas import StaffResp

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/recommend", response_model=StaffResp)
def recommend(
    project_id: int,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("PO")),
) -> StaffResp:
    """Return ranked developer candidates for the project."""

    tenant_id = user["tenant_id"]
    project = db.get(m.Project, project_id)
    if not project or project.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")
    candidates = rank_candidates(db, tenant_id, project)
    return StaffResp(project_id=project_id, candidates=candidates)
