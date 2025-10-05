from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as m


def check_idempotency(
    session: Session,
    *,
    provider: str,
    delivery_key: str,
) -> bool:
    stmt = (
        select(m.IntegrationEventLog.id)
        .where(m.IntegrationEventLog.provider == provider)
        .where(m.IntegrationEventLog.delivery_key == delivery_key)
    )
    return session.execute(stmt).first() is not None


def record_idempotency(
    session: Session,
    *,
    provider: str,
    delivery_key: str,
    action: str | None,
    entity: str | None,
    tenant_id: str | None,
    status: str,
    metadata: dict[str, object],
) -> None:
    log = m.IntegrationEventLog(
        provider=provider,
        delivery_key=delivery_key,
        action=action,
        entity=entity,
        tenant_id=tenant_id,
        status=status,
        metadata_json=metadata,
    )
    session.add(log)
