"""Factory for assembling gateway-backed LLM clients."""
from __future__ import annotations

from ...config import (
    normalize_provider,
    provider_default_base_url,
    provider_default_model,
    resolve_provider_api_key,
)
from .gateway import GatewayBackedLlmClient, LLMClient
from .providers.anthropic import AnthropicMessagesAdapter
from .providers.gemini import GeminiContentAdapter
from .providers.openai import OpenAIChatAdapter


def make_llm_client(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    normalized = normalize_provider(provider)
    resolved_model = model or provider_default_model(normalized)
    resolved_key = resolve_provider_api_key(normalized, explicit=api_key)
    resolved_base = base_url or provider_default_base_url(normalized) or None
    if normalized == "claude":
        return GatewayBackedLlmClient(
            AnthropicMessagesAdapter(
                model=resolved_model,
                api_key=resolved_key,
                base_url=resolved_base,
            )
        )
    if normalized == "gemini":
        return GatewayBackedLlmClient(
            GeminiContentAdapter(
                model=resolved_model,
                api_key=resolved_key,
            )
        )
    if normalized in {"openai", "openai_compatible", "deepseek", "glm"}:
        return GatewayBackedLlmClient(
            OpenAIChatAdapter(
                model=resolved_model,
                api_key=resolved_key,
                base_url=resolved_base,
            )
        )
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Choose claude, gemini, openai, deepseek, or glm."
    )
