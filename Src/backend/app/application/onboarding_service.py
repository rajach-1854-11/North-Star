"""Onboarding plan generation combining planner output with deterministic gaps."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.domain.schemas import OnboardingPlan
from app.ports.talent_graph import project_skill_gap
from loguru import logger


def _format_gap_bullets(gaps: List[tuple[str, float]]) -> str:
    """Return markdown bullet list of the top gaps."""
    return "\n".join(f"- {path} (gap {gap:.2f})" for path, gap in gaps[:5])


def generate_onboarding(
    db: Session,
    user_claims: Dict[str, object],
    project_key: str,
    project_id: int,
    developer_id: int,
    dev_name: str,
    autonomy: str,
) -> OnboardingPlan:
    """Create an onboarding plan by merging planner output with graph-derived gaps.

    NOTE: We import the planner lazily inside this function to avoid a circular
    import between app.ports.planner -> app.application.policy_bus -> app.application.*.
    """
    # Lazy import to break circular dependency
    from app.ports import planner as _planner

    gaps_algo = project_skill_gap(db, developer_id=developer_id, project_id=project_id)
    gap_bullets = _format_gap_bullets(gaps_algo)
    task = (
        f"Create a personalized onboarding plan for developer {dev_name} joining project {project_key}.\n"
        "Here are algorithmic skill gaps derived from our Talent Graph (use these as starting focus areas):\n"
        f"{gap_bullets if gap_bullets else '- No major gaps detected; focus on system differences and environment setup.'}\n\n"
        "First, run rag_search on project docs to identify 3-5 key differences and knowledge gaps, "
        "then create a Confluence page summarizing the onboarding with embedded evidence, "
        "and create a Jira epic for the 10-working-day onboarding tasks."
    )

    plan = _planner.create_plan(
        task_prompt=task,
        allowed_tools=["rag_search", "confluence_page", "jira_epic"],
    )
    exec_res = _planner.execute_plan(plan, user_claims=user_claims)
    if exec_res.get("output", {}).get("notes") == "fallback_heuristic_plan":
        logger.warning("Planner fallback engaged for onboarding; returning heuristic plan")
        return _fallback_onboarding_plan(dev_name, project_key, gaps_algo)
    output = exec_res.get("output", {})
    artifacts = exec_res.get("artifacts", {})

    llm_gaps = output.get("gaps") or []
    if not llm_gaps and gaps_algo:
        llm_gaps = [{"topic": path, "confidence": 0.8} for path, _gap in gaps_algo[:5]]

    return OnboardingPlan(
        summary=output.get("summary", "Onboarding plan"),
        gaps=llm_gaps,
        two_week_plan=output.get("two_week_plan", []),
        artifacts={
            "confluence": artifacts.get("step_2:confluence_page") or artifacts.get("confluence_page") or {},
            "jira_epic": artifacts.get("step_3:jira_epic") or artifacts.get("jira_epic") or {},
        },
    )


def _fallback_onboarding_plan(
    dev_name: str,
    project_key: str,
    gaps_algo: List[tuple[str, float]],
) -> OnboardingPlan:
    """Produce a deterministic onboarding plan when the planner is unavailable."""

    top_gaps = gaps_algo[:5]
    if not top_gaps:
        top_gaps = [("Project domain knowledge", 0.5)]

    gap_entries = [{"topic": path, "confidence": min(0.9, 0.6 + gap / 2)} for path, gap in top_gaps]

    tasks = []
    day = 1
    for path, gap in top_gaps[:3]:
        tasks.append({
            "day": day,
            "task": f"Deep dive into '{path}' with focus on closing gap ({gap:.2f}).",
        })
        day += 3

    tasks.extend(
        [
            {"day": max(day, 7), "task": "Shadow senior engineer and document environment setup."},
            {"day": max(day + 3, 10), "task": "Deliver a walkthrough or demo to confirm understanding."},
        ]
    )

    summary = (
        f"Self-guided onboarding plan for {dev_name} joining project {project_key}. "
        "Prioritize the highlighted gaps and pair with team members during the first two weeks."
    )

    return OnboardingPlan(
        summary=summary,
        gaps=gap_entries,
        two_week_plan=tasks,
        artifacts={
            "confluence": {
                "url": "Planner fallback engaged; create Confluence page manually.",
            },
            "jira_epic": {
                "url": "Planner fallback engaged; create Jira epic manually.",
            },
        },
        notice="Planner service unavailable; delivered heuristic onboarding plan. Please retry later.",
    )
