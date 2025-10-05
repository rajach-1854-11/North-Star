"""Lightweight local knowledge base fallback when Qdrant is unavailable."""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Sequence, Tuple

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain import models as m
from app.utils.chunk import smart_chunks
from app.utils.hashing import hash_text

_TOKEN_RE = re.compile(r"[A-Za-z0-9_#.-]+")


def _tokenise(text: str) -> List[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def store_chunks(
    db: Session,
    *,
    tenant_id: str,
    project: m.Project,
    text: str,
    source: str,
    max_tokens: int = 480,
    overlap_tokens: int = 40,
) -> dict[str, int]:
    """Persist document chunks into the ``event`` table for fallback retrieval."""

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
        raise ValueError("No chunkable content for fallback store")

    payloads = []
    for index, chunk in enumerate(chunks):
        chunk_id = hash_text(chunk, namespace=f"{tenant_id}:{project.key}")
        payloads.append(
            m.Event(
                tenant_id=tenant_id,
                project_id=project.id,
                developer_id=0,
                type="kb_chunk",
                payload_json={
                    "chunk_id": chunk_id,
                    "text": chunk,
                    "project_key": project.key,
                    "position": index,
                    "source": source,
                },
            )
        )

    # Replace existing chunks for the project to keep snapshot consistent.
    existing = (
        db.query(m.Event)
        .filter(m.Event.tenant_id == tenant_id)
        .filter(m.Event.type == "kb_chunk")
        .all()
    )
    for event in existing:
        if (event.payload_json or {}).get("project_key") == project.key:
            db.delete(event)
    db.add_all(payloads)
    db.commit()

    logger.bind(req="").info(
        "Stored fallback knowledge chunks",
        project=project.key,
        tenant=tenant_id,
        chunks=len(payloads),
    )

    return {"collection": "local_kb", "count": len(payloads), "chunks": len(payloads)}


def search_chunks(
    db: Session,
    *,
    tenant_id: str,
    project_keys: Sequence[str],
    query: str,
    limit: int,
) -> List[Tuple[float, str, dict]]:
    """Retrieve chunks via simple keyword scoring for fallback responses."""

    tokens = _tokenise(query)
    if not tokens:
        tokens = [token.lower() for token in (query or "").split() if token]

    stmt = (
        select(m.Event)
        .where(m.Event.tenant_id == tenant_id)
        .where(m.Event.type == "kb_chunk")
    )

    events = db.execute(stmt).scalars().all()
    if project_keys:
        project_keys_set = set(project_keys)
        events = [event for event in events if (event.payload_json or {}).get("project_key") in project_keys_set]
    results: List[Tuple[float, str, dict]] = []
    for event in events:
        payload = event.payload_json or {}
        text = payload.get("text", "")
        chunk_tokens = _tokenise(text)
        if not chunk_tokens:
            continue

        token_counts = {token: chunk_tokens.count(token) for token in set(chunk_tokens)}
        score = 0.0
        for token in tokens:
            tf = token_counts.get(token, 0)
            if tf:
                score += 1.0 + math.log(tf)

        if score <= 0:
            continue

        results.append((score, payload.get("project_key", ""), payload))

    results.sort(key=lambda item: item[0], reverse=True)
    top = results[:limit]
    if not top and events:
        # Return the first few chunks as a neutral fallback.
        top = [(0.1, evt.payload_json.get("project_key", ""), evt.payload_json) for evt in events[:limit]]

    return top