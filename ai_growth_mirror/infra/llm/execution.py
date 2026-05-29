"""Shared retry and limiter orchestration for LLM JSON calls."""
from __future__ import annotations

import logging
import time
from typing import Any

from ...domain.common.contracts import LlmGateway
from ...domain.common.contracts import LlmCallRequest
from .limiter import ProviderExecutionPolicy, is_rate_limit_error, is_transient_error

# Per HTTP call; session-read jobs may chain session_read + prompt_lens.
LLM_HTTP_TIMEOUT_SEC = 120.0
# Per pending session worker (session read + optional prompt lens).
FACET_SESSION_TIMEOUT_SEC = 360.0


def complete_json_with_retries(
    *,
    llm: LlmGateway,
    request: LlmCallRequest,
    retry_delays: tuple[float, ...] = (),
    limiter: ProviderExecutionPolicy | None = None,
    logger: logging.Logger | None = None,
    log_context: str = "llm-json",
) -> Any:
    """Execute a JSON LLM request with shared transient retry semantics."""
    last_exc: Exception | None = None
    for attempt, delay in enumerate((*retry_delays, None), start=1):
        try:
            if limiter is not None:
                limiter.acquire()
            try:
                raw = llm.complete_json(request)
            finally:
                if limiter is not None:
                    limiter.release()
            if limiter is not None:
                limiter.on_success()
            return raw
        except Exception as exc:
            last_exc = exc
            if limiter is not None and is_rate_limit_error(exc):
                limiter.on_429()
            if delay is not None and is_transient_error(exc):
                if logger is not None:
                    logger.debug(
                        "Transient LLM failure for %s, retrying in %.0fs (attempt %d): %s",
                        log_context,
                        delay,
                        attempt,
                        exc,
                    )
                time.sleep(delay)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"LLM request for {log_context} exited without a result")
