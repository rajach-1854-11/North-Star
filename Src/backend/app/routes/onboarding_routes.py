"""Routes for onboarding plan generation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application.onboarding_service import generate_onboarding
from app.deps import get_db, require_role
from app.domain import models as m
from app.domain.schemas import OnboardingReq, OnboardingResp

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/generate", response_model=OnboardingResp)
def generate(
    req: OnboardingReq,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("PO")),
) -> OnboardingResp:
    """Generate an onboarding plan for the requested developer."""

    tenant_id = user["tenant_id"]
    project = db.get(m.Project, req.project_id)
    if not project or project.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")

    plan = generate_onboarding(
        db,
        user_claims=user,
        project_key=project.key,
        project_id=project.id,
        developer_id=req.developer_id,
        dev_name=f"Dev{req.developer_id}",
        autonomy=req.autonomy,
    )
    return OnboardingResp(plan=plan, audit_ref="AUD-001")
