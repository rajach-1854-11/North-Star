"""FastAPI routes for GitHub webhook ingestion."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.utils.hashing import hash_bytes
from app.utils.idempotency import acquire_once, request_key
from worker.job_queue import enqueue_github_event

router = APIRouter(prefix="/events", tags=["events"])


def _verify_signature(signature: str | None, body: bytes) -> bool:
    """Validate the ``X-Hub-Signature-256`` header using HMAC-SHA256."""

    if not settings.github_webhook_secret:
        raise HTTPException(status_code=500, detail="GitHub webhook secret is not configured")

    digest = hash_bytes(body, algo="sha256", key=settings.github_webhook_secret)
    expected = f"sha256={digest}"
    return signature is not None and hmac.compare_digest(expected, signature)


@router.post("/github")
async def github(request: Request) -> dict[str, Any]:
    """Receive a GitHub webhook and enqueue it for background processing."""

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(signature, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    idem_key = request_key(dict(request.headers), body, prefix="webhook")
    if not acquire_once(idem_key, ttl_seconds=900):
        return {"status": "duplicate_ignored", "idempotency_key": idem_key}

    event = request.headers.get("X-GitHub-Event", "unknown")
    payload = await request.json()
    enqueue_github_event({"event": event, "payload": payload})
    return {"status": "queued", "idempotency_key": idem_key}
