"""Domain-level retrieval orchestration helpers."""

from __future__ import annotations

from typing import Sequence

from app.domain.schemas import RetrieveResp
from app.ports import retriever


def retrieve_context(
    query: str,
    tenant_id: str,
    targets: Sequence[str],
    k: int,
    lambda_w: float | None = None,
) -> RetrieveResp:
    """Run the configured retriever and normalise its response."""

    resolved_targets = list(targets) or ["global"]
    user_claims = {"tenant_id": tenant_id, "accessible_projects": resolved_targets}
    payload = retriever.rag_search(
        tenant_id=tenant_id,
        user_claims=user_claims,
        query=query,
        targets=resolved_targets,
        k=k,
        strategy="qdrant",
    )
    return retriever.api_response(payload)
