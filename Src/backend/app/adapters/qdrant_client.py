"""Thin wrapper around the Qdrant client configured for the app."""

from __future__ import annotations

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

if not settings.qdrant_url:
    raise ExternalServiceError("Qdrant URL is not configured")

client = QdrantClient(url=settings.qdrant_url)

def get_client() -> QdrantClient:
    return client


def ensure_collection(name: str, dense_dim: int = 1024) -> str:
    """Ensure a multi-vector collection exists with the expected schema."""
    try:
        info = client.get_collection(name)
        if info:
            return name
    except (ResponseHandlingException, UnexpectedResponse):
        pass

    client.recreate_collection(
        collection_name=name,
        vectors_config={"dense": qm.VectorParams(size=dense_dim, distance=qm.Distance.COSINE)},
        sparse_vectors_config={"sparse": qm.SparseVectorParams(indexed=True)},
    )
    return name


def upsert_points(
    collection: str,
    ids: Sequence[str],
    dense_vectors: Sequence[Sequence[float]],
    sparse_vectors: Sequence[qm.SparseVector],
    payloads: Sequence[dict[str, object]],
) -> None:
    """Upsert a batch of points into Qdrant."""
    client.upsert(
        collection_name=collection,
        points=qm.Batch(
            ids=list(ids),
            vectors={"dense": list(dense_vectors), "sparse": list(sparse_vectors)},
            payloads=list(payloads),
        ),
    )


def hybrid_search(
    collections: Iterable[str],
    query_dense: List[float],
    query_sparse: qm.SparseVector,
    k: int,
    _lambda: float,
) -> List[Tuple[float, str, dict]]:
    """Perform hybrid search across multiple collections and aggregate results."""
    _ = _lambda  # reserved
    results: List[Tuple[float, str, dict]] = []
    for col in collections:
        ensure_collection(col, dense_dim=len(query_dense))
        response = client.search(
            collection_name=col,
            query_vector=qm.NamedVector(name="dense", vector=query_dense),
            sparse_vector=query_sparse,
            limit=k,
            with_payload=True,
            with_vectors=False,
            params=qm.SearchParams(hnsw_ef=128, exact=False),
        )
        for point in response:
            results.append((float(point.score), col, point.payload or {}))
    results.sort(key=lambda item: item[0], reverse=True)
    return results[:k]
