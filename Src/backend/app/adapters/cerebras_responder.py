"""Adapter for invoking the Cerebras chat completion endpoint for narrative responses."""

from __future__ import annotations

from typing import Dict, List

import httpx

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.utils.http import sync_client


def chat(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = 700,
) -> str:
    """Invoke the Cerebras chat completions API and return the assistant message content."""

    if not settings.cerebras_base_url or not settings.cerebras_api_key or not settings.cerebras_model:
        raise ExternalServiceError("Cerebras configuration is incomplete")

    base = settings.cerebras_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    url = f"{base}/v1/chat/completions"
    payload: Dict[str, object] = {
        "model": settings.cerebras_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }

    with sync_client(timeout=120) as client:
        response = client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Cerebras request failed: {exc.response.status_code}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as exc:
            raise ExternalServiceError("Cerebras returned an unexpected payload") from exc

    return (content or "").strip()
