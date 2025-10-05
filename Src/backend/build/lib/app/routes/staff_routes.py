"""Staffing recommendation routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import StaffResp
from app.ports.staffing import recommend_staff as recommend_staff_port

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/recommend", response_model=StaffResp)
def recommend(
    project_id: int,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA")),
) -> StaffResp:
    """Return ranked developer candidates for the project."""

    return recommend_staff_port(db, user_claims=user, project_id=project_id)
