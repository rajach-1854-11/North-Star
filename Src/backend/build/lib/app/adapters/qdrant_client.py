"""Thin wrapper around the Qdrant client configured for the app."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Dict, Iterable, List, Sequence, Tuple

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
    logger.info("Provisioning Qdrant collection", collection=name, dim=int(dense_dim))
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": qm.VectorParams(size=dense_dim, distance=qm.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": qm.SparseVectorParams(),
        },
    )
    logger.info("Provisioned Qdrant collection", collection=name)


def ensure_payload_indexes(name: str) -> None:
    """Ensure required payload indexes exist for tenant and project filters."""

    for field in ("tenant_id", "project_id", "project_key"):
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
            logger.info(
                "Qdrant payload index ensured",
                collection=name,
                index=field,
                status="created",
            )
        except (ResponseHandlingException, UnexpectedResponse) as exc:
            status = getattr(exc, "status_code", None)
            message = str(exc).lower()
            if status in {400, 409} and ("exists" in message or "already" in message):
                logger.info(
                    "Qdrant payload index ensured",
                    collection=name,
                    index=field,
                    status="exists",
                )
                continue
            if status == 404:
                logger.error(
                    "Qdrant collection unavailable for index creation",
                    collection=name,
                    index=field,
                    status=status,
                )
                raise ExternalServiceError(
                    f"Qdrant collection '{name}' is not accessible for index creation"
                ) from exc
            logger.error(
                "Qdrant payload index creation failed",
                collection=name,
                index=field,
                status=status,
                error=str(exc),
            )
            raise ExternalServiceError(
                f"Qdrant payload index creation failed for '{name}.{field}': {exc}"
            ) from exc


def ensure_all_payload_indexes() -> None:
    """Enumerate collections and ensure payload indexes exist (idempotent)."""

    try:
        collections = client.get_collections()
    except (ResponseHandlingException, UnexpectedResponse) as exc:
        logger.warning("Unable to enumerate Qdrant collections for index bootstrap: {}", exc)
        return

    for collection in getattr(collections, "collections", []) or []:
        name = getattr(collection, "name", None)
        if not name:
            continue
        try:
            ensure_payload_indexes(name)
        except ExternalServiceError as exc:
            logger.warning("Failed to ensure payload indexes", collection=name, error=str(exc))


def ensure_collection(name: str, dense_dim: int | None = None, *, create_if_missing: bool = True) -> str:
    """Validate that the expected collection exists and matches schema."""

    expected_dim = dense_dim or settings.embed_dim
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

        if size is not None and int(size) != int(expected_dim):
            logger.error(
                "Qdrant collection has incompatible vector size",
                collection=name,
                actual_dim=int(size),
                expected_dim=int(expected_dim),
            )
            raise ExternalServiceError(
                f"Qdrant collection '{name}' has incompatible vector size; expected {expected_dim}"
            )

        ensure_payload_indexes(name)
        return name
    except (ResponseHandlingException, UnexpectedResponse) as exc:
        status = getattr(exc, "status_code", None)
        if status == 404:
            if not create_if_missing:
                logger.warning(
                    "Qdrant collection missing",
                    collection=name,
                    expected_dim=int(expected_dim),
                )
                raise ExternalServiceError(
                    f"Qdrant collection '{name}' is missing"
                ) from exc
            _create_collection(name, expected_dim)
            ensure_payload_indexes(name)
            return name
        logger.error(
            "Qdrant collection error",
            collection=name,
            status=status,
            expected_dim=int(expected_dim),
            error=str(exc),
        )
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
        logger.error(
            "Failed to upsert points into Qdrant",
            collection=collection,
            count=len(ids),
            error=str(exc),
        )
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
    query_filter: Dict[str, object] | qm.Filter | None = None,
) -> List[Tuple[float, str, dict]]:
    """Perform hybrid search across multiple collections and aggregate results."""

    weight_dense = max(0.0, min(1.0, _lambda))
    weight_sparse = 1.0 - weight_dense

    if len(query_dense) != settings.embed_dim:
        raise ExternalServiceError(
            f"Embedding dimension mismatch; expected {settings.embed_dim}, got {len(query_dense)}"
        )

    if isinstance(query_filter, dict):
        from app.adapters.hybrid_retriever import _build_filter  # local import to avoid cycle

        query_filter = _build_filter(query_filter)

    results: List[Tuple[float, str, dict]] = []
    for col in collections:
        ensure_collection(col, dense_dim=settings.embed_dim, create_if_missing=False)

        def _search_with_retry(vector):
            try:
                return client.search(
                    collection_name=col,
                    query_vector=vector,
                    limit=k,
                    with_payload=True,
                    with_vectors=False,
                    search_params=qm.SearchParams(hnsw_ef=128, exact=False),
                    query_filter=query_filter if isinstance(query_filter, qm.Filter) else None,
                )
            except (ResponseHandlingException, UnexpectedResponse) as exc:
                status = getattr(exc, "status_code", None)
                if status == 400 and "index" in str(exc).lower():
                    vector_name = getattr(vector, "name", "unknown")
                    if settings.qdrant_autofix_index_missing:
                        logger.warning(
                            "Encountered missing Qdrant index; attempting autofix",
                            collection=col,
                            vector_type=vector_name,
                        )
                        ensure_payload_indexes(col)
                        return client.search(
                            collection_name=col,
                            query_vector=vector,
                            limit=k,
                            with_payload=True,
                            with_vectors=False,
                            search_params=qm.SearchParams(hnsw_ef=128, exact=False),
                            query_filter=query_filter if isinstance(query_filter, qm.Filter) else None,
                        )
                    else:
                        logger.error(
                            "Qdrant search failed due to missing index",
                            collection=col,
                            vector_type=vector_name,
                            status=status,
                        )
                else:
                    logger.error(
                        "Qdrant search failure",
                        collection=col,
                        vector_type=getattr(vector, "name", "unknown"),
                        status=status,
                    )
                raise

        dense_points = _search_with_retry(qm.NamedVector(name="dense", vector=query_dense))
        sparse_points = _search_with_retry(qm.NamedSparseVector(name="sparse", vector=query_sparse))

        for score, payload in _fuse_hybrid(dense_points, sparse_points, weight_dense, weight_sparse)[:k]:
            results.append((score, col, payload))

    results.sort(key=lambda item: item[0], reverse=True)
    return results[:k]
