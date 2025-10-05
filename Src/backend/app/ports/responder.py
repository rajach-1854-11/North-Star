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

    providers = _provider_order()
    if not providers:
        raise ExternalServiceError("No LLM providers are configured")

    last_exc: ExternalServiceError | None = None

    for provider in providers:
        chat_impl = openai_responder.chat if provider == "openai" else cerebras_responder.chat
        try:
            return chat_impl(messages=messages, temperature=temperature, max_tokens=max_tokens)
        except ExternalServiceError as exc:
            logger.warning(
                "LLM provider '{}' unavailable; attempting fallback. reason={}",
                provider,
                exc,
            )
            last_exc = exc
            continue

    assert last_exc is not None
    raise last_exc


def _provider_order() -> List[str]:
    primary = (settings.llm_provider or "cerebras").lower()
    candidates: List[str] = []

    if _is_configured(primary):
        candidates.append(primary)
    else:
        logger.warning("Primary LLM provider '{}' is not fully configured.", primary)

    fallback = "openai" if primary == "cerebras" else "cerebras"
    if fallback not in candidates and _is_configured(fallback):
        candidates.append(fallback)

    return candidates


def _is_configured(provider: str) -> bool:
    provider = provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "cerebras":
        return bool(settings.cerebras_base_url and settings.cerebras_api_key and settings.cerebras_model)
    return False
