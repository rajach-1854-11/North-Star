"""Hybrid dense+sparse retrieval helpers."""

from __future__ import annotations

from typing import Iterable, List, Tuple

from qdrant_client.http import models as qm

from app.adapters.dense_bge import embed_one
from app.adapters.qdrant_client import ensure_collection, hybrid_search as qdrant_hybrid_search, client
from app.adapters.sparse_hash import encode_sparse


def _search_dense(collection: str, query_dense: List[float], k: int):
    """Search dense vectors within a collection."""
    return client.search(
        collection_name=collection,
        query_vector=qm.NamedVector(name="dense", vector=query_dense),
        limit=k,
        with_payload=True,
        with_vectors=False,
        search_params=qm.SearchParams(hnsw_ef=128, exact=False),
    )


def _search_sparse(collection: str, query_sparse: qm.SparseVector, k: int):
    """Search sparse vectors within a collection."""
    return client.search(
        collection_name=collection,
        query_vector=qm.NamedSparseVector(name="sparse", vector=query_sparse),
        limit=k,
        with_payload=True,
        with_vectors=False,
        search_params=qm.SearchParams(hnsw_ef=128, exact=False),
    )


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


def search(tenant_id: str, targets: Iterable[str], query: str, k: int = 12, strategy: str = "qdrant") -> List[Tuple[float, str, dict]]:
    """Search hybrid collections for the query using the requested strategy."""
    # IMPORTANT: match ingestion collection naming
    collections = [f"{tenant_id}__{target}" for target in (list(targets) or ["global"])]

    query_dense = embed_one(query)
    sparse_encoded = encode_sparse(query)
    query_sparse = qm.SparseVector(indices=sparse_encoded.indices, values=sparse_encoded.values)

    fused: List[Tuple[float, str, dict]] = []
    for collection in collections:
        ensure_collection(collection, dense_dim=len(query_dense))
        if strategy == "rrf":
            dense_results = _search_dense(collection, query_dense, k)
            sparse_results = _search_sparse(collection, query_sparse, k)
            for score, payload in _rrf_rank(dense_results, sparse_results, k=k):
                fused.append((float(score), collection, payload or {}))
        else:
            for point in qdrant_hybrid_search([collection], query_dense, query_sparse, k, _lambda=0.5):
                fused.append(point)
    fused.sort(key=lambda item: item[0], reverse=True)
    return fused[:k]
