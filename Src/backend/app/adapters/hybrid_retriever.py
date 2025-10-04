"""Hybrid dense+sparse retrieval helpers."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from qdrant_client.http import models as qm

from app.adapters.dense_bge import embed_one
from app.adapters.qdrant_client import (
    ResponseHandlingException,
    UnexpectedResponse,
    client,
    ensure_collection,
    ensure_payload_indexes,
    hybrid_search as qdrant_hybrid_search,
)
from app.adapters.sparse_hash import encode_sparse
from app.config import settings
from app.domain.errors import ExternalServiceError
from loguru import logger


def _build_filter(meta_filters: Dict[str, object]) -> qm.Filter | None:
    if not meta_filters:
        return None

    must_conditions: List[qm.FieldCondition] = []
    must_not_conditions: List[qm.FieldCondition] = []

    for key, value in meta_filters.items():
        if isinstance(value, dict):
            values_in = value.get("in")
            values_not_in = value.get("not_in")
            if values_in:
                must_conditions.append(
                    qm.FieldCondition(key=key, match=qm.MatchAny(any=values_in))
                )
            if values_not_in:
                must_not_conditions.append(
                    qm.FieldCondition(key=key, match=qm.MatchAny(any=values_not_in))
                )
        else:
            must_conditions.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))

    if not must_conditions and not must_not_conditions:
        return None

    filter_ = qm.Filter()
    if must_conditions:
        filter_.must = must_conditions
    if must_not_conditions:
        filter_.must_not = must_not_conditions
    return filter_


def _should_retry_for_index(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status == 400 and "index" in message


def _search_dense(collection: str, query_dense: List[float], k: int, query_filter: qm.Filter | None):
    """Search dense vectors within a collection."""
    try:
        return client.search(
            collection_name=collection,
            query_vector=qm.NamedVector(name="dense", vector=query_dense),
            limit=k,
            with_payload=True,
            with_vectors=False,
            search_params=qm.SearchParams(hnsw_ef=128, exact=False),
            query_filter=query_filter,
        )
    except (ResponseHandlingException, UnexpectedResponse) as exc:
        if _should_retry_for_index(exc):
            if settings.qdrant_autofix_index_missing:
                logger.warning(
                    "Encountered missing Qdrant index during dense search; attempting autofix",
                    collection=collection,
                )
                ensure_payload_indexes(collection)
                return client.search(
                    collection_name=collection,
                    query_vector=qm.NamedVector(name="dense", vector=query_dense),
                    limit=k,
                    with_payload=True,
                    with_vectors=False,
                    search_params=qm.SearchParams(hnsw_ef=128, exact=False),
                    query_filter=query_filter,
                )
            logger.error(
                "Qdrant dense search failed due to missing index",
                collection=collection,
                status=getattr(exc, "status_code", None),
            )
        raise


def _search_sparse(collection: str, query_sparse: qm.SparseVector, k: int, query_filter: qm.Filter | None):
    """Search sparse vectors within a collection."""
    try:
        return client.search(
            collection_name=collection,
            query_vector=qm.NamedSparseVector(name="sparse", vector=query_sparse),
            limit=k,
            with_payload=True,
            with_vectors=False,
            search_params=qm.SearchParams(hnsw_ef=128, exact=False),
            query_filter=query_filter,
        )
    except (ResponseHandlingException, UnexpectedResponse) as exc:
        if _should_retry_for_index(exc):
            if settings.qdrant_autofix_index_missing:
                logger.warning(
                    "Encountered missing Qdrant index during sparse search; attempting autofix",
                    collection=collection,
                )
                ensure_payload_indexes(collection)
                return client.search(
                    collection_name=collection,
                    query_vector=qm.NamedSparseVector(name="sparse", vector=query_sparse),
                    limit=k,
                    with_payload=True,
                    with_vectors=False,
                    search_params=qm.SearchParams(hnsw_ef=128, exact=False),
                    query_filter=query_filter,
                )
            logger.error(
                "Qdrant sparse search failed due to missing index",
                collection=collection,
                status=getattr(exc, "status_code", None),
            )
        raise


def _rrf_rank(dense_res, sparse_res, k: int, k_rrf: int = 60):
    """Fuse dense and sparse results using Reciprocal Rank Fusion."""
    dense_rank = {str(point.id): index + 1 for index, point in enumerate(dense_res)}
    sparse_rank = {str(point.id): index + 1 for index, point in enumerate(sparse_res)}
    ids = set(dense_rank) | set(sparse_rank)
    scored = []
    for identifier in ids:
        rd = dense_rank.get(identifier, 10**6)
        rs = sparse_rank.get(identifier, 10**6)
        score = 1.0 / (k_rrf + rd) + 1.0 / (k_rrf + rs)
        payload = None
        for candidate in dense_res:
            if str(candidate.id) == identifier:
                payload = candidate.payload
                break
        if payload is None:
            for candidate in sparse_res:
                if str(candidate.id) == identifier:
                    payload = candidate.payload
                    break
        scored.append((score, payload))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:k]


def search(
    tenant_id: str,
    targets: Iterable[str],
    query: str,
    k: int = 12,
    strategy: str = "qdrant",
    meta_filters: Dict[str, object] | None = None,
) -> List[Tuple[float, str, dict]]:
    """Search hybrid collections for the query using the requested strategy."""
    # IMPORTANT: match ingestion collection naming
    collections = [f"{tenant_id}__{target}" for target in (list(targets) or ["global"])]

    query_dense = embed_one(query)
    if len(query_dense) != settings.embed_dim:
        raise ExternalServiceError(
            f"Embedding dimension mismatch; expected {settings.embed_dim}, got {len(query_dense)}"
        )
    sparse_encoded = encode_sparse(query)
    query_sparse = qm.SparseVector(indices=sparse_encoded.indices, values=sparse_encoded.values)
    query_filter = _build_filter(meta_filters or {})

    fused: List[Tuple[float, str, dict]] = []
    for collection in collections:
        ensure_collection(collection, dense_dim=settings.embed_dim, create_if_missing=False)
        if strategy == "rrf":
            dense_results = _search_dense(collection, query_dense, k, query_filter)
            sparse_results = _search_sparse(collection, query_sparse, k, query_filter)
            for score, payload in _rrf_rank(dense_results, sparse_results, k=k):
                fused.append((float(score), collection, payload or {}))
        else:
            for point in qdrant_hybrid_search(
                [collection],
                query_dense,
                query_sparse,
                k,
                _lambda=0.5,
                query_filter=query_filter,
            ):
                fused.append(point)
    fused.sort(key=lambda item: item[0], reverse=True)
    return fused[:k]
