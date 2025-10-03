"""Thin wrapper around the Qdrant client configured for the app."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Iterable, List, Sequence, Tuple

from qdrant_client import QdrantClient
try:
    import qdrant_client.exceptions as qexc  # type: ignore[reportMissingImports]
    ResponseHandlingException = getattr(qexc, "ResponseHandlingException", Exception)
    UnexpectedResponse = getattr(qexc, "UnexpectedResponse", Exception)
except Exception:  # pragma: no cover
    ResponseHandlingException = UnexpectedResponse = Exception  # type: ignore[assignment]

from qdrant_client.http import models as qm

from app.config import settings
from app.domain.errors import ExternalServiceError
from loguru import logger

if not settings.qdrant_url:
    raise ExternalServiceError("Qdrant URL is not configured")

client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

def get_client() -> QdrantClient:
    return client


def _create_collection(name: str, dense_dim: int) -> None:
    logger.info("Provisioning Qdrant collection", collection=name, dim=dense_dim)
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": qm.VectorParams(size=dense_dim, distance=qm.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": qm.SparseVectorParams(),
        },
    )


def ensure_collection(name: str, dense_dim: int = 1024) -> str:
    """Validate that the expected collection exists and matches schema."""

    try:
        info = client.get_collection(name)
        if not info:
            raise ExternalServiceError(f"Qdrant collection '{name}' is unavailable")

        dense = None
        params = getattr(info.config, "params", None) if info.config else None
        if params is not None:
            vectors = getattr(params, "vectors", None)
            if isinstance(vectors, Mapping):
                dense = vectors.get("dense")
            else:
                dense = getattr(vectors, "dense", None)

        size = None
        if isinstance(dense, Mapping):
            size = dense.get("size")
        elif dense is not None:
            size = getattr(dense, "size", None)

        if size is not None and size != dense_dim:
            raise ExternalServiceError(
                f"Qdrant collection '{name}' has incompatible vector size; expected {dense_dim}"
            )
        return name
    except (ResponseHandlingException, UnexpectedResponse) as exc:
        status = getattr(exc, "status_code", None)
        if status == 404:
            _create_collection(name, dense_dim)
            return name
        raise ExternalServiceError(f"Qdrant collection '{name}' is not accessible: {exc}") from exc


def upsert_points(
    collection: str,
    ids: Sequence[str],
    dense_vectors: Sequence[Sequence[float]],
    sparse_vectors: Sequence[qm.SparseVector],
    payloads: Sequence[dict[str, object]],
) -> None:
    """Upsert a batch of points into Qdrant."""
    try:
        client.upsert(
            collection_name=collection,
            points=qm.Batch(
                ids=list(ids),
                vectors={"dense": list(dense_vectors), "sparse": list(sparse_vectors)},
                payloads=list(payloads),
            ),
        )
    except (ResponseHandlingException, UnexpectedResponse) as exc:  # pragma: no cover
        raise ExternalServiceError(f"Failed to upsert points into '{collection}': {exc}") from exc


def _fuse_hybrid(
    dense_results: Sequence[qm.ScoredPoint],
    sparse_results: Sequence[qm.ScoredPoint],
    weight_dense: float,
    weight_sparse: float,
) -> List[Tuple[float, dict]]:
    fused: dict[str, dict[str, object]] = {}

    for point in dense_results:
        identifier = str(point.id)
        entry = fused.setdefault(identifier, {"payload": point.payload or {}, "dense": 0.0, "sparse": 0.0})
        entry["dense"] = max(float(point.score), float(entry.get("dense", 0.0)))
        if not entry.get("payload"):
            entry["payload"] = point.payload or {}

    for point in sparse_results:
        identifier = str(point.id)
        entry = fused.setdefault(identifier, {"payload": point.payload or {}, "dense": 0.0, "sparse": 0.0})
        entry["sparse"] = max(float(point.score), float(entry.get("sparse", 0.0)))
        if not entry.get("payload"):
            entry["payload"] = point.payload or {}

    combined: List[Tuple[float, dict]] = []
    for entry in fused.values():
        dense_score = float(entry.get("dense", 0.0))
        sparse_score = float(entry.get("sparse", 0.0))
        score = (weight_dense * dense_score) + (weight_sparse * sparse_score)
        combined.append((score, entry.get("payload", {}) or {}))

    combined.sort(key=lambda item: item[0], reverse=True)
    return combined


def hybrid_search(
    collections: Iterable[str],
    query_dense: List[float],
    query_sparse: qm.SparseVector,
    k: int,
    _lambda: float,
) -> List[Tuple[float, str, dict]]:
    """Perform hybrid search across multiple collections and aggregate results."""

    weight_dense = max(0.0, min(1.0, _lambda))
    weight_sparse = 1.0 - weight_dense

    results: List[Tuple[float, str, dict]] = []
    for col in collections:
        ensure_collection(col, dense_dim=len(query_dense))

        dense_points = client.search(
            collection_name=col,
            query_vector=qm.NamedVector(name="dense", vector=query_dense),
            limit=k,
            with_payload=True,
            with_vectors=False,
            search_params=qm.SearchParams(hnsw_ef=128, exact=False),
        )
        sparse_points = client.search(
            collection_name=col,
            query_vector=qm.NamedSparseVector(name="sparse", vector=query_sparse),
            limit=k,
            with_payload=True,
            with_vectors=False,
            search_params=qm.SearchParams(hnsw_ef=128, exact=False),
        )

        for score, payload in _fuse_hybrid(dense_points, sparse_points, weight_dense, weight_sparse)[:k]:
            results.append((score, col, payload))

    results.sort(key=lambda item: item[0], reverse=True)
    return results[:k]
