"""Adapter for invoking the OpenAI chat completion endpoint for narrative responses."""

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
    """Invoke OpenAI's chat completions API and return the assistant message content."""

    if not settings.openai_api_key:
        raise ExternalServiceError("OpenAI configuration is incomplete (missing API key)")

    url = f"{(settings.openai_base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
    payload: Dict[str, object] = {
        "model": settings.openai_model or "gpt-5",
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.8,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    with sync_client(timeout=120) as client:
        response = client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"OpenAI request failed: {exc.response.status_code}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as exc:
            raise ExternalServiceError("OpenAI returned an unexpected payload") from exc

    return (content or "").strip()
