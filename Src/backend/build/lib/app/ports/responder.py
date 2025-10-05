"""Provider-agnostic chat response generation."""

from __future__ import annotations

from typing import Dict, List

from loguru import logger

from app.adapters import cerebras_responder, openai_responder
from app.config import settings
from app.domain.errors import ExternalServiceError


def generate_chat_response(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = 700,
) -> str:
    """Route the chat generation request to the configured LLM provider."""

    provider = (settings.llm_provider or "cerebras").lower()
    chat_impl = openai_responder.chat if provider == "openai" else cerebras_responder.chat

    try:
        return chat_impl(messages=messages, temperature=temperature, max_tokens=max_tokens)
    except ExternalServiceError as exc:
        logger.warning(
            "LLM responder unavailable; falling back to heuristic summary. reason={}",
            exc,
        )
        raise
