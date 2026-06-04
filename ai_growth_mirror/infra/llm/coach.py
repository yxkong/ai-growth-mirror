"""Infrastructure adapter for period-level growth guidance."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...domain.growth.model import GrowthProfile
    from ...domain.common.contracts import LlmGateway

logger = logging.getLogger(__name__)

from ai_growth_mirror.assets.prompts import build_prompt_environment, normalize_report_language
from ...domain.common.contracts import (
    LlmCallRequest,
    LlmGateway,
    PromptRenderRequest,
    PromptTemplateGateway,
)
from ...domain.growth.coaching import (
    CoachingContent,
    CoachingPriority,
    CoachingTakeaway,
    parse_coaching_payload,
    priority_keys_for_coaching,
)
from ...domain.growth.diagnosis import (
    build_diagnosis_candidate_packet,
    rule_fallback_diagnosis,
)
from ...domain.growth.planning import rank_growth_priorities
from .execution import complete_json_with_retries

_COACH_RETRY_DELAYS = (2.0, 5.0)


class GrowthGuideTemplateAdapter(PromptTemplateGateway):
    """Prompt-template adapter for the growth-guide prompt bundle."""

    def render(self, request: PromptRenderRequest) -> str:
        return _render_template(request.asset_path, request.context)


def _render_template(name: str, ctx: dict[str, Any]) -> str:
    """Render a Jinja2 template from the growth guide prompt directory."""
    from jinja2 import StrictUndefined

    env = build_prompt_environment()
    env.undefined = StrictUndefined
    tmpl = env.get_template(f"growth_coach/{name}")
    return tmpl.render(**ctx)

def generate_growth_guidance(
    *,
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
    llm: "LlmGateway",
    language: str = "zh",
    tool_display_name: str = "AI Tool",
    period_label: str = "",
    trend_info: str = "",
    schema_mismatch: bool = False,
    recent_friction_snippets: list[str] | None = None,
    recent_takeaway_snippets: list[str] | None = None,
) -> Optional[CoachingContent]:
    """Call LLM to generate personalized growth guidance.

    Returns None on failure (caller falls back to rule-based content).
    The function now builds a structured Stage-1 DiagnosisCandidatePacket and
    passes it into the prompt so the LLM can perform grounded Stage-2 synthesis.
    """
    pq_dims = stats.pq_avg_dimensions or {}
    weakest_pq = min(pq_dims.items(), key=lambda kv: kv[1]) if pq_dims else ("", 0.0)
    top_friction = sorted(stats.friction_type_counts.items(), key=lambda kv: -kv[1])[:5]
    language = normalize_report_language(language)
    priority_keys = priority_keys_for_coaching(stats, capability_scores)

    # Stage-1: build ranked candidates and evidence packet
    ranked_priorities = rank_growth_priorities(
        stats,
        capability_scores,
        top_deficit_keys=tuple(
            (stats.pq_deficit_counts or {}).keys()
        )[:5],
    )
    diagnosis_packet = build_diagnosis_candidate_packet(
        stats,
        capability_scores,
        ranked_priorities,
        recent_friction_snippets=recent_friction_snippets,
        recent_takeaway_snippets=recent_takeaway_snippets,
        trend_info=trend_info,
        schema_mismatch=schema_mismatch,
    )

    ctx: dict[str, Any] = {
        "language": language,
        "report_language": language,
        "growth_level": stats.growth_level,
        "mirror_score": stats.mirror_score,
        "session_count": stats.session_count,
        "active_days": stats.active_days,
        "avg_chain": round(stats.avg_autonomous_chain_length or 0.0, 1),
        "heavy_session_count": stats.heavy_session_count,
        "tool_display_name": tool_display_name,
        "period_label": period_label,
        "capability_scores": capability_scores,
        "outcome_counts": stats.outcome_counts,
        "top_friction": top_friction,
        "pq_sessions_evaluated": stats.pq_sessions_evaluated,
        "weakest_pq_dim": weakest_pq[0],
        "weakest_pq_score": weakest_pq[1],
        "pq_avg_efficiency": stats.pq_avg_efficiency_score,
        "constraint_rate_pct": round((getattr(stats, "constraint_prompt_rate", 0.0) or 0.0) * 100),
        "context_rate_pct": round((getattr(stats, "code_context_rate", 0.0) or 0.0) * 100),
        "mcp_session_rate_pct": round((getattr(stats, "mcp_session_rate", 0.0) or 0.0) * 100),
        "subagent_session_count": getattr(stats, "subagent_session_count", 0),
        "asset_creation_signals": {
            "skill_files_authored": getattr(stats, "skill_authored_count", 0),
            "hook_config_sessions": getattr(stats, "hook_modified_session_count", 0),
            "mcp_config_sessions": getattr(stats, "mcp_authored_session_count", 0),
        },
        "skill_authored_count": getattr(stats, "skill_authored_count", 0),
        "hook_modified_session_count": getattr(stats, "hook_modified_session_count", 0),
        "mcp_authored_session_count": getattr(stats, "mcp_authored_session_count", 0),
        "priority_keys": priority_keys,
        # Stage-1 evidence packet for grounded Stage-2 synthesis
        "diagnosis_candidates": diagnosis_packet.candidates,
        "diagnosis_packet": diagnosis_packet,
    }

    prompt_adapter = GrowthGuideTemplateAdapter()
    try:
        system_prompt = prompt_adapter.render(
            PromptRenderRequest(asset_path="system.md.j2", context=ctx)
        )
        user_prompt = prompt_adapter.render(
            PromptRenderRequest(asset_path="user.md.j2", context=ctx)
        )
    except Exception as exc:
        logger.warning("coaching template render failed: %s", exc)
        return None

    try:
        raw = complete_json_with_retries(
            llm=llm,
            request=LlmCallRequest(prompt=user_prompt, system=system_prompt),
            retry_delays=_COACH_RETRY_DELAYS,
            logger=logger,
            log_context="growth-coach",
        )
        if not isinstance(raw, dict):
            logger.warning("growth guidance response was not a JSON object: %r", type(raw).__name__)
            return None
        coaching = parse_coaching_payload(raw)
        # Stage-3: if LLM didn't produce a diagnosis, fall back to rule layer
        if coaching.diagnosis is None:
            coaching.diagnosis = rule_fallback_diagnosis(diagnosis_packet)
        return coaching
    except Exception as exc:
        logger.warning("growth guidance LLM call failed: %s", exc)
        return None


