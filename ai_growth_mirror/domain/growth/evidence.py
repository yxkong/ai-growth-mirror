"""Schema-versioned evidence payload for report sidecars."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..session.model import SessionRecord
from ..session.scope import SessionScope
from ..signals.model import SessionRead
from .model import GrowthProfile

EVIDENCE_SCHEMA_VERSION = "1.2"


@dataclass(frozen=True)
class CoreEvidence:
    schema_version: str
    generated_at: str
    tool_display_name: str
    date_range: dict[str, Any]
    scope_filters: dict[str, Any]
    sources_summary: dict[str, Any]
    coverage: dict[str, Any]
    stats: dict[str, Any]
    session_examples: list[dict[str, Any]] = field(default_factory=list)
    session_read_summaries: list[dict[str, Any]] = field(default_factory=list)
    agentic_evidence_graph: dict[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_plain_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return dict(value)


def _truncate_text(value: str, max_len: int) -> str:
    text = (value or "").strip()
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def clean_project_name(project_path: str) -> str:
    if not project_path:
        return ""
    
    # Normalize separators
    normalized = project_path.replace("\\", "/").strip()
    if normalized.startswith("//?/"):
        normalized = normalized[4:]
    normalized = normalized.rstrip("/")
    if not normalized:
        return ""

    # Check if there is a slash
    is_flat = "/" not in normalized
    if is_flat:
        parts = [p for p in normalized.split("-") if p]
    else:
        parts = [p for p in normalized.split("/") if p]

    # Helper to clean/strip path prefixes
    if parts:
        # Strip Windows drive letter (e.g. 'C:', 'c')
        first = parts[0]
        if (len(first) == 2 and first[1] == ':' and first[0].isalpha()) or (len(first) == 1 and first.isalpha()):
            parts = parts[1:]

    # Strip 'users' or 'home' and the immediately following element (which is the username)
    for i, part in enumerate(parts):
        if part.lower() in ("users", "home"):
            if i + 1 < len(parts):
                parts = parts[i + 2:]
            else:
                parts = parts[i + 1:]
            break

    # Reconstruct the display name
    if is_flat:
        display = "-".join(parts)
        
        # If the flat string ends with the current project name, return the current project name
        try:
            current_project = Path.cwd().name
            if current_project:
                display_lower = display.lower()
                current_lower = current_project.lower()
                if display_lower == current_lower or display_lower.endswith("-" + current_lower):
                    return current_project
        except Exception:
            pass
    else:
        # Slashed paths are always resolved to the last directory component
        display = parts[-1] if parts else ""

    if not display:
        return "project"

    display_lower = display.lower()
    
    # Redact any UUID or hash-like suffixes or pure hex values if they are the sole name
    import re
    if re.match(r"^[0-9a-f\-]{8,}$", display_lower) or re.match(r"^\d+$", display_lower):
        return "project"

    if display_lower in ("users", "home", ""):
        return "project"

    if any(k in normalized.lower() for k in ("empty-window", "var-folders", "tmp-folders")):
        return "project"

    # Final guard: case-insensitive check against local username if available
    try:
        import getpass
        username = getpass.getuser()
    except Exception:
        import os
        username = os.environ.get("USER") or os.environ.get("USERNAME") or os.environ.get("LOGNAME") or ""
        
    if username and username.lower() in display_lower:
        display = re.sub(re.escape(username), "project", display, flags=re.IGNORECASE)
        display = re.sub(r"-+", "-", display).strip("-")
        if not display or display.lower() == "project":
            return "project"

    return display



def _project_name(project_path: str) -> str:
    return clean_project_name(project_path)


def _observed_date_range(sessions: Iterable[SessionRecord]) -> str:
    starts = [session.start_time for session in sessions if session.start_time]
    ends = [session.end_time for session in sessions if session.end_time]
    if not starts:
        return ""
    start_label = min(starts)[:10]
    end_label = max(ends)[:10] if ends else max(starts)[:10]
    return f"{start_label} to {end_label}"


def _scope_payload(scope: SessionScope, *, redact: bool) -> dict[str, Any]:
    if redact:
        return {"redacted": True}
    return {
        "repos": list(scope.repos),
        "dirs": [str(path.expanduser().resolve(strict=False)) for path in scope.dirs],
        "keywords": list(scope.keywords),
    }


def _stats_payload(stats: GrowthProfile, *, redact: bool) -> dict[str, Any]:
    top_projects = [] if redact else [(_project_name(name), count) for name, count in stats.top_projects]
    return {
        "session_count": stats.session_count,
        "total_user_messages": stats.total_user_messages,
        "total_messages": stats.total_messages,
        "active_days": stats.active_days,
        "top_projects": top_projects,
        "top_languages": stats.top_languages,
        "top_tools": stats.top_tools,
        "outcome_counts": stats.outcome_counts,
        "goal_category_counts": stats.goal_category_counts,
        "friction_type_counts": stats.friction_type_counts,
        "friction_by_attribution": stats.friction_by_attribution,
        "total_files_modified": stats.total_files_modified,
        "tool_error_counts": stats.tool_error_counts,
        "advanced_feature_ratio": stats.advanced_feature_ratio,
        "tool_build_rate": stats.tool_build_rate,
        "subagent_session_rate": stats.subagent_session_rate,
        "verification_behavior_rate": stats.verification_behavior_rate,
        "code_session_count": stats.code_session_count,
        "code_verification_rate": stats.code_verification_rate,
        "test_run_rate": stats.test_run_rate,
        "heavy_session_rate": stats.heavy_session_rate,
        "avg_autonomous_chain_length": stats.avg_autonomous_chain_length,
        "max_autonomous_chain_length": stats.max_autonomous_chain_length,
        "tier_diversity_count": stats.tier_diversity_count,
        "workflow_structured_session_count": stats.workflow_structured_session_count,
        "workflow_build_substantial_count": stats.workflow_build_substantial_count,
        "workflow_build_moderate_count": stats.workflow_build_moderate_count,
        "ai_authoring_distinct_categories": stats.ai_authoring_distinct_categories,
        "constraint_prompt_rate": stats.constraint_prompt_rate,
        "code_context_rate": stats.code_context_rate,
        "avg_prompt_word_count": stats.avg_prompt_word_count,
        "unique_skill_count": stats.unique_skill_count,
        "assetized_session_rate": stats.assetized_session_rate,
        "skill_usage_session_rate": stats.skill_usage_session_rate,
        "public_framework_session_rate": stats.public_framework_session_rate,
        "local_method_framework_session_rate": stats.local_method_framework_session_rate,
        "workflow_fingerprint_session_rate": stats.workflow_fingerprint_session_rate,
        "workflow_reuse_depth": stats.workflow_reuse_depth,
        "asset_authoring_session_rate": stats.asset_authoring_session_rate,
        "human_intervention_session_count": stats.human_intervention_session_count,
        "human_intervention_session_rate": stats.human_intervention_session_rate,
        "agentic_system_score": stats.agentic_system_score,
        "growth_level": stats.growth_level,
        "mirror_score": stats.mirror_score,
        "pq_sessions_evaluated": stats.pq_sessions_evaluated,
        "pq_llm_session_count": stats.pq_llm_session_count,
        "pq_heuristic_session_count": stats.pq_heuristic_session_count,
        "pq_light_session_count": stats.pq_light_session_count,
        "pq_avg_dimensions": stats.pq_avg_dimensions,
        "pq_avg_efficiency_score": stats.pq_avg_efficiency_score,
        "pq_deficit_counts": stats.pq_deficit_counts,
        "total_cost_usd": stats.total_cost_usd,
        "avg_cost_per_session": stats.avg_cost_per_session,
        "total_input_tokens": stats.total_input_tokens,
        "total_output_tokens": stats.total_output_tokens,
        "total_cache_read_tokens": stats.total_cache_read_tokens,
        "total_cache_write_tokens": stats.total_cache_write_tokens,
        "avg_cache_hit_rate": stats.avg_cache_hit_rate,
        "mcp_session_rate": stats.mcp_session_rate,
        "mcp_session_count": stats.mcp_session_count,
        "total_subagent_invocations": stats.total_subagent_invocations,
        "agent_asset": (
            {
                "skill_files": stats.agent_asset.skill_files_count,
                "prompt_files": stats.agent_asset.prompt_files_count,
                "rule_files": stats.agent_asset.rule_files_count,
                "total_asset_files": stats.agent_asset.total_asset_files,
                "local_method_frameworks": stats.agent_asset.local_method_frameworks[:20],
            }
            if stats.agent_asset is not None
            else None
        ),
    }


def _build_session_examples(
    sessions: list[SessionRecord],
    *,
    limit: int,
    redact: bool,
) -> list[dict[str, Any]]:
    ordered = sorted(sessions, key=lambda item: item.start_time or "", reverse=True)
    rows: list[dict[str, Any]] = []
    for session in ordered[:limit]:
        rows.append(
            {
                "session_id": session.session_id,
                "tool_name": session.tool_name,
                "project": "" if redact else _project_name(session.project_path),
                "start_time": session.start_time,
                "duration_minutes": session.duration_minutes,
                "user_message_count": session.user_message_count,
                "assistant_message_count": session.assistant_message_count,
                "files_modified": session.files_modified,
                "git_commits": session.git_commits,
                "lines_added": session.lines_added,
                "lines_removed": session.lines_removed,
                "uses_subagent": session.uses_subagent,
                "uses_mcp": session.uses_mcp,
                "uses_web_search": session.uses_web_search,
                "uses_web_fetch": session.uses_web_fetch,
                "has_verification_behavior": session.has_verification_behavior,
                "has_test_commands": session.has_test_commands,
                "autonomous_chain_lengths": session.autonomous_chain_lengths[:10],
                "first_prompt": "" if redact else _truncate_text(session.first_prompt, 220),
                "top_user_messages": (
                    []
                    if redact
                    else [_truncate_text(message, 180) for message in session.top_user_messages[:5]]
                ),
            }
        )
    return rows


def _build_session_read_summaries(
    session_reads: list[SessionRead],
    session_by_id: dict[str, SessionRecord],
    *,
    limit: int,
    redact: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for session_read in session_reads[:limit]:
        session = session_by_id.get(session_read.session_id)
        rows.append(
            {
                "session_id": session_read.session_id,
                "tool_name": session_read.tool_name,
                "project": "" if redact or session is None else _project_name(session.project_path),
                "delivery_outcome": session_read.delivery_outcome,
                "support_value": session_read.support_value,
                "confidence": session_read.confidence,
                "work_intent_mix": session_read.work_intent_mix,
                "collaboration_shape": session_read.collaboration_shape,
                "session_takeaway": "" if redact else _truncate_text(session_read.session_takeaway, 260),
                "key_gain": session_read.key_gain,
                "resistance_signals": [
                    _as_plain_dict(signal) for signal in session_read.resistance_signals[:5]
                ],
                "momentum_signals": [
                    _as_plain_dict(signal) for signal in session_read.momentum_signals[:5]
                ],
            }
        )
    return rows


def build_core_evidence(
    *,
    sessions: list[SessionRecord],
    facets: list[SessionRead],
    stats: GrowthProfile,
    tool_display_name: str,
    sources_summary: dict | None = None,
    scope_filters: SessionScope | None = None,
    since_label: str = "",
    until_label: str = "",
    quality_eligible: int | None = None,
    extraction_failed: int = 0,
    redact: bool = False,
    session_example_limit: int = 25,
    session_read_summary_limit: int = 40,
    include_evidence_graph: bool = True,
) -> CoreEvidence:
    session_by_id = {session.session_id: session for session in sessions}
    scope = scope_filters or SessionScope()

    agentic_graph: dict[str, Any] | None = None
    if include_evidence_graph:
        from .evidence_graph import build_agentic_evidence_graph, evidence_graph_to_dict

        graph = build_agentic_evidence_graph(sessions, facets)
        agentic_graph = evidence_graph_to_dict(graph)

    return CoreEvidence(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        generated_at=_utc_now(),
        tool_display_name=tool_display_name,
        date_range={
            "since": since_label,
            "until": until_label,
            "observed": _observed_date_range(sessions),
        },
        scope_filters=_scope_payload(scope, redact=redact),
        sources_summary=dict(sources_summary or {}),
        coverage={
            "session_count": len(sessions),
            "session_read_count": len(facets),
            "quality_eligible": quality_eligible,
            "extraction_failed": extraction_failed,
        },
        stats=_stats_payload(stats, redact=redact),
        session_examples=_build_session_examples(
            sessions,
            limit=session_example_limit,
            redact=redact,
        ),
        session_read_summaries=_build_session_read_summaries(
            facets,
            session_by_id,
            limit=session_read_summary_limit,
            redact=redact,
        ),
        agentic_evidence_graph=agentic_graph,
    )


def core_evidence_to_dict(core: CoreEvidence) -> dict[str, Any]:
    return asdict(core)
