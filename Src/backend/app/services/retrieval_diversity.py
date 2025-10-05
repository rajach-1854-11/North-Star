"""Utilities for assessing and improving retrieval diversity."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence


def dedupe_by_source(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return results keeping the highest scoring item per chunk identifier."""

    best: Dict[str, Dict[str, Any]] = {}
    overflow: List[Dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get("chunk_id") or "").strip()
        score = float(item.get("score") or 0.0)
        target = {
            "text": item.get("text"),
            "score": score,
            "source": item.get("source"),
            "chunk_id": chunk_id or None,
            "embedding": item.get("embedding"),
        }
        if chunk_id:
            current = best.get(chunk_id)
            if current is None or (current.get("score") or 0.0) < score:
                best[chunk_id] = target
        else:
            overflow.append(target)
    deduped = list(best.values())
    deduped.sort(key=lambda r: r.get("score") or 0.0, reverse=True)
    if overflow:
        deduped.extend(overflow)
    return deduped


def lexical_filter(
    results: Sequence[Dict[str, Any]],
    k: int = 8,
    max_overlap: float = 0.6,
) -> List[Dict[str, Any]]:
    """Simple trigram based filter to reduce near-duplicate text when embeddings are unavailable."""

    def _normalise(text: str) -> List[str]:
        cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
        return [token for token in cleaned.split() if token]

    def _trigrams(tokens: List[str]) -> set[tuple[str, str, str]]:
        if len(tokens) < 3:
            return set()
        return {tuple(tokens[i : i + 3]) for i in range(len(tokens) - 2)}

    picked: List[Dict[str, Any]] = []
    picked_trigrams: List[set[tuple[str, str, str]]] = []

    for item in sorted(results, key=lambda r: r.get("score") or 0.0, reverse=True):
        text = str(item.get("text") or "")
        tokens = _normalise(text)
        tri = _trigrams(tokens)
        if not picked:
            picked.append(item)
            picked_trigrams.append(tri)
            if len(picked) >= k:
                break
            continue
        overlap = 0.0
        for existing in picked_trigrams:
            if not existing:
                continue
            overlap = max(overlap, len(tri & existing) / (len(tri) + 1e-9))
        if overlap <= max_overlap:
            picked.append(item)
            picked_trigrams.append(tri)
            if len(picked) >= k:
                break
    return picked


def diversity_stats(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    sources = [str(r.get("source") or "") for r in results if r.get("source")]
    chunk_ids = [str(r.get("chunk_id") or "") for r in results if r.get("chunk_id")]
    counts = Counter(sources)
    top_source = counts.most_common(1)[0][0] if counts else None
    top_count = counts.most_common(1)[0][1] if counts else 0
    return {
        "total_hits": len(results),
        "unique_chunks": len(set(chunk_ids)),
        "unique_sources": len(counts),
        "top_source": top_source,
        "top_source_share": top_count / float(len(results) or 1),
    }


def diversity_gate(
    results: Sequence[Dict[str, Any]],
    *,
    min_unique_chunks: int = 3,
    max_top_source_share: float = 0.6,
) -> tuple[bool, Dict[str, Any]]:
    stats = diversity_stats(results)
    ok = stats["total_hits"] == 0 or (
        stats["unique_chunks"] >= min_unique_chunks
        and stats["top_source_share"] <= max_top_source_share
    )
    stats["top_source_share"] = round(stats["top_source_share"], 3)
    return ok, stats
