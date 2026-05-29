"""Gateway layer: port-facing LLM client and provider adapter protocol."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from ...domain.common.contracts import LlmCallRequest
from .json_repair import decode_json_payload

_JSON_RETRIES = 2


class LLMClient(ABC):
    """Infra LLM gateway base (``complete`` / ``complete_json`` match ``LlmGateway``)."""

    @abstractmethod
    def complete(self, request: LlmCallRequest) -> str:
        raise NotImplementedError

    def complete_json(self, request: LlmCallRequest) -> Any:
        last_exc: Exception = json.JSONDecodeError("no response", "", 0)
        for _ in range(_JSON_RETRIES + 1):
            raw = self.complete(request)
            try:
                return decode_json_payload(raw)
            except json.JSONDecodeError as exc:
                last_exc = exc
        raise last_exc


class ProviderAdapter(ABC):
    @abstractmethod
    def complete(self, request: LlmCallRequest) -> str:
        raise NotImplementedError


class GatewayBackedLlmClient(LLMClient):
    """LLM client backed by a provider adapter."""

    def __init__(self, adapter: ProviderAdapter):
        self.adapter = adapter

    def complete(self, request: LlmCallRequest) -> str:
        return self.adapter.complete(request)
