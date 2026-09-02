"""Infrastructure adapter for cross-session work-focus synthesis."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...domain.common.contracts import LlmGateway
    from ...domain.session.model import SessionRecord
    from ...domain.signals.model import SessionRead

logger = logging.getLogger(__name__)

from ai_growth_mirror.assets.prompts import build_prompt_environment, normalize_report_language
from ...domain.common.contracts import (
    LlmCallRequest,
    LlmGateway,
    PromptRenderRequest,
    PromptTemplateGateway,
)
from .execution import complete_json_with_retries
from .privacy import sanitize_outbound_text

_WORK_FOCUS_RETRY_DELAYS = (2.0, 5.0)
_MAX_SESSION_ROWS = 40
class WorkFocusTemplateAdapter(PromptTemplateGateway):
    """Prompt-template adapter for the work-focus synthesis prompt bundle."""

    def render(self, request: PromptRenderRequest) -> str:
        return _render_template(request.asset_path, request.context)


def _render_template(name: str, ctx: dict[str, Any]) -> str:
    from jinja2 import StrictUndefined

    env = build_prompt_environment()
    env.undefined = StrictUndefined
    tmpl = env.get_template(f"work_focus/{name}")
    return tmpl.render(**ctx)


def _fallback_summary_from_prompt(session: "SessionRecord") -> str:
    text = (session.first_prompt or "").strip()
    if not text and session.top_user_messages:
        text = (session.top_user_messages[0] or "").strip()
    if not text:
        return ""
    text = sanitize_outbound_text(text, max_chars=200)
    return " ".join(text.split())


def _build_session_rows(
    sessions: list["SessionRecord"],
    session_reads: list["SessionRead"],
) -> list[dict[str, Any]]:
    read_by_session = {read.session_id: read for read in session_reads or []}
    sorted_sessions = sorted(
        sessions,
        key=lambda session: session.start_time or "",
        reverse=True,
    )[:_MAX_SESSION_ROWS]
    rows: list[dict[str, Any]] = []
    project_aliases: dict[str, str] = {}
    for session in sorted_sessions:
        read = read_by_session.get(session.session_id)
        summary = ""
        intent_mix: dict[str, int] = {}
        confidence = ""
        if read is not None:
            summary = (read.work_summary or "").strip()
            intent_mix = {
                key: int(value or 0)
                for key, value in (read.work_intent_mix or {}).items()
                if int(value or 0) > 0
            }
            confidence = (read.confidence or "").strip()
        if not summary:
            summary = _fallback_summary_from_prompt(session)
        project_key = (session.project_path or "").replace("\\", "/").casefold().strip()
        if project_key and project_key not in project_aliases:
            project_aliases[project_key] = f"project-{len(project_aliases) + 1:02d}"
        rows.append(
            {
                "project_name": project_aliases.get(project_key, ""),
                "work_summary": sanitize_outbound_text(summary, max_chars=300),
                "work_intent_mix": intent_mix,
                "confidence": confidence,
            }
        )
    return rows


def generate_work_focus_summary(
    *,
    sessions: list["SessionRecord"],
    session_reads: list["SessionRead"],
    llm: "LlmGateway",
    language: str = "zh",
) -> Optional[dict[str, Any]]:
    """Call LLM to synthesize cross-session work-focus narrative.

    Returns a dict with ``headline`` and ``recent_work`` on success, else None.
    """
    language = normalize_report_language(language)
    session_rows = _build_session_rows(sessions, session_reads)
    if not session_rows:
        return None

    ctx: dict[str, Any] = {
        "language": language,
        "report_language": language,
        "session_count": len(sessions),
        "sessions": session_rows,
    }

    prompt_adapter = WorkFocusTemplateAdapter()
    try:
        system_prompt = prompt_adapter.render(
            PromptRenderRequest(asset_path="system.md.j2", context=ctx)
        )
        user_prompt = prompt_adapter.render(
            PromptRenderRequest(asset_path="user.md.j2", context=ctx)
        )
    except Exception as exc:
        logger.warning(
            "AGM-LLM-CALL-FAILED context=work-focus-template exception_type=%s",
            type(exc).__name__,
        )
        return None

    try:
        raw = complete_json_with_retries(
            llm=llm,
            request=LlmCallRequest(prompt=user_prompt, system=system_prompt),
            retry_delays=_WORK_FOCUS_RETRY_DELAYS,
            logger=logger,
            log_context="work-focus",
        )
        if not isinstance(raw, dict):
            logger.warning(
                "AGM-LLM-RESPONSE-INVALID context=work-focus response_type=%s",
                type(raw).__name__,
            )
            return None
        headline = raw.get("headline")
        recent_work = raw.get("recent_work")
        if not isinstance(headline, str):
            return None
        if not isinstance(recent_work, list):
            return None
        return {
            "headline": headline.strip(),
            "recent_work": [item.strip() for item in recent_work if isinstance(item, str) and item.strip()],
        }
    except Exception as exc:
        logger.warning(
            "AGM-LLM-CALL-FAILED context=work-focus exception_type=%s",
            type(exc).__name__,
        )
        return None
