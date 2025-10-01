"""Skill profile routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/profile")
def profile(
    developer_id: int,
    db: Session = Depends(get_db),
    _user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the skill profile for a developer."""

    rows = db.execute(
        text(
            """
            select s.path_cache, ds.score, ds.last_seen_at
            from developer_skill ds join skill s on s.id=ds.skill_id
            where ds.developer_id=:developer_id
            order by ds.score desc limit 50
            """
        ),
        {"developer_id": developer_id},
    ).all()
    skills = [
        {
            "path": row[0],
            "score": float(row[1]),
            "last_seen": row[2].isoformat() if row[2] else None,
        }
        for row in rows
    ]
    return {"developer_id": developer_id, "skills": skills}
