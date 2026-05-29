"""Shared immutable contracts used across domain/application boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PromptRenderRequest:
    """Structured prompt render input shared by prompt assets."""

    asset_path: str
    context: dict[str, Any]


@dataclass(frozen=True)
class LlmCallRequest:
    """Provider-neutral text generation request."""

    prompt: str
    system: str = ""
    max_tokens: int = 4096
    cacheable_system: str = ""


class LlmGateway(Protocol):
    """LLM completion contract; infra ``LLMClient`` implements this structurally."""

    def complete(self, request: LlmCallRequest) -> str: ...

    def complete_json(self, request: LlmCallRequest) -> Any: ...


class PromptTemplateGateway(Protocol):
    """Prompt render contract for growth-coach and session-analysis templates."""

    def render(self, request: PromptRenderRequest) -> str: ...
