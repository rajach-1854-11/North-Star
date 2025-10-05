"""Audit log port enforcing tenant scope."""

from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import AuditEntry, AuditResp


def list_audit_entries(
    db: Session,
    *,
    user_claims: Dict[str, object],
    actor: int | None,
    limit: int,
) -> AuditResp:
    """Return recent audit entries for the caller's tenant."""

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")
    limit = max(1, min(limit, 200))

    query = db.query(m.AuditLog).filter(m.AuditLog.tenant_id == tenant_id)
    if actor is not None:
        query = query.filter(m.AuditLog.actor_user_id == actor)

    rows: List[m.AuditLog] = query.order_by(m.AuditLog.ts.desc()).limit(limit).all()
    items = [
        AuditEntry(
            ts=row.ts,
            actor=row.actor_user_id,
            action=row.action,
            status=row.result_code,
            request_id=row.request_id,
        )
        for row in rows
    ]
    return AuditResp(items=items)