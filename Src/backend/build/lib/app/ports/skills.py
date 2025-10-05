"""Skill-related port helpers."""

from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import SkillEntry, SkillProfileResp


def developer_profile(
    db: Session,
    *,
    user_claims: Dict[str, object],
    developer_id: int,
) -> SkillProfileResp:
    """Return the developer skill profile within tenant boundaries."""

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")
    role = user_claims.get("role")
    if role == "Dev":
        claimed_dev_id = user_claims.get("developer_id")
        if claimed_dev_id != developer_id:
            raise HTTPException(status_code=403, detail="Developers may only view their own profile")
    developer = db.get(m.Developer, developer_id)
    if not developer or developer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Developer not found")

    stmt = (
        select(m.Skill.path_cache, m.DeveloperSkill.score, m.DeveloperSkill.last_seen_at)
        .join(m.DeveloperSkill, m.Skill.id == m.DeveloperSkill.skill_id)
        .where(m.DeveloperSkill.developer_id == developer_id)
        .order_by(m.DeveloperSkill.score.desc())
        .limit(50)
    )
    rows: List[tuple[str, float, object]] = db.execute(stmt).all()
    skills = [
        SkillEntry(path=row[0], score=float(row[1]), last_seen=row[2] if row[2] else None)
        for row in rows
    ]
    return SkillProfileResp(developer_id=developer_id, skills=skills)