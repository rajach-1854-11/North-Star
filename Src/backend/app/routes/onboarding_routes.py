"""Routes for onboarding plan generation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import OnboardingReq, OnboardingResp
from app.ports.onboarding import generate_plan

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/generate", response_model=OnboardingResp)
def generate(
    req: OnboardingReq,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO")),
) -> OnboardingResp:
    """Generate an onboarding plan for the requested developer."""

    return generate_plan(
        db,
        user_claims=user,
        developer_id=req.developer_id,
        project_id=req.project_id,
        autonomy=req.autonomy,
    )
