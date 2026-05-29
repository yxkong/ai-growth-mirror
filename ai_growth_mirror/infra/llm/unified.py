"""Legacy unified client wrapper used by tests and small integration points."""
from __future__ import annotations

from typing import Any

from .json_repair import LLMResponse, repair_json


class UnifiedLLMClient:
    """Tiny adapter used by tests and small integration points."""

    def __init__(self, delegate: Any):
        self._delegate = delegate

    def complete_json(self, *, system: str, user: str, model: str, provider: str) -> LLMResponse:
        raw = self._delegate(system=system, user=user, model=model, provider=provider)
        parsed, levels = repair_json(raw)
        return LLMResponse(text=raw, parsed_json=parsed, repair_levels_used=levels)
