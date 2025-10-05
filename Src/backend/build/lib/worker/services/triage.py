from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain import models as m


def record_triage(
    session: Session,
    *,
    provider: str,
    delivery_key: str | None,
    reason: str,
    payload: dict[str, Any],
) -> None:
    entry = m.AttributionTriage(
        provider=provider,
        delivery_key=delivery_key,
        reason=reason,
        payload=payload,
    )
    session.add(entry)
