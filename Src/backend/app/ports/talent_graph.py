# FILE: northstar/backend/app/application/talent_graph.py
"""
Talent Graph utilities for North Star.

Purpose
-------
Provides hierarchical skill operations over the Postgres schema:
- skill(path_cache hierarchy)
- developer_skill (per-developer scores/evidence)
- project_skill (per-project required importance)

Key functions
-------------
- ensure_skill_path(db, path) -> skill_id
- rollup_developer_scores(db, developer_id) -> {path_cache: score}
- project_requirements(db, project_id) -> {path_cache: importance}
- compute_skill_gaps(dev_vec, req_vec) -> [(path_cache, gap)]
- project_skill_gap(db, developer_id, project_id) -> [(path_cache, gap)]
"""
from __future__ import annotations
from typing import List, Dict, Tuple
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.domain import models as m
from collections import defaultdict

def ensure_skill_path(db: Session, path: List[str]) -> int:
    """
    Ensure a hierarchical path exists in 'skill' table. Returns leaf skill_id.

    In this prototype, we store only a denormalized 'path_cache' string and depth.
    Parent linking is omitted for speed but can be added later by creating the full tree.
    """
    if not path:
        raise ValueError("empty path")
    path_cache = ">".join(path)
    sid = db.execute(select(m.Skill.id).where(m.Skill.path_cache == path_cache)).scalar()
    if sid:
        return sid
    depth = len(path)
    leaf_name = path[-1]
    # Upsert by path_cache
    db.execute(
        text(
            """
            INSERT INTO skill(name, parent_id, path_cache, depth)
            VALUES (:n, NULL, :p, :d)
            ON CONFLICT (path_cache) DO UPDATE
              SET name = EXCLUDED.name,
                  depth = EXCLUDED.depth
            """
        ),
        {"n": leaf_name, "p": path_cache, "d": depth},
    )
    sid = db.execute(select(m.Skill.id).where(m.Skill.path_cache == path_cache)).scalar()
    return sid

def rollup_developer_scores(db: Session, developer_id: int) -> Dict[str, float]:
    """
    Collapses developer_skill rows into a dict keyed by path_cache with max score.
    """
    rows = db.execute(
        text(
            """
            SELECT s.path_cache, ds.score
            FROM developer_skill ds
            JOIN skill s ON s.id = ds.skill_id
            WHERE ds.developer_id = :d
            """
        ),
        {"d": developer_id},
    ).all()
    agg: Dict[str, float] = defaultdict(float)
    for path, score in rows:
        agg[path] = max(agg[path], float(score))
    return dict(agg)

def project_requirements(db: Session, project_id: int) -> Dict[str, float]:
    """
    Returns a dict of required skills (path_cache -> importance weight).
    """
    rows = db.execute(
        text(
            """
            SELECT s.path_cache, ps.importance
            FROM project_skill ps
            JOIN skill s ON s.id = ps.skill_id
            WHERE ps.project_id = :p
            """
        ),
        {"p": project_id},
    ).all()
    return {path: float(importance) for path, importance in rows}

def compute_skill_gaps(dev_vec: Dict[str, float], req_vec: Dict[str, float]) -> List[Tuple[str, float]]:
    """
    For each required skill, compute gap = max(0, required - current).
    Returns a list sorted by largest gap first.
    """
    gaps: List[Tuple[str, float]] = []
    for path, req_weight in req_vec.items():
        cur = dev_vec.get(path, 0.0)
        gap = max(0.0, float(req_weight) - float(cur))
        if gap > 0:
            gaps.append((path, gap))
    gaps.sort(key=lambda x: x[1], reverse=True)
    return gaps

def project_skill_gap(db: Session, developer_id: int, project_id: int) -> List[Tuple[str, float]]:
    """
    Convenience wrapper: compute gaps for a developer against a project's required skills.
    """
    dev_vec = rollup_developer_scores(db, developer_id)
    req_vec = project_requirements(db, project_id)
    return compute_skill_gaps(dev_vec, req_vec)
