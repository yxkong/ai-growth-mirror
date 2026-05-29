"""Google Gemini provider adapter."""
from __future__ import annotations

from ....config import resolve_provider_api_key
from ....domain.common.contracts import LlmCallRequest
from ..gateway import ProviderAdapter


class GeminiContentAdapter(ProviderAdapter):
    def __init__(self, *, model: str, api_key: str | None) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - env specific
            raise ImportError("google-generativeai required: pip install google-generativeai") from exc
        genai.configure(api_key=api_key or resolve_provider_api_key("gemini") or "")
        self.model = model
        self.model_obj = genai.GenerativeModel(model)

    def complete(self, request: LlmCallRequest) -> str:
        merged_system = (
            f"{request.cacheable_system}\n\n{request.system}".strip()
            if request.cacheable_system
            else request.system
        )
        content = f"{merged_system}\n\n{request.prompt}" if merged_system else request.prompt
        response = self.model_obj.generate_content(
            content,
            generation_config={"max_output_tokens": request.max_tokens},
        )
        return response.text
