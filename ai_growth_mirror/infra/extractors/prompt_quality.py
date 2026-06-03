"""LLM-based prompt-lens extractor.

Extracts a 5-dimension score plus deficit/strength findings and concrete
before/after takeaways for a single session. LLM judgement is used when the
session has enough material; otherwise callers should fall back to heuristic
proxy scoring so the downstream prompt-lens chain remains continuous.

The two-template split (`prompt_lens/system.md.j2` + `prompt_lens/user.md.j2`) routes the long
static rubric through Anthropic ephemeral prompt caching, so per-session
cost is dominated by the short variable user block.
"""
from __future__ import annotations

import logging
from typing import Optional

from jinja2 import Environment

from ...domain.session.model import SessionRecord
from ...domain.common.contracts import LlmGateway
from ...domain.common.contracts import LlmCallRequest
from ...domain.signals.model import PromptLensScores
from ...domain.signals.payloads import parse_prompt_lens_payload
from ...assets.prompts import build_prompt_environment, normalize_report_language
from ...domain.signals.taxonomy import PQ_DIMENSIONS
from ..llm.execution import complete_json_with_retries

logger = logging.getLogger(__name__)

# Sessions below this threshold lack enough user-side material for the rubric
# to score reliably; callers should use heuristic proxy scoring instead of
# making an LLM call.
MIN_USER_MESSAGES_FOR_PQ = 5

_PROMPT_LENS_SYSTEM_PROMPT_CACHE: dict[str, str] = {}
_PQ_RETRY_DELAYS = (2.0, 5.0)


def _jinja_env() -> Environment:
    return build_prompt_environment()


def _prompt_lens_system_prompt(env: Environment, *, report_language: str = "zh") -> str:
    lang = normalize_report_language(report_language)
    cached = _PROMPT_LENS_SYSTEM_PROMPT_CACHE.get(lang)
    if cached is None:
        cached = env.get_template("prompt_lens/system.md.j2").render(
            report_language=lang,
        )
        _PROMPT_LENS_SYSTEM_PROMPT_CACHE[lang] = cached
    return cached


def _format_user_messages(meta: SessionRecord) -> str:
    if not meta.top_user_messages:
        return "(no user messages captured)"
    return "\n".join(
        f"User#{i+1}: {msg}" for i, msg in enumerate(meta.top_user_messages)
    )


def should_extract_prompt_lens(meta: SessionRecord) -> bool:
    """Whether this session is rich enough for semantic prompt-lens analysis."""
    if meta.user_message_count >= MIN_USER_MESSAGES_FOR_PQ:
        return True
    indexed_prompt = bool(meta.unique_skills_used or meta.slash_commands or meta.skill_invocation_count > 0)
    return indexed_prompt and meta.user_message_count >= 1 and meta.assistant_message_count >= 3


def extract_prompt_lens(
    meta: SessionRecord,
    llm: LlmGateway,
    *,
    outcome: str = "",
    had_course_correction: bool = False,
    language: str = "zh",
) -> Optional[PromptLensScores]:
    """Run the prompt-lens LLM call and parse the response.

    Returns None when the session is below the user-message gate or when the
    LLM call/parse fails (logged at WARNING; caller may fall back to heuristic
    proxy scoring and retry LLM analysis on the next run).

    `language` controls the natural-language output fields (description,
    label, takeaway prose) — pass "zh" for Chinese reports, "en" otherwise.
    The `original` / `better_prompt` fields are exempt and follow the user's
    own message language regardless of report locale.
    """
    if not should_extract_prompt_lens(meta):
        return None

    language = normalize_report_language(language)
    env = _jinja_env()
    system_prompt = _prompt_lens_system_prompt(env, report_language=language)
    user_tmpl = env.get_template("prompt_lens/user.md.j2")
    prompt = user_tmpl.render(
        tool_display_name=meta.tool_name.replace("_", " ").title(),
        project_path=meta.project_path,
        duration_minutes=meta.duration_minutes,
        user_message_count=meta.user_message_count,
        assistant_message_count=meta.assistant_message_count,
        outcome=outcome,
        had_course_correction=had_course_correction,
        numbered_user_messages=_format_user_messages(meta),
        language=language,
        report_language=language,
    )

    try:
        raw = complete_json_with_retries(
            llm=llm,
            request=LlmCallRequest(
                prompt=prompt,
                cacheable_system=system_prompt,
                max_tokens=4096,
            ),
            retry_delays=_PQ_RETRY_DELAYS,
            logger=logger,
            log_context=f"prompt-lens:{meta.tool_name}/{meta.session_id}",
        )
    except Exception as e:
        logger.warning(
            "Prompt-lens extraction failed for %s/%s: %s",
            meta.tool_name, meta.session_id, e,
        )
        return None

    if not isinstance(raw, dict):
        logger.warning(
            "Prompt-lens response was not a JSON object for %s/%s: %r",
            meta.tool_name, meta.session_id, type(raw).__name__,
        )
        return None

    return parse_prompt_lens_payload(raw)


__all__ = [
    "MIN_USER_MESSAGES_FOR_PQ",
    "PQ_DIMENSIONS",
    "extract_prompt_lens",
    "should_extract_prompt_lens",
]

