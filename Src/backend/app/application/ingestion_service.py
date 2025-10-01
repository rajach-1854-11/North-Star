"""Document ingestion pipeline for project knowledge bases."""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from typing import Any, List

from fastapi import HTTPException
from loguru import logger
from qdrant_client import QdrantClient
try:
    import qdrant_client.exceptions as qexc  # type: ignore[reportMissingImports]
    ResponseHandlingException = getattr(qexc, "ResponseHandlingException", Exception)
    UnexpectedResponse = getattr(qexc, "UnexpectedResponse", Exception)
except Exception:  # pragma: no cover - fallback for older versions
    ResponseHandlingException = UnexpectedResponse = Exception  # type: ignore[assignment]
from qdrant_client.http import models as qm

from app.adapters.dense_bge import embed_batch, embed_one
from app.adapters.qdrant_client import get_client
from app.adapters.sparse_hash import encode_sparse
from app.utils.chunk import smart_chunks
from app.utils.hashing import hash_text


def _collection_name(tenant_id: str, project_key: str) -> str:
    """Return the Qdrant collection name for the project."""
    return f"{tenant_id}__{project_key}"


def _ensure_collection(client: QdrantClient, name: str, dense_size: int) -> None:
    """Create the collection if it does not exist."""
    try:
        client.get_collection(name)
        return
    except (ResponseHandlingException, UnexpectedResponse):
        logger.info("Creating Qdrant collection", collection=name, dense_size=dense_size)

    client.recreate_collection(
        collection_name=name,
        vectors_config={"dense": qm.VectorParams(size=dense_size, distance=qm.Distance.COSINE)},
    )


def _to_points(
    chunks: Iterable[str],
    dense_vecs: List[List[float]],
    tenant_id: str,
    project_key: str,
) -> List[qm.PointStruct]:
    """Convert embedded chunks into Qdrant point structs."""
    points: List[qm.PointStruct] = []
    for index, (chunk, vector) in enumerate(zip(chunks, dense_vecs)):
        sparse = encode_sparse(chunk)
        chunk_id = hash_text(chunk, namespace=f"{tenant_id}:{project_key}")
        points.append(
            qm.PointStruct(
                id=chunk_id,
                vector={
                    "dense": vector,
                    "sparse": qm.SparseVector(indices=sparse.indices, values=sparse.values),
                },
                payload={
                    "text": chunk,
                    "chunk_id": chunk_id,
                    "tenant_id": tenant_id,
                    "project_key": project_key,
                    "source": "upload",
                    "position": index,
                },
            )
        )
    return points


def ingest_text(
    text: str,
    tenant_id: str,
    project_key: str,
    *,
    max_tokens: int = 480,
    overlap_tokens: int = 40,
) -> dict[str, Any]:
    """Chunk, embed, and upsert plain text into Qdrant."""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Empty document")

    chunks = list(
        smart_chunks(
            text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            respect_markdown=True,
            section_prefix=True,
        )
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunkable content")

    try:
        dense_vecs = embed_batch(chunks)
    except Exception as exc:  # noqa: BLE001 - upstream libraries surface generic exceptions
        logger.warning("embed_batch failed; falling back to sequential embedding", error=str(exc))
        dense_vecs = [embed_one(chunk) for chunk in chunks]

    if not dense_vecs or not dense_vecs[0]:
        raise HTTPException(status_code=500, detail="Embedding returned empty vectors")

    client = get_client()
    collection = _collection_name(tenant_id, project_key)
    _ensure_collection(client, collection, dense_size=len(dense_vecs[0]))

    points = _to_points(chunks, dense_vecs, tenant_id, project_key)
    client.upsert(collection_name=collection, points=points, wait=True)
    logger.info("Ingested chunks", count=len(points), collection=collection)

    return {"collection": collection, "count": len(points), "chunks": len(points)}


def _pdf_to_text(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        from PyPDF2 import PdfReader
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise HTTPException(status_code=415, detail="PDF support not installed; pip install PyPDF2") from exc

    reader = PdfReader(BytesIO(file_bytes))
    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 - library surfaces broad exceptions
            logger.warning("Failed to extract text from PDF page", error=str(exc))
            pages.append("")
    return "\n\n".join(pages).strip()


def ingest_file(
    file_bytes: bytes,
    filename: str,
    tenant_id: str,
    project_key: str,
) -> dict[str, Any]:
    """Ingest a file by dispatching to the correct decoder."""
    name = (filename or "").lower()
    if name.endswith((".md", ".markdown", ".txt")):
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="ignore")
        return ingest_text(text, tenant_id, project_key)

    if name.endswith(".pdf"):
        text = _pdf_to_text(file_bytes)
        if not text:
            raise HTTPException(status_code=422, detail="Could not extract text from PDF")
        return ingest_text(text, tenant_id, project_key)

    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="ignore")
    return ingest_text(text, tenant_id, project_key)
