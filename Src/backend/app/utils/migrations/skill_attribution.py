from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_skill_attribution_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    if "developer_skill" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE developer_skill SET last_seen_at = CURRENT_TIMESTAMP WHERE last_seen_at IS NULL"
                )
            )
            if engine.dialect.name.startswith("postgres"):
                conn.execute(
                    text(
                        "ALTER TABLE developer_skill ALTER COLUMN last_seen_at SET DEFAULT CURRENT_TIMESTAMP"
                    )
                )
                conn.execute(text("ALTER TABLE developer_skill ALTER COLUMN last_seen_at SET NOT NULL"))

    logger.info("skill_attribution_schema.ensure.complete")
