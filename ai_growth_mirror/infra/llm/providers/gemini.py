import logging

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
        self.last_usage = None

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
        
        # Extract and log usage
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_token_count", 0)
            candidates_tokens = getattr(usage, "candidates_token_count", 0)
            total_tokens = getattr(usage, "total_token_count", 0)
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "candidates_tokens": candidates_tokens,
                "total_tokens": total_tokens,
            }
            logging.info(
                f"Gemini API Usage for model {self.model}: "
                f"prompt_tokens={prompt_tokens}, "
                f"candidates_tokens={candidates_tokens}, "
                f"total_tokens={total_tokens}"
            )
            
        return response.text
