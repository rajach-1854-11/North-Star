"""Helpers for computing talent-related metrics."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict

from sqlalchemy.orm import Session

from app.domain import models as m


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def recency_boost(last_seen_at: datetime | None, half_life_days: int = 90) -> float:
    """Return a decay score between 0.5 and 1.0 based on recency."""

    if last_seen_at is None:
        return 0.5
    days = (_utc_now() - last_seen_at).days
    return 0.5 + 0.5 * math.exp(-days / half_life_days)


def get_dev_skill_vector(db: Session, developer_id: int) -> Dict[str, float]:
    """Return a mapping of skill path to score for a developer."""

    rows = (
        db.query(m.DeveloperSkill, m.Skill)
        .join(m.Skill, m.DeveloperSkill.skill_id == m.Skill.id)
        .filter(m.DeveloperSkill.developer_id == developer_id)
        .all()
    )
    return {skill.path_cache: ds.score for ds, skill in rows}


def get_project_required_skills(db: Session, project_id: int) -> Dict[str, float]:
    """Return required skills for a project keyed by skill path."""

    rows = (
        db.query(m.ProjectSkill, m.Skill)
        .join(m.Skill, m.ProjectSkill.skill_id == m.Skill.id)
        .filter(m.ProjectSkill.project_id == project_id)
        .all()
    )
    return {skill.path_cache: ps.importance for ps, skill in rows}
