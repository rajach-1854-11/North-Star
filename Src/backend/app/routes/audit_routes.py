"""Audit log inspection routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import AuditResp
from app.ports.audit import list_audit_entries

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditResp)
def audit(
    actor: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA")),
) -> AuditResp:
    """Return recent audit log entries filtered by actor when provided."""

    return list_audit_entries(db, user_claims=_user, actor=actor, limit=limit)
