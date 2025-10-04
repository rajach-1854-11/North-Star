from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.config import settings


@dataclass
class BaselineContext:
    pr_created_at: datetime | None
    pr_merged_at: datetime | None
    jira_done_at: datetime | None
    already_applied: bool


def compute_baseline_delta(ctx: BaselineContext) -> float | None:
    if ctx.already_applied:
        return None
    if ctx.pr_merged_at is None or ctx.jira_done_at is None:
        return None
    if ctx.pr_merged_at < ctx.pr_created_at if ctx.pr_created_at else False:
        return None
    return settings.skill_baseline_increment
