from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as m
from app.config import settings


def record_peer_credit(
    session: Session,
    *,
    tenant_id: str,
    reviewer_developer_id: int,
    repo_full_name: str,
    pr_number: int,
    submitted_at: datetime,
    evidence: dict[str, object],
) -> float:
    window_days = settings.review_peer_credit_window_days
    cap = settings.review_peer_credit_cap_per_window
    value = settings.review_peer_credit

    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)

    stmt = (
        select(m.PeerReviewCredit)
        .where(m.PeerReviewCredit.tenant_id == tenant_id)
        .where(m.PeerReviewCredit.reviewer_developer_id == reviewer_developer_id)
        .where(m.PeerReviewCredit.window_end >= window_start)
    )
    existing = session.execute(stmt).scalars().all()
    total_in_window = sum(item.credit_value for item in existing)

    if total_in_window >= value * cap:
        return 0.0

    credit = m.PeerReviewCredit(
        tenant_id=tenant_id,
        reviewer_developer_id=reviewer_developer_id,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        credit_value=value,
        window_start=window_start,
        window_end=window_start + timedelta(days=window_days),
        evidence=evidence,
    )
    session.add(credit)
    return value
