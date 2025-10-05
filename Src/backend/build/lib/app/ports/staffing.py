"""Staffing recommendation port functions."""

from __future__ import annotations

from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.application.staffing_service import rank_candidates
from app.domain import models as m
from app.domain.schemas import StaffCandidate, StaffResp


def recommend_staff(
    db: Session,
    *,
    user_claims: Dict[str, object],
    project_id: int,
) -> StaffResp:
    """Return staffing recommendations ensuring tenant access and schema conversion."""

    role = user_claims.get("role")
    if role not in {"Admin", "PO", "BA"}:
        raise HTTPException(status_code=403, detail="Only admins, product owners, or business analysts may request staffing recommendations")

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")
    project = db.get(m.Project, project_id)
    if not project or project.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")

    raw_candidates = rank_candidates(db, tenant_id, project)
    candidates = [StaffCandidate(**candidate) for candidate in raw_candidates]
    return StaffResp(project_id=project_id, candidates=candidates)