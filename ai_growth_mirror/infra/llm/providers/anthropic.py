"""Anthropic Messages API provider adapter."""
from __future__ import annotations

from typing import Any

from ....config import resolve_provider_api_key
from ....domain.common.contracts import LlmCallRequest
from ..execution import LLM_HTTP_TIMEOUT_SEC
from ..gateway import ProviderAdapter


def extract_anthropic_text(response: Any) -> str:
    for block in getattr(response, "content", []):
        if hasattr(block, "text"):
            return block.text
    return ""


def is_caching_unsupported_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "cache_control" in message or "prompt-caching" in message or "anthropic-beta" in message:
        return True
    if "invalid beta flag" in message or "beta flag" in message or "beta header" in message:
        return True
    return "unsupported" in message and ("system" in message or "block" in message)


class AnthropicMessagesAdapter(ProviderAdapter):
    _MIN_CACHEABLE_TOKENS = 1024
    _CHARS_PER_TOKEN = 4

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env specific
            raise ImportError("anthropic package required: pip install anthropic") from exc
        kwargs: dict[str, Any] = {
            "api_key": api_key or resolve_provider_api_key("claude"),
            "timeout": LLM_HTTP_TIMEOUT_SEC,
        }
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)
        self.model = model
        self._caching_disabled = False

    def _system_argument(self, request: LlmCallRequest) -> str | list[dict[str, Any]]:
        if not request.cacheable_system:
            return request.system
        if len(request.cacheable_system) < self._MIN_CACHEABLE_TOKENS * self._CHARS_PER_TOKEN:
            return f"{request.cacheable_system}\n\n{request.system}".strip()
        if self._caching_disabled:
            return f"{request.cacheable_system}\n\n{request.system}".strip()
        blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": request.cacheable_system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if request.system:
            blocks.append({"type": "text", "text": request.system})
        return blocks

    def complete(self, request: LlmCallRequest) -> str:
        system_argument = self._system_argument(request)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if system_argument:
            payload["system"] = system_argument
        structured_system = isinstance(system_argument, list)
        if structured_system:
            payload["extra_headers"] = {"anthropic-beta": "prompt-caching-2024-07-31"}
        try:
            response = self.client.messages.create(**payload)
        except Exception as exc:
            if structured_system and is_caching_unsupported_error(exc):
                self._caching_disabled = True
                payload["system"] = f"{request.cacheable_system}\n\n{request.system}".strip()
                payload.pop("extra_headers", None)
                response = self.client.messages.create(**payload)
            else:
                raise
        text = extract_anthropic_text(response)
        if text:
            return text
        if request.max_tokens < 16384:
            payload["max_tokens"] = 16384
            response = self.client.messages.create(**payload)
            text = extract_anthropic_text(response)
            if text:
                return text
        raise ValueError("No text block in Anthropic response.")
