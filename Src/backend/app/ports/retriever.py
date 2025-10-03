# FILE: backend/app/ports/retriever.py
from __future__ import annotations
from typing import Any, Dict, List, Sequence, Tuple

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.adapters.hybrid_retriever import search as hybrid_search
from app.application.local_kb import search_chunks as fallback_search
from app.deps import SessionLocal
from app.domain.errors import ExternalServiceError
from app.domain.schemas import RetrieveHit, RetrieveResp
from app.utils.hashing import hash_text
from worker.handlers.evidence_builder import build_evidence_snippets

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
    db: Session | None = None,
) -> Dict[str, Any]:
    """Execute the hybrid retriever and return fused payloads."""

    targets = targets or ["global"]
    accessible = user_claims.get("accessible_projects", [])
    _assert_targets_allowed(targets, accessible)

    use_fallback = strategy == "local"
    fallback_message: str | None = None
    raw: List[Tuple[float, str, Dict[str, Any]]] = []

    if not use_fallback:
        try:
            raw = hybrid_search(tenant_id, targets, query, k=max(k * 3, 24), strategy=strategy)
        except ExternalServiceError as exc:
            logger.bind(req="").warning(
                "Hybrid retriever unavailable; switching to fallback", error=str(exc)
            )
            use_fallback = True
            fallback_message = "Remote retrieval unavailable; using local fallback results. Please retry later."
        except Exception:  # noqa: BLE001 - defensive catch to preserve API availability
            logger.bind(req="").exception("Hybrid retriever crashed; switching to fallback")
            use_fallback = True
            fallback_message = "Remote retrieval unavailable; using local fallback results. Please retry later."

    if use_fallback:
        session = db or SessionLocal()
        close_session = db is None
        try:
            raw = fallback_search(
                session,
                tenant_id=tenant_id,
                project_keys=targets,
                query=query,
                limit=max(k * 2, 24),
            )
            if fallback_message is None:
                fallback_message = "Remote retrieval unavailable; using local fallback results. Please retry later."
        finally:
            if close_session:
                session.close()
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
    return {"results": hits, "evidence": evidence, "fallback_message": fallback_message}

def api_response(payload: Dict[str, Any]) -> RetrieveResp:
    """Coerce internal payload structure into the API response schema."""

    resp_kwargs = {"results": payload["results"]}
    if payload.get("fallback_message"):
        resp_kwargs["message"] = payload["fallback_message"]
    return RetrieveResp(**resp_kwargs)
