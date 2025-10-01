"""Extract skills from structured planner output and persist to Postgres."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.adapters.cerebras_planner import chat_json
from app.config import settings

DATABASE_URL = (
    f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

engine: Engine = create_engine(DATABASE_URL)

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


def _write_skill(assertion: Dict[str, Any]) -> None:
    parts = assertion.get("path", [])
    if not parts:
        return
    path = ">".join(parts)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO skill(name, parent_id, path_cache, depth)
                VALUES(:name, NULL, :path, :depth)
                ON CONFLICT (path_cache) DO UPDATE SET
                    name = EXCLUDED.name,
                    depth = EXCLUDED.depth
                """
            ),
            {"name": parts[-1], "path": path, "depth": len(parts)},
        )
        skill_id = conn.execute(text("SELECT id FROM skill WHERE path_cache=:path"), {"path": path}).scalar()
        if skill_id is None:
            return
        conn.execute(
            text(
                """
                INSERT INTO developer_skill(developer_id, skill_id, score, confidence, evidence_ref)
                VALUES(:developer_id, :skill_id, :score, :confidence, :evidence)
                ON CONFLICT (developer_id, skill_id) DO UPDATE SET
                    score = greatest(developer_skill.score, EXCLUDED.score),
                    confidence = greatest(developer_skill.confidence, EXCLUDED.confidence),
                    last_seen_at = now()
                """
            ),
            {
                "developer_id": 1,
                "skill_id": skill_id,
                "score": assertion.get("confidence", 0.7),
                "confidence": assertion.get("confidence", 0.7),
                "evidence": "gh:event",
            },
        )


def extract_skills_and_write(event: str, payload: Dict[str, Any]) -> None:
    """Extract skills from a GitHub event payload and persist them."""

    prompt = _format_prompt(event, payload)
    output = chat_json(prompt, SCHEMA_HINT)
    for assertion in output.get("assertions", []):
        _write_skill(assertion)
