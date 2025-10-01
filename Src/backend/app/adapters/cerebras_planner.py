"""Adapter for invoking the Cerebras planning endpoint."""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.utils.http import sync_client


def chat_json(prompt: str, schema_hint: str) -> Dict[str, Any]:
    """Call the Cerebras chat completion endpoint expecting JSON output."""

    if not settings.cerebras_base_url or not settings.cerebras_api_key or not settings.cerebras_model:
        raise ExternalServiceError("Cerebras configuration is incomplete")

    url = f"{settings.cerebras_base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": settings.cerebras_model,
        "messages": [
            {"role": "system", "content": "You are a planning agent. Output ONLY valid JSON per schema."},
            {"role": "user", "content": f"Return strictly valid JSON.\nSchema hints:\n{schema_hint}\n\nTask:\n{prompt}"},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

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
    return json.loads(content)
