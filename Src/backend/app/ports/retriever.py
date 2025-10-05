# FILE: backend/app/ports/retriever.py
from __future__ import annotations
from typing import Any, Dict, List, Sequence, Tuple

from fastapi import HTTPException
from loguru import logger

from app.domain import models as m
from sqlalchemy.orm import Session

from app.adapters.hybrid_retriever import search as hybrid_search
from app.application.contrastive_mapper import ABMapper
from app.application.local_kb import search_chunks as fallback_search
from app.config import settings
from app.deps import SessionLocal
from app.domain.errors import ExternalServiceError
from app.domain.schemas import RetrieveHit, RetrieveReq, RetrieveResp
from app.policy.compiler import compile_policy
from app.policy.plan import PolicyPlan
from app.utils.hashing import hash_text
from worker.handlers.evidence_builder import build_evidence_snippets

def _assert_targets_allowed(targets: Sequence[str], accessible: Sequence[str]) -> List[str]:
    """Ensure requested targets are within the caller's accessible projects.

    Returns a canonicalised list where casing matches the caller's accessible projects
    (falling back to the original value when no canonical form exists).
    """

    accessible_map: Dict[str, str] = {}
    for raw in accessible or []:
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        accessible_map[value.lower()] = value

    normalised: List[str] = []
    for raw in targets or []:
        if raw is None:
            continue
        candidate = str(raw).strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered == "global":
            normalised.append(accessible_map.get("global", "global"))
            continue
        canonical = accessible_map.get(lowered)
        if canonical is None:
            raise HTTPException(status_code=403, detail=f"Access denied to project: {candidate}")
        normalised.append(canonical)

    return normalised or [accessible_map.get("global", "global")]

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

def _extract_plan_metadata(plan: PolicyPlan) -> Dict[str, Any]:
    allow_projects: List[str] = []
    deny_projects: List[str] = []
    for node in plan.steps:
        if node.kind == "AllowProjects":
            allow_projects = list(node.args.get("projects", []))
        if node.kind == "DenyProjects":
            deny_projects = list(node.args.get("projects", []))
    return {"allow_projects": allow_projects, "deny_projects": deny_projects}


def _meta_filters_from_plan(plan: PolicyPlan) -> Dict[str, Any]:
    for node in plan.steps:
        if node.kind == "FilterByMeta":
            return dict(node.args.get("filters", {}))
    return {}


def rag_search(
    tenant_id: str,
    user_claims: Dict[str, Any],
    query: str,
    targets: List[str] | None = None,
    k: int = 12,
    strategy: str = "qdrant",
    include_rosetta: bool = False,
    known_projects: List[str] | None = None,
    db: Session | None = None,
) -> Dict[str, Any]:
    """Execute the hybrid retriever and return fused payloads."""

    tenant_key = str(tenant_id or "").strip()
    if not tenant_key:
        raise HTTPException(status_code=403, detail="Missing tenant context")

    tenant_session = db or SessionLocal()
    created_session = db is None
    try:
        tenant_exists = tenant_session.get(m.Tenant, tenant_key) is not None
    finally:
        if created_session:
            tenant_session.close()

    if not tenant_exists:
        raise HTTPException(status_code=404, detail="Tenant not found")

    router_mode = settings.router_mode
    logger.bind(router_mode=router_mode, tenant_id=tenant_id).debug("Router mode selected")
    if router_mode == "learned":
        raise HTTPException(
            status_code=501,
            detail={
                "code": "ROUTER_NOT_IMPLEMENTED",
                "message": "Learned router pending",
            },
        )

    targets = targets or ["global"]
    accessible = user_claims.get("accessible_projects", [])
    targets = _assert_targets_allowed(targets, accessible)

    req = RetrieveReq(
        query=query,
    targets=list(targets or []),
        k=k,
        strategy=strategy,
        include_rosetta=include_rosetta,
        known_projects=list(known_projects or []),
    )
    plan = compile_policy(user_claims, req)
    plan_meta = _extract_plan_metadata(plan)
    filters = _meta_filters_from_plan(plan)

    logger.bind(
        request_id=user_claims.get("request_id", ""),
        tenant_id=tenant_id,
        user_role=user_claims.get("role"),
        plan_hash=plan.plan_hash,
        allow_projects=plan_meta["allow_projects"],
        deny_projects=plan_meta["deny_projects"],
    ).info("PolicyPlan compiled")

    use_fallback = strategy == "local"
    fallback_message: str | None = None
    raw: List[Tuple[float, str, Dict[str, Any]]] = []
    candidate_limit = max(int(k or 0), 40)

    if not use_fallback:
        try:
            raw = hybrid_search(
                tenant_id,
                targets,
                query,
                k=candidate_limit,
                strategy=strategy,
                meta_filters=filters,
            )
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
                limit=candidate_limit,
            )
            if fallback_message is None:
                fallback_message = "Remote retrieval unavailable; using local fallback results. Please retry later."
        finally:
            if close_session:
                session.close()
    fused = _dedupe_by_chunk_id(raw, limit=k)

    hits: List[RetrieveHit] = []
    raw_candidates: List[Dict[str, Any]] = []
    for score, col, pl in fused:
        src = pl.get("merged_sources") or pl.get("project_key") or pl.get("project_id", col)
        candidate_payload = {
            "score": float(score),
            "source": str(src),
            "chunk_id": pl.get("chunk_id", ""),
            "text": pl.get("text", ""),
            "embedding_present": bool(pl.get("embedding") is not None),
        }
        raw_candidates.append(candidate_payload)
        hits.append(RetrieveHit(
            text=pl.get("text", "[No text found in payload]"),
            score=float(score),
            source=str(src),
            chunk_id=pl.get("chunk_id", ""),
        ))

    evidence = build_evidence_snippets(hits)

    evidence_signature = hash_text("|".join(hit.chunk_id for hit in hits), namespace="evidence") if hits else ""

    logger.bind(
        request_id=user_claims.get("request_id", ""),
        plan_hash=plan.plan_hash,
        candidates_pre=len(raw),
        candidates_post=len(fused),
        pruned_count=max(len(raw) - len(fused), 0),
        final_k=len(hits),
        evidence_hash=evidence_signature,
    ).info("PolicyPlan execution summary")

    rosetta_payload: Dict[str, Any] | None = None
    rosetta_narrative_md: str | None = None
    if settings.abmap_enabled and req.include_rosetta and hits:
        mapper: ABMapper
        if db is not None:
            mapper = ABMapper(tenant_id=tenant_id, session=db)
        else:
            mapper = ABMapper(tenant_id=tenant_id, session_factory=SessionLocal)

        accessible_set = {str(p) for p in accessible if p}
        target_set = {str(t) for t in targets if t}
        allowed_targets = target_set & accessible_set
        if "global" in targets:
            allowed_targets.add("global")

        known_projects = user_claims.get("known_projects") or req.known_projects or targets

        rosetta = mapper.infer(
            known_projects=known_projects,
            top_hits=hits,
            allowed_targets=allowed_targets,
            context={"query": query, "plan_hash": plan.plan_hash},
        )
        rosetta_payload = {
            "skills_gap": rosetta.skills_gap,
            "curated_docs": rosetta.curated_docs,
        }
        rosetta_narrative_md = rosetta.narrative_md

    return {
        "results": hits,
        "evidence": evidence,
        "fallback_message": fallback_message,
        "rosetta": rosetta_payload,
        "rosetta_narrative_md": rosetta_narrative_md,
        "raw_candidates": raw_candidates,
    }

def api_response(payload: Dict[str, Any]) -> RetrieveResp:
    """Coerce internal payload structure into the API response schema."""

    resp_kwargs = {"results": payload["results"]}
    if payload.get("fallback_message"):
        resp_kwargs["message"] = payload["fallback_message"]
    if payload.get("rosetta"):
        resp_kwargs["rosetta"] = payload["rosetta"]
    if payload.get("rosetta_narrative_md"):
        resp_kwargs["rosetta_narrative_md"] = payload["rosetta_narrative_md"]
    return RetrieveResp(**resp_kwargs)
