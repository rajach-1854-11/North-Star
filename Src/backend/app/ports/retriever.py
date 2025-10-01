# FILE: backend/app/ports/retriever.py
from __future__ import annotations
from typing import Any, Dict, List, Sequence, Tuple
from fastapi import HTTPException
from app.adapters.hybrid_retriever import search as hybrid_search  # your adapters path/spelling
from app.adapters.sparse_hash import encode_sparse
from app.adapters.dense_bge import embed_one
from app.domain.schemas import RetrieveHit, RetrieveResp
from worker.handlers.evidence_builder import build_evidence_snippets
from app.utils.hashing import hash_text

def _assert_targets_allowed(targets: Sequence[str], accessible: Sequence[str]) -> None:
    """Ensure requested targets are within the caller's accessible projects."""

    for t in targets or []:
        if t != "global" and t not in accessible:
            raise HTTPException(status_code=403, detail=f"Access denied to project: {t}")

def _dedupe_by_chunk_id(
    rows: List[Tuple[float, str, Dict[str, Any]]],
    limit: int
) -> List[Tuple[float, str, Dict[str, Any]]]:
    """Merge duplicate chunks across collections preferring the best score."""

    best: Dict[str, Tuple[float, str, Dict[str, Any], set[str]]] = {}
    for score, col, pl in rows:
        cid = pl.get("chunk_id") or hash_text(pl.get("text",""), namespace="retrieval")
        src = pl.get("project_key", pl.get("project_id", col))
        if cid not in best or score > best[cid][0]:
            best[cid] = (score, col, pl, {str(src)})
        else:
            best[cid][3].add(str(src))
    merged: List[Tuple[float, str, Dict[str, Any]]] = []
    for _cid, (score, col, pl, sources) in best.items():
        pl = dict(pl)
        pl["merged_sources"] = "+".join(sorted(sources))
        merged.append((score, col, pl))
    merged.sort(key=lambda x: x[0], reverse=True)
    return merged[:limit]

def rag_search(
    tenant_id: str,
    user_claims: Dict[str, Any],
    query: str,
    targets: List[str] | None = None,
    k: int = 12,
    strategy: str = "qdrant",
) -> Dict[str, Any]:
    """Execute the hybrid retriever and return fused payloads."""

    targets = targets or ["global"]
    accessible = user_claims.get("accessible_projects", [])
    _assert_targets_allowed(targets, accessible)

    _ = embed_one(query)
    _ = encode_sparse(query)

    raw = hybrid_search(tenant_id, targets, query, k=max(k * 3, 24), strategy=strategy)
    fused = _dedupe_by_chunk_id(raw, limit=k)

    hits: List[RetrieveHit] = []
    for score, col, pl in fused:
        src = pl.get("merged_sources") or pl.get("project_key") or pl.get("project_id", col)
        hits.append(RetrieveHit(
            text=pl.get("text", "[No text found in payload]"),
            score=float(score),
            source=str(src),
            chunk_id=pl.get("chunk_id", "")
        ))

    evidence = build_evidence_snippets(hits)
    return {"results": hits, "evidence": evidence}

def api_response(payload: Dict[str, Any]) -> RetrieveResp:
    """Coerce internal payload structure into the API response schema."""

    return RetrieveResp(results=payload["results"])
