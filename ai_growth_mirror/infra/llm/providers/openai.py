"""OpenAI-compatible chat completions provider adapter."""
from __future__ import annotations

from typing import Any

from ....config import resolve_provider_api_key
from ....domain.common.contracts import LlmCallRequest
from ..execution import LLM_HTTP_TIMEOUT_SEC
from ..gateway import ProviderAdapter


def is_json_mode_unsupported(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("response_format", "json_object", "400", "422", "unsupported")
    )


class OpenAIChatAdapter(ProviderAdapter):
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - env specific
            raise ImportError("openai package required: pip install openai") from exc
        kwargs: dict[str, Any] = {
            "api_key": api_key or resolve_provider_api_key("openai"),
            "timeout": LLM_HTTP_TIMEOUT_SEC,
        }
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self._json_mode = True

    def complete(self, request: LlmCallRequest) -> str:
        merged_system = (
            f"{request.cacheable_system}\n\n{request.system}".strip()
            if request.cacheable_system
            else request.system
        )
        messages: list[dict[str, str]] = []
        if merged_system:
            messages.append({"role": "system", "content": merged_system})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = self.client.chat.completions.create(**payload)
        except Exception as exc:
            if self._json_mode and is_json_mode_unsupported(exc):
                self._json_mode = False
                payload.pop("response_format", None)
                response = self.client.chat.completions.create(**payload)
            else:
                raise
        return response.choices[0].message.content or ""
