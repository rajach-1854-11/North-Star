"""Strategic staffing logic for ranking developers."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.talent_service import get_dev_skill_vector, get_project_required_skills, recency_boost
from app.domain import models as m
from app.ports.talent_graph import project_skill_gap


def cosine_dict(lhs: Dict[str, float], rhs: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors represented as dicts."""

    if not lhs or not rhs:
        return 0.0
    intersection = set(lhs).intersection(rhs)
    if not intersection:
        return 0.0
    numerator = sum(lhs[key] * rhs[key] for key in intersection)
    denominator = math.sqrt(sum(value * value for value in lhs.values())) * math.sqrt(
        sum(value * value for value in rhs.values())
    )
    return numerator / denominator if denominator > 0 else 0.0


def _ensure_aware(timestamp: datetime | None) -> datetime | None:
    if timestamp is None:
        return None
    return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)


def rank_candidates(db: Session, tenant_id: str, project: m.Project) -> List[Dict[str, object]]:
    """Return ranked candidate dictionaries for the requested project."""

    developers = db.query(m.Developer).filter(m.Developer.tenant_id == tenant_id).all()
    requirements = get_project_required_skills(db, project.id)

    requirement_paths = list(requirements.keys())
    skill_labels: Dict[str, str] = {}
    if requirement_paths:
        rows = (
            db.query(m.Skill.path_cache, m.Skill.name)
            .filter(m.Skill.path_cache.in_(requirement_paths))
            .all()
        )
        skill_labels = {path: name for path, name in rows}

    results: List[Dict[str, object]] = []
    for developer in developers:
        vector = get_dev_skill_vector(db, developer.id)
        project_similarity = cosine_dict(vector, requirements)

        requirement_total = sum(requirements.values()) or 1.0
        proven = sum(min(vector.get(path, 0.0), weight) for path, weight in requirements.items()) / requirement_total

        paths = list(requirements.keys())
        last_seen = None
        if paths:
            stmt = (
                select(func.max(m.DeveloperSkill.last_seen_at))
                .join(m.Skill, m.Skill.id == m.DeveloperSkill.skill_id)
                .where(m.DeveloperSkill.developer_id == developer.id)
                .where(m.Skill.path_cache.in_(paths))
            )
            last_seen = db.execute(stmt).scalar()
        recency = recency_boost(_ensure_aware(last_seen if isinstance(last_seen, datetime) else None))

        availability = 0.8
        fit = 0.40 * project_similarity + 0.30 * proven + 0.20 * recency + 0.10 * availability

        gaps = project_skill_gap(db, developer_id=developer.id, project_id=project.id)
        gap_entries: List[Dict[str, object]] = []
        for index, (path, gap) in enumerate(gaps[:3]):
            display = skill_labels.get(path)
            if not display and path:
                display = path.split('.')[-1]
            gap_entries.append(
                {
                    "rank": index + 1,
                    "path": path,
                    "name": display or path,
                    "gap": round(gap, 2),
                }
            )

        gap_lines = [
            f"Gap #{entry['rank']}: {entry['name']} (Δ={entry['gap']:.2f})"
            for entry in gap_entries
        ]

        results.append(
            {
                "developer_id": developer.id,
                "fit": round(fit, 4),
                "factors": {
                    "project_similarity": round(project_similarity, 3),
                    "proven_skill": round(proven, 3),
                    "recency": round(recency, 3),
                    "availability": round(availability, 3),
                },
                "availability": {"earliest_start": None, "percent_free": 0.5},
                "skill_gaps": gap_entries,
                "explanations": [
                    "Project similarity is cosine over hierarchical skill paths.",
                    "Proven skill coverage is overlap against required weights.",
                    "Recency uses exponential decay with 90-day half-life.",
                    *gap_lines,
                ],
            }
        )

    results.sort(key=lambda candidate: candidate["fit"], reverse=True)
    return results
