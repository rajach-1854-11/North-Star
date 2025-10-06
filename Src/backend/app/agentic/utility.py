"""Shared helper utilities for agentic planner/tool orchestration."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Sequence


EMPTY_VALUE_SENTINEL = "__agentic_empty__"


REQUIRED_TOOL_FIELDS: Dict[str, List[str]] = {
    "jira_epic": ["summary", "description", "description_text"],
    "confluence_page": ["title", "body_html"],
}


def validate_tool_args(
    tool_name: str,
    args: Dict[str, Any],
    required_fields: Dict[str, List[str]] | None = None,
) -> Dict[str, Any]:
    """Return structured validation result for tool arguments."""

    required = required_fields or REQUIRED_TOOL_FIELDS
    missing: List[str] = []
    auto_fill: Dict[str, Any] = {}

    for field in required.get(tool_name, []):
        value = args.get(field)
        if value in (None, ""):
            missing.append(field)

    return {"ok": not missing, "missing": missing, "auto_fill": auto_fill}


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def mmr_select(
    hits: Iterable[Dict[str, Any]] | Iterable[Any],
    *,
    limit: int = 6,
    lambda_param: float = 0.65,
) -> List[Dict[str, Any]]:
    """Return a sub-selection of hits using Maximal Marginal Relevance."""

    prepared: List[Dict[str, Any]] = []
    for hit in hits:
        if hasattr(hit, "model_dump"):
            data = hit.model_dump()
        elif hasattr(hit, "dict"):
            data = hit.dict()
        else:
            data = dict(hit) if isinstance(hit, dict) else {}
        prepared.append(data)

    if not prepared:
        return []

    selected: List[Dict[str, Any]] = []
    remaining = prepared.copy()

    while remaining and len(selected) < limit:
        best_idx = 0
        best_score = float("-inf")
        for idx, candidate in enumerate(remaining):
            relevance = float(candidate.get("score") or 0.0)
            diversity = 0.0
            candidate_embedding = candidate.get("embedding")
            if candidate_embedding and selected:
                diversity = max(
                    _cosine_similarity(candidate_embedding, chosen.get("embedding") or [])
                    for chosen in selected
                )
            score = lambda_param * relevance - (1 - lambda_param) * diversity
            if score > best_score:
                best_score = score
                best_idx = idx
        selected.append(remaining.pop(best_idx))

    return selected[:limit]


def token_estimate(text: str) -> int:
    """Very rough token estimate (4 chars per token heuristic)."""

    clean = text or ""
    return max(1, math.ceil(len(clean) / 4))


def summarize_text(text: str, *, max_chars: int = 3000, allow_llm: bool = False) -> str:
    """Return a summary capped at ``max_chars`` with optional LLM note."""

    stripped = (text or "").strip()
    if not stripped:
        return ""
    if len(stripped) <= max_chars:
        return stripped
    truncated = stripped[: max_chars - 3].rstrip() + "..."
    if allow_llm:
        return truncated + " (auto-summarized)"
    return truncated + " (auto-truncated - consider allowing 'llm')"


def build_context_items(
    hits: Sequence[Dict[str, Any]],
    *,
    allow_llm: bool = False,
    max_chars: int = 3000,
) -> List[Dict[str, Any]]:
    """Build context payload items from retrieval hits."""

    items: List[Dict[str, Any]] = []
    for idx, hit in enumerate(hits, start=1):
        text = summarize_text(str(hit.get("text") or ""), max_chars=max_chars, allow_llm=allow_llm)
        items.append(
            {
                "n": idx,
                "chunk_id": hit.get("chunk_id"),
                "source": hit.get("source"),
                "score": float(hit.get("score") or 0.0),
                "text": text,
            }
        )
    return items


def local_extract_for_fields(context_items: Sequence[Dict[str, Any]], missing_fields: Sequence[str]) -> Dict[str, str]:
    """Provide lightweight heuristics to populate missing tool fields."""

    top_text = ""
    if context_items:
        top_text = str(context_items[0].get("text") or "")

    sentences = re.split(r"(?<=[.!?])\s+", top_text.strip()) if top_text else []
    sentences = [sent.strip() for sent in sentences if sent.strip()]

    suggestions: Dict[str, str] = {}
    if "summary" in missing_fields:
        headline = sentences[0] if sentences else top_text[:140]
        suggestions["summary"] = (headline or "PX onboarding epic")[:140]
    if "description" in missing_fields or "description_text" in missing_fields:
        body_sentences = sentences[:3] or ([top_text[:300]] if top_text else [])
        description = " ".join(body_sentences).strip()
        if not description:
            description = "Auto-generated description for PX onboarding."
        suggestions["description"] = description[:1000]
        suggestions["description_text"] = suggestions["description"]
    if "title" in missing_fields:
        suggestions["title"] = (sentences[0] if sentences else "PX context summary")[:120]
    if "body_html" in missing_fields:
        snippet = "<p>" + (" ".join(sentences[:5]) or top_text[:600]) + "</p>"
        suggestions["body_html"] = snippet

    return suggestions


def normalise_tool_name(tool: str) -> str:
    mapping = {
        "jira_epic": "jira",
        "jira_issue": "jira",
        "confluence_page": "confluence",
    }
    return mapping.get(tool, tool)