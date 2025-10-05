"""FastAPI routes for Jira webhook ingestion."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.utils.idempotency import acquire_once, request_key
from worker.job_queue import enqueue_jira_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/jira")
async def jira(request: Request) -> dict[str, Any]:
    body = await request.body()
    headers = dict(request.headers)
    idem_key = request_key(headers, body, prefix="webhook")
    if not acquire_once(idem_key, ttl_seconds=900):
        return {"status": "duplicate_ignored", "idempotency_key": idem_key}

    if settings.env == "prod" and not settings.atlassian_api_token:
        raise HTTPException(status_code=500, detail="Jira integration not configured")

    payload = await request.json()
    enqueue_jira_event({"event": request.headers.get("X-Event-Key"), "payload": payload})
    return {"status": "queued", "idempotency_key": idem_key}
