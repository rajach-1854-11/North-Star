"""Document ingestion pipeline for project knowledge bases."""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from typing import Any, List
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from qdrant_client.http import models as qm

from app.adapters.dense_bge import embed_batch
from app.adapters.qdrant_client import ensure_collection as ensure_qdrant_collection, get_client, upsert_points
from app.domain.errors import ExternalServiceError
from app.adapters.sparse_hash import encode_sparse
from app.utils.chunk import smart_chunks
from app.utils.hashing import hash_text


def _collection_name(tenant_id: str, project_key: str) -> str:
    """Return the Qdrant collection name for the project."""
    return f"{tenant_id}__{project_key}"


def _to_points(
    chunks: Iterable[str],
    dense_vecs: List[List[float]],
    tenant_id: str,
    project_key: str,
) -> tuple[List[str], List[List[float]], List[qm.SparseVector], List[dict[str, Any]]]:
    """Convert embedded chunks into components suitable for upsert."""
    ids: List[str] = []
    sparse_vectors: List[qm.SparseVector] = []
    payloads: List[dict[str, Any]] = []
    for index, (chunk, vector) in enumerate(zip(chunks, dense_vecs)):
        sparse = encode_sparse(chunk)
        digest = hash_text(chunk, namespace=f"{tenant_id}:{project_key}")
        chunk_uuid = UUID(hex=digest[:32])
        chunk_id = str(chunk_uuid)
        ids.append(chunk_id)
        sparse_vectors.append(qm.SparseVector(indices=sparse.indices, values=sparse.values))
        payloads.append(
            {
                "text": chunk,
                "chunk_id": chunk_id,
                "chunk_hash": digest,
                "tenant_id": tenant_id,
                "project_key": project_key,
                "source": "upload",
                "position": index,
            }
        )
    return ids, dense_vecs, sparse_vectors, payloads


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
    except Exception as exc:  # noqa: BLE001 - upstream library raises broad errors
        raise ExternalServiceError(f"Embedding model unavailable: {exc}") from exc

    if not dense_vecs or not dense_vecs[0]:
        raise ExternalServiceError("Embedding returned empty vectors")

    collection = _collection_name(tenant_id, project_key)
    ensure_qdrant_collection(collection, dense_dim=len(dense_vecs[0]))

    ids, dense_vectors, sparse_vectors, payloads = _to_points(chunks, dense_vecs, tenant_id, project_key)
    upsert_points(collection, ids, dense_vectors, sparse_vectors, payloads)
    logger.info("Ingested chunks", count=len(ids), collection=collection)

    return {"collection": collection, "count": len(ids), "chunks": len(ids)}


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


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Decode file bytes into plain text using best-effort heuristics."""

    name = (filename or "").lower()
    if name.endswith((".md", ".markdown", ".txt")):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore")

    if name.endswith(".pdf"):
        text = _pdf_to_text(file_bytes)
        if not text:
            raise HTTPException(status_code=422, detail="Could not extract text from PDF")
        return text

    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="ignore")


def ingest_file(
    file_bytes: bytes,
    filename: str,
    tenant_id: str,
    project_key: str,
) -> dict[str, Any]:
    """Ingest a file by dispatching to the correct decoder."""

    text = extract_text(file_bytes, filename)
    return ingest_text(text, tenant_id, project_key)
