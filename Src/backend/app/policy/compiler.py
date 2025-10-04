from __future__ import annotations

from typing import Dict, Iterable, List

from app.config import settings
from app.domain.schemas import RetrieveReq

from .plan import PlanNode, PolicyPlan


def _normalise_projects(projects: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    normalised: List[str] = []
    for item in projects:
        key = (item or "").strip()
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            normalised.append(key)
    return normalised


def compile_policy(user_claims: Dict[str, object], req: RetrieveReq) -> PolicyPlan:
    tenant_id = str(user_claims.get("tenant_id") or settings.tenant_id)
    accessible = _normalise_projects(user_claims.get("accessible_projects", []))
    if "global" not in accessible:
        accessible.append("global")

    requested = _normalise_projects(req.targets or accessible)
    if not requested:
        requested = accessible

    allowed = [project for project in requested if project == "global" or project in accessible]
    if not allowed:
        allowed = ["global"]

    deny_from_policy = set(settings.policy_deny_projects)
    deny_from_claims = set(map(str, user_claims.get("deny_projects", [])))
    deny_projects = _normalise_projects(deny_from_policy | deny_from_claims)

    project_in = [project for project in allowed if project != "global"]
    project_filters: Dict[str, object] = {}
    if project_in:
        project_filters["in"] = project_in

    filter_meta = {"tenant_id": tenant_id}
    if project_filters:
        filter_meta["project_key"] = project_filters

    steps: List[PlanNode] = [
        PlanNode("AllowTenant", {"tenant_id": tenant_id}),
        PlanNode("AllowProjects", {"projects": allowed}),
    ]

    if deny_projects and settings.policy_enforcement == "strict":
        steps.append(PlanNode("DenyProjects", {"projects": deny_projects}))
        project_filters.setdefault("not_in", deny_projects)
        if project_filters:
            filter_meta["project_key"] = project_filters

    steps.extend(
        [
            PlanNode("FilterByMeta", {"filters": filter_meta}),
            PlanNode("DenseQuery", {"model": settings.bge_model}),
            PlanNode("SparseQuery", {"encoder": "sparse_hash"}),
            PlanNode(
                "HybridMerge",
                {
                    "lambda": settings.hybrid_lambda,
                    "strategy": req.strategy,
                },
            ),
            PlanNode("DedupByChunk", {}),
            PlanNode("LimitK", {"k": req.k}),
        ]
    )

    if settings.policy_proof_mode or settings.policy_enforcement == "strict":
        steps.append(PlanNode("Explain", {"enabled": True}))

    return PolicyPlan.from_steps(steps)
