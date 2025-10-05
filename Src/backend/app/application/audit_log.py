"""Audit logging utilities for agentic planner executions."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from loguru import logger


def _scrub_sequences(items: Sequence[Mapping[str, Any]] | None, *, limit: int = 25) -> list[dict[str, Any]]:
    if not items:
        return []
    scrubbed: list[dict[str, Any]] = []
    for item in items[:limit]:
        if isinstance(item, Mapping):
            scrubbed.append(dict(item))
        else:
            scrubbed.append({"value": str(item)})
    return scrubbed


def write_chat_audit_entry(
    *,
    request_id: str,
    tenant_id: str,
    user_id: str | None,
    query: str,
    retriever_candidates: Sequence[Mapping[str, Any]] | None = None,
    top6: Sequence[Mapping[str, Any]] | None = None,
    planner_instruction: str | None = None,
    llm_payload: Mapping[str, Any] | None = None,
    llm_response: Mapping[str, Any] | None = None,
    adapter_events: Iterable[Mapping[str, Any]] | None = None,
) -> None:
    """Emit a structured audit log entry for downstream ingestion."""

    payload = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "query": query,
        "planner_instruction": planner_instruction,
        "retriever_candidates": _scrub_sequences(retriever_candidates),
        "top6": _scrub_sequences(top6, limit=6),
        "llm_payload": dict(llm_payload) if isinstance(llm_payload, Mapping) else llm_payload,
        "llm_response": dict(llm_response) if isinstance(llm_response, Mapping) else llm_response,
        "adapter_events": list(adapter_events)[:50] if adapter_events else [],
    }
    logger.bind(channel="audit", event="chat_execution").info(payload)
