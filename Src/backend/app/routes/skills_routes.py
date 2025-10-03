"""Skill profile routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.schemas import SkillProfileResp
from app.ports.skills import developer_profile

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/profile", response_model=SkillProfileResp)
def profile(
    developer_id: int,
    db: Session = Depends(get_db),
    _user: Dict[str, Any] = Depends(get_current_user),
) -> SkillProfileResp:
    """Return the skill profile for a developer."""

    return developer_profile(db, user_claims=_user, developer_id=developer_id)
