from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from worker.services.scoring.baseline import BaselineContext, compute_baseline_delta
from worker.services.scoring.modifiers import ModifierContext, ReviewSignal, apply_modifiers


@dataclass
class ScoreComputationResult:
    baseline_delta: float | None
    final_delta: float


def compute_skill_delta(
    *,
    pr_created_at: datetime | None,
    pr_merged_at: datetime | None,
    jira_done_at: datetime | None,
    already_applied: bool,
    review_signals: Iterable[ReviewSignal],
    review_cycles: int,
    approvals_count: int,
    major_rework_requested: bool,
    time_to_merge_seconds: int | None,
    peer_credit_total: float,
    baseline_default: float,
) -> ScoreComputationResult:
    baseline = compute_baseline_delta(
        BaselineContext(
            pr_created_at=pr_created_at,
            pr_merged_at=pr_merged_at,
            jira_done_at=jira_done_at,
            already_applied=already_applied,
        )
    )
    if baseline is None:
        return ScoreComputationResult(baseline_delta=None, final_delta=0.0)

    modified = apply_modifiers(
        ModifierContext(
            baseline=baseline,
            review_signals=tuple(review_signals),
            review_cycles=review_cycles,
            time_to_merge_seconds=time_to_merge_seconds,
            peer_credit_total=peer_credit_total,
            major_rework_requested=major_rework_requested,
            approvals_count=approvals_count,
        )
    )
    return ScoreComputationResult(baseline_delta=baseline, final_delta=modified)
