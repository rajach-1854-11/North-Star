from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from app.config import settings


@dataclass
class PeerReviewEvent:
    reviewer_developer_id: int
    repo_full_name: str
    pr_number: int
    submitted_at: datetime
    helpful: bool


def allocate_peer_review_credit(events: Iterable[PeerReviewEvent]) -> dict[int, float]:
    window_days = settings.review_peer_credit_window_days
    credit_value = settings.review_peer_credit
    cap_per_window = settings.review_peer_credit_cap_per_window

    accrued: dict[int, float] = defaultdict(float)
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    for event in events:
        if not event.helpful:
            continue
        if event.submitted_at < cutoff:
            continue
        developer_total = min(credit_value, credit_value * cap_per_window)
        accrued[event.reviewer_developer_id] += developer_total

    return dict(accrued)
