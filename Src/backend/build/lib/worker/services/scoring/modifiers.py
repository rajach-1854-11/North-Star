from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from app.config import settings


@dataclass
class ReviewSignal:
    changes_requested: bool
    approved: bool
    nit_comment: bool
    submitted_at: datetime


@dataclass
class ModifierContext:
    baseline: float
    review_signals: Iterable[ReviewSignal]
    review_cycles: int
    time_to_merge_seconds: int | None
    peer_credit_total: float
    major_rework_requested: bool
    approvals_count: int


def _time_to_merge_modifier(time_to_merge_seconds: int | None) -> float:
    if time_to_merge_seconds is None:
        return 0.0
    threshold_seconds = settings.time_to_merge_threshold_hours * 3600
    if time_to_merge_seconds <= threshold_seconds:
        return settings.time_to_merge_bonus
    else:
        return -settings.time_to_merge_penalty


def apply_modifiers(ctx: ModifierContext) -> float:
    if not settings.enable_review_signals:
        return ctx.baseline

    total = ctx.baseline
    if ctx.major_rework_requested:
        total -= settings.review_major_rework_penalty

    total -= settings.review_cycle_penalty * ctx.review_cycles
    nit_notes = sum(1 for signal in ctx.review_signals if signal.nit_comment)
    total -= settings.review_nit_penalty * nit_notes

    if ctx.approvals_count and ctx.review_cycles == 0:
        total += ctx.baseline * settings.review_first_review_multiplier
        total += settings.review_approval_bonus

    total += _time_to_merge_modifier(ctx.time_to_merge_seconds)
    total += ctx.peer_credit_total
    return total
