"""Deterministic privacy boundary for outbound LLM user prompts."""

from __future__ import annotations

import re
from dataclasses import replace

from ...domain.common.contracts import LlmCallRequest

REDACTED_SECRET = "<redacted-secret>"
REDACTED_PATH = "<redacted-path>"
REDACTED_EMAIL = "<redacted-email>"

_PEM_RE = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd)"
    r"\b\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
)
_EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Z]{2,}(?![\w.-])")
_UNC_PATH_RE = re.compile(r"(?m)(?<!\w)\\\\(?:[^\\\r\n]+\\)+[^\r\n]*")
_WINDOWS_PATH_RE = re.compile(r"(?m)(?<!\w)[A-Za-z]:[\\/][^\r\n]*")
_UNIX_HOME_PATH_RE = re.compile(r"(?m)(?<!\w)/(?:home|Users)/[^\r\n]*")
_TILDE_PATH_RE = re.compile(r"(?m)(?<!\w)~[\\/][^\r\n]*")


def sanitize_outbound_text(text: str | None, *, max_chars: int | None = None) -> str:
    """Redact high-risk structured values while preserving useful task semantics."""
    if not text:
        return ""
    sanitized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    sanitized = _PEM_RE.sub(REDACTED_SECRET, sanitized)
    sanitized = _BEARER_RE.sub(f"Bearer {REDACTED_SECRET}", sanitized)
    sanitized = _SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}={REDACTED_SECRET}",
        sanitized,
    )
    sanitized = _EMAIL_RE.sub(REDACTED_EMAIL, sanitized)
    sanitized = _UNC_PATH_RE.sub(REDACTED_PATH, sanitized)
    sanitized = _WINDOWS_PATH_RE.sub(REDACTED_PATH, sanitized)
    sanitized = _UNIX_HOME_PATH_RE.sub(REDACTED_PATH, sanitized)
    sanitized = _TILDE_PATH_RE.sub(REDACTED_PATH, sanitized)
    sanitized = "".join(
        character
        for character in sanitized
        if character in "\n\t" or ord(character) >= 32
    )
    if max_chars is not None:
        return sanitized[: max(0, max_chars)]
    return sanitized


def sanitize_llm_request(request: LlmCallRequest) -> LlmCallRequest:
    """Return a request whose user prompt has crossed the privacy boundary."""
    return replace(request, prompt=sanitize_outbound_text(request.prompt))


__all__ = [
    "REDACTED_EMAIL",
    "REDACTED_PATH",
    "REDACTED_SECRET",
    "sanitize_llm_request",
    "sanitize_outbound_text",
]
