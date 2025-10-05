from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, List, Literal

NodeType = Literal[
    "AllowTenant",
    "AllowProjects",
    "DenyProjects",
    "DenseQuery",
    "SparseQuery",
    "HybridMerge",
    "FilterByMeta",
    "DedupByChunk",
    "LimitK",
    "Explain",
]


@dataclass(frozen=True)
class PlanNode:
    kind: NodeType
    args: Dict[str, object]


@dataclass(frozen=True)
class PolicyPlan:
    steps: List[PlanNode]
    plan_hash: str

    @staticmethod
    def from_steps(steps: List[PlanNode]) -> "PolicyPlan":
        payload = [f"{node.kind}:{sorted(node.args.items())}" for node in steps]
        digest = sha256("|".join(map(str, payload)).encode("utf-8")).hexdigest()
        return PolicyPlan(steps=list(steps), plan_hash=digest)
