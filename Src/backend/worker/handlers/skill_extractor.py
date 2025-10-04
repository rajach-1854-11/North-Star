"""Utilities for generating and persisting skill assertions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.cerebras_planner import chat_json
from app.config import settings
from app.domain import models as m

from worker.services.database import engine

SCHEMA_HINT = """{
 "assertions":[{"path":[str,...], "confidence":float, "evidence":str}]
}"""


def _format_prompt(event: str, payload: Dict[str, Any]) -> str:
    keys = ", ".join(sorted(payload.keys()))
    return (
        f"Event type: {event}\n"
        f"Payload keys: {keys}\n"
        "Extract hierarchical skills (path arrays), confidence (0..1), and short evidence."
    )


def generate_skill_assertions(event: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Call the planner to derive skill assertions without mutating the database."""

    prompt = _format_prompt(event, payload)
    output = chat_json(prompt, SCHEMA_HINT)
    assertions: List[Dict[str, Any]] = []
    for raw in output.get("assertions", []) or []:
        parts: Iterable[str] = [str(p).strip() for p in raw.get("path", []) if str(p).strip()]
        path = [p for p in parts if p]
        if not path:
            continue
        assertions.append(
            {
                "path": path,
                "confidence": float(raw.get("confidence", settings.skill_confidence_default)),
                "evidence": raw.get("evidence") or "gh:event",
            }
        )
    return assertions


def ensure_skill(session: Session, path: Iterable[str]) -> int | None:
    """Ensure a skill hierarchy path exists and return the leaf skill id."""

    parts = [str(p).strip() for p in path if str(p).strip()]
    if not parts:
        return None
    path_cache = ">".join(parts)
    depth = len(parts) - 1
    session.execute(
        text(
            """
            INSERT INTO skill(name, parent_id, path_cache, depth)
            VALUES(:name, NULL, :path, :depth)
            ON CONFLICT (path_cache) DO UPDATE SET
                name = EXCLUDED.name,
                depth = EXCLUDED.depth
            """
        ),
        {"name": parts[-1], "path": path_cache, "depth": depth},
    )
    skill_id = session.execute(
        text("SELECT id FROM skill WHERE path_cache=:path"), {"path": path_cache}
    ).scalar_one()
    return int(skill_id)


def apply_skill_delta(
    session: Session,
    *,
    developer_id: int,
    skill_id: int,
    project_id: int | None,
    delta: float,
    confidence: float,
    evidence_ref: str,
) -> None:
    """Apply a score delta to a developer skill, ensuring timestamps update."""

    seen_at = datetime.now(timezone.utc)

    session.execute(
        text(
            """
            INSERT INTO developer_skill(
                developer_id,
                skill_id,
                score,
                confidence,
                evidence_ref,
                project_id,
                last_seen_at
            )
            VALUES(
                :developer_id,
                :skill_id,
                :delta,
                :confidence,
                :evidence_ref,
                :project_id,
                :last_seen_at
            )
            ON CONFLICT (developer_id, skill_id) DO UPDATE SET
                score = developer_skill.score + EXCLUDED.score,
                confidence = MAX(developer_skill.confidence, EXCLUDED.confidence),
                evidence_ref = EXCLUDED.evidence_ref,
                project_id = COALESCE(EXCLUDED.project_id, developer_skill.project_id),
                last_seen_at = :last_seen_at
            """
        ),
        {
            "developer_id": developer_id,
            "skill_id": skill_id,
            "delta": delta,
            "confidence": confidence,
            "evidence_ref": evidence_ref[:255],
            "project_id": project_id,
            "last_seen_at": seen_at,
        },
    )


__all__ = [
    "generate_skill_assertions",
    "ensure_skill",
    "apply_skill_delta",
    "engine",
]
