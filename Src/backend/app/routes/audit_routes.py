"""Audit log inspection routes."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit(
    actor: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return recent audit log entries filtered by actor when provided."""

    if actor:
        rows = db.execute(
            text(
                "select ts, actor_user_id, action, result_code, request_id from audit_log "
                "where actor_user_id=:actor order by ts desc limit :limit"
            ),
            {"actor": actor, "limit": limit},
        ).all()
    else:
        rows = db.execute(
            text(
                "select ts, actor_user_id, action, result_code, request_id from audit_log "
                "order by ts desc limit :limit"
            ),
            {"limit": limit},
        ).all()
    items = [
        {
            "ts": row[0].isoformat() if hasattr(row[0], "isoformat") else row[0],
            "actor": row[1],
            "action": row[2],
            "status": row[3],
            "request_id": row[4],
        }
        for row in rows
    ]
    return {"items": items}
