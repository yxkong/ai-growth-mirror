"""Growth scoring and profile aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import median
from typing import Optional

from ..session.model import SessionRecord
from ..signals.framework import detect_frameworks
from ..signals.model import SessionRead
from .costs import cache_hit_rate
from .model import AgentAssetStats, GrowthGap, GrowthProfile, GrowthStage, RadarAxis

MIN_SESSIONS_HARD = 5
MIN_SESSIONS_WARN = 15
MIN_SESSION_READS_FOR_MIRROR_SCORE = 5

_CODE_LANGUAGES = frozenset(
    {
        "Python",
        "TypeScript",
        "JavaScript",
        "Go",
        "Rust",
        "Java",
        "Ruby",
        "C#",
        "C++",
        "C",
        "Shell",
        "SQL",
        "Swift",
        "Kotlin",
        "PHP",
        "Scala",
        "Elixir",
        "Clojure",
        "Haskell",
        "Lua",
        "Perl",
        "R",
    }
)
_IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}
_SKIPPED_TOOL_NAMES = frozenset({"", "unknown"})


def _is_code_session(session: SessionRecord) -> bool:
    return bool(set(session.languages) & _CODE_LANGUAGES)


def _safe_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _session_local_days(session: SessionRecord) -> set[str]:
    observed_days: set[str] = set()
    for stamp in session.user_message_timestamps:
        parsed = _safe_iso_datetime(stamp)
        if parsed is not None:
            observed_days.add(parsed.astimezone().strftime("%Y-%m-%d"))
    if not observed_days:
        parsed = _safe_iso_datetime(session.start_time)
        if parsed is not None:
            observed_days.add(parsed.astimezone().strftime("%Y-%m-%d"))
    return observed_days


def _project_key(project_path: str) -> str:
    if not project_path:
        return ""
    normalized = project_path.replace("\\", "/").rstrip("/")
    if normalized.startswith("//?/"):
        normalized = normalized[4:]
    return normalized.rsplit("/", 1)[-1]


def _increment_map(target: dict[str, int], key: str, amount: int = 1) -> None:
    if key:
        target[key] = target.get(key, 0) + amount


def _rank_counter(counter: Counter, limit: int) -> list[tuple[str, int]]:
    return counter.most_common(limit)


def _aggregate_prompt_quality(stats: GrowthProfile, session_reads: list[SessionRead]) -> None:
    from ..signals.taxonomy import PQ_DIMENSIONS

    prompt_lens_reads = [read for read in session_reads if read.prompt_lens is not None]
    stats.pq_sessions_evaluated = len(prompt_lens_reads)
    if not prompt_lens_reads:
        return

    stats.pq_llm_session_count = sum(
        1 for read in prompt_lens_reads if getattr(read.prompt_lens, "source", "") == "llm"
    )
    stats.pq_heuristic_session_count = sum(
        1 for read in prompt_lens_reads if getattr(read.prompt_lens, "source", "") == "heuristic"
    )
    stats.pq_light_session_count = sum(
        1 for read in prompt_lens_reads if getattr(read.prompt_lens, "coverage", "") == "light"
    )

    status_of = lambda read: getattr(read.prompt_lens, "evaluation_status", "")
    stats.pq_llm_evaluated_count = sum(
        1 for read in prompt_lens_reads if status_of(read) == "llm_evaluated"
    )
    stats.pq_insufficient_count = sum(
        1 for read in prompt_lens_reads if status_of(read) == "insufficient_input"
    )
    stats.pq_llm_failed_count = sum(
        1 for read in prompt_lens_reads if status_of(read) == "llm_failed"
    )
    stats.pq_llm_unavailable_count = sum(
        1 for read in prompt_lens_reads if status_of(read) == "llm_unavailable"
    )

    stats.pq_avg_dimensions = {
        dimension: round(
            sum(getattr(read.prompt_lens, dimension) for read in prompt_lens_reads)
            / len(prompt_lens_reads),
            1,
        )
        for dimension in PQ_DIMENSIONS
    }
    stats.pq_avg_efficiency_score = round(
        sum(read.prompt_lens.efficiency_score for read in prompt_lens_reads)
        / len(prompt_lens_reads),
        1,
    )

    deficits: dict[str, int] = {}
    ranked_takeaways: list[tuple[object, str]] = []
    for read in prompt_lens_reads:
        impact_by_category = {
            finding.category: finding.impact for finding in read.prompt_lens.findings
        }
        for finding in read.prompt_lens.findings:
            if finding.type != "strength":
                _increment_map(deficits, finding.category)
        for takeaway in read.prompt_lens.takeaways:
            ranked_takeaways.append((takeaway, impact_by_category.get(takeaway.category, "medium")))
    stats.pq_deficit_counts = deficits
    ranked_takeaways.sort(
        key=lambda item: (
            0 if item[0].type == "improve" else 1,
            _IMPACT_RANK.get(item[1], 1),
        )
    )
    stats.pq_top_takeaways = [takeaway for takeaway, _ in ranked_takeaways[:4]]


def _soft_threshold(value: float, lo: float, hi: float, max_pts: float) -> float:
    if value <= lo:
        return 0.0
    if value >= hi:
        return max_pts
    return max_pts * (value - lo) / (hi - lo)


def _bounded_average(*weighted_values: tuple[float, float]) -> float:
    total_weight = sum(weight for _value, weight in weighted_values) or 1.0
    total_score = sum(
        max(0.0, min(100.0, value)) * weight for value, weight in weighted_values
    )
    return round(total_score / total_weight, 1)


def _compute_growth_level(
    *,
    avg_chain: float,
    verification_rate: float,
    heavy_session_rate: float,
    heavy_session_count: int,
    total_token_volume: int,
    mcp_session_rate: float,
    subagent_session_rate: float,
    total_subagent_invocations: int,
    web_session_rate: float,
    tool_build_rate: float,
    unique_skill_count: int,
    tier_diversity: int,
    distinct_tool_count: int,
    distinct_model_count: int,
    workflow_build_substantial_count: int,
    workflow_build_moderate_count: int,
    ai_authoring_distinct_categories: int,
    fully_achieved_rate: float,
    workflow_structured_count: int,
    session_count: int,
    skill_authored_count: int,
    hook_modified_session_count: int,
    mcp_authored_session_count: int,
    assetized_session_rate: float,
    constraint_prompt_rate: float = 0.0,
    code_context_rate: float = 0.0,
    prompt_dimensions: dict[str, float] | None = None,
    test_run_rate: float = 0.0,
    code_verification_rate: float = 0.0,
    commit_rate: float = 0.0,
    total_files_modified: int = 0,
    friction_by_attribution: dict[str, int] | None = None,
) -> tuple[str, int, dict[str, float]]:
    prompt_dimensions = prompt_dimensions or {}
    friction_by_attribution = friction_by_attribution or {}

    structured_rate = workflow_structured_count / max(session_count, 1)
    user_actionable = float(friction_by_attribution.get("user-actionable", 0))
    friction_total = float(sum(friction_by_attribution.values()))
    user_actionable_ratio = user_actionable / friction_total if friction_total else 0.0
    files_per_session = total_files_modified / max(session_count, 1)

    intent_clarity = _bounded_average(
        (constraint_prompt_rate * 100.0, 0.28),
        (code_context_rate * 100.0, 0.24),
        (prompt_dimensions.get("request_specificity", 50.0), 0.26),
        (
            (
                prompt_dimensions.get("context_provision", 50.0)
                + prompt_dimensions.get("scope_management", 50.0)
            )
            / 2.0,
            0.22,
        ),
    )
    execution_driving = _bounded_average(
        (_soft_threshold(avg_chain, 1.5, 8.0, 100.0), 0.32),
        (_soft_threshold(heavy_session_rate, 0.10, 0.40, 100.0), 0.18),
        (
            max(
                _soft_threshold(subagent_session_rate, 0.0, 0.18, 100.0),
                _soft_threshold(float(total_subagent_invocations), 0.0, 18.0, 100.0),
            ),
            0.16,
        ),
        (_soft_threshold(float(tier_diversity), 2.0, 5.0, 100.0), 0.18),
        (structured_rate * 100.0, 0.16),
    )
    implementation_depth = _bounded_average(
        (_soft_threshold(files_per_session, 0.5, 3.0, 100.0), 0.32),
        (_soft_threshold(float(total_token_volume), 500_000.0, 12_000_000.0, 100.0), 0.18),
        (code_verification_rate * 100.0, 0.20),
        (fully_achieved_rate * 100.0, 0.15),
        (_soft_threshold(float(total_files_modified), 3.0, 40.0, 100.0), 0.15),
    )
    delivery_closure = _bounded_average(
        (fully_achieved_rate * 100.0, 0.42),
        (verification_rate * 100.0, 0.24),
        (test_run_rate * 100.0, 0.18),
        (commit_rate * 100.0, 0.08),
        (code_verification_rate * 100.0, 0.08),
    )
    adaptive_recovery = _bounded_average(
        (prompt_dimensions.get("correction_quality", 50.0), 0.34),
        (fully_achieved_rate * 100.0, 0.20),
        (verification_rate * 100.0, 0.18),
        ((1.0 - user_actionable_ratio) * 100.0, 0.14),
        (structured_rate * 100.0, 0.14),
    )

    tool_bonus = _bounded_average(
        (_soft_threshold(mcp_session_rate, 0.0, 0.20, 100.0), 0.20),
        (_soft_threshold(web_session_rate, 0.0, 0.20, 100.0), 0.12),
        (_soft_threshold(tool_build_rate, 0.0, 0.20, 100.0), 0.18),
        (
            _soft_threshold(
                float(skill_authored_count + mcp_authored_session_count + hook_modified_session_count),
                0.0,
                8.0,
                100.0,
            ),
            0.13,
        ),
        (_soft_threshold(float(ai_authoring_distinct_categories), 0.0, 3.0, 100.0), 0.12),
        (_soft_threshold(float(distinct_tool_count), 1.0, 3.0, 100.0), 0.25),
        (_soft_threshold(float(distinct_model_count), 1.0, 3.0, 100.0), 0.20),
    )
    workflow_bonus = _bounded_average(
        (structured_rate * 100.0, 0.34),
        (_soft_threshold(float(unique_skill_count), 0.0, 4.0, 100.0), 0.16),
        (
            _soft_threshold(
                float(workflow_build_substantial_count + workflow_build_moderate_count),
                0.0,
                5.0,
                100.0,
            ),
            0.16,
        ),
        (_soft_threshold(assetized_session_rate, 0.05, 0.35, 100.0), 0.12),
        (_soft_threshold(float(skill_authored_count), 0.0, 5.0, 100.0), 0.10),
        (_soft_threshold(float(mcp_authored_session_count), 0.0, 3.0, 100.0), 0.06),
        (_soft_threshold(float(hook_modified_session_count), 0.0, 3.0, 100.0), 0.06),
    )
    tool_leverage_bonus = min(tool_bonus / 25.0, 4.0)
    workflow_maturity_bonus = min(workflow_bonus / 33.0, 3.0)

    weakest_axis = min(
        intent_clarity,
        execution_driving,
        implementation_depth,
        delivery_closure,
        adaptive_recovery,
    )
    consistency_modifier = 0.0
    if weakest_axis >= 65.0:
        consistency_modifier += 2.0
    elif weakest_axis < 40.0:
        consistency_modifier -= 3.0

    total_score = (
        intent_clarity * 0.20
        + execution_driving * 0.22
        + implementation_depth * 0.22
        + delivery_closure * 0.22
        + adaptive_recovery * 0.14
        + tool_leverage_bonus
        + workflow_maturity_bonus
        + consistency_modifier
    )
    score = max(0, min(100, round(total_score)))
    if session_count < 8 and score > 69:
        score = 69
    elif session_count < 15 and score > 82:
        score = 82

    if score >= 90:
        level = "L5"
    elif score >= 75:
        level = "L4"
    elif score >= 56:
        level = "L3"
    elif score >= 38:
        level = "L2"
    else:
        level = "L1"

    return level, score, {
        "intent_clarity": round(intent_clarity, 1),
        "execution_driving": round(execution_driving, 1),
        "implementation_depth": round(implementation_depth, 1),
        "delivery_closure": round(delivery_closure, 1),
        "adaptive_recovery": round(adaptive_recovery, 1),
    }


def _axis_status(score: float) -> str:
    if score < 45.0:
        return "weak"
    if score < 65.0:
        return "unstable"
    if score < 82.0:
        return "solid"
    return "strong"


def _axis_confidence(stats: GrowthProfile) -> float:
    return round(min(1.0, max(0.35, stats.session_count / 24.0)), 2)


def _build_radar_axes(stats: GrowthProfile) -> list[RadarAxis]:
    confidence = _axis_confidence(stats)
    keys = [
        "intent_clarity",
        "execution_driving",
        "implementation_depth",
        "delivery_closure",
        "adaptive_recovery",
    ]
    axes: list[RadarAxis] = []
    for key in keys:
        score = round((stats.agentic_sub_scores or {}).get(key, 0.0), 1)
        axes.append(
            RadarAxis(
                key=key,
                label="",
                score=score,
                status=_axis_status(score),
                short_reason="",
                confidence=confidence,
            )
        )
    return axes


def _build_gap_rankings(stats: GrowthProfile) -> list[GrowthGap]:
    axes = {axis.key: axis.score for axis in stats.radar_axes}
    candidates = [
        ("framing_gap", 100.0 - axes.get("intent_clarity", 0.0)),
        ("workflow_composition_gap", 100.0 - axes.get("execution_driving", 0.0)),
        ("code_penetration_gap", 100.0 - axes.get("implementation_depth", 0.0)),
        (
            "verification_gap",
            100.0
            - ((axes.get("delivery_closure", 0.0) * 0.65) + stats.verification_behavior_rate * 35.0),
        ),
        ("closure_gap", 100.0 - axes.get("delivery_closure", 0.0)),
        ("debug_recovery_gap", 100.0 - axes.get("adaptive_recovery", 0.0)),
    ]
    ranked: list[GrowthGap] = []
    for rank, (key, severity) in enumerate(
        sorted(candidates, key=lambda item: item[1], reverse=True)[:4],
        start=1,
    ):
        ranked.append(
            GrowthGap(
                key=key,
                label="",
                severity=round(severity, 1),
                rank=rank,
                evidence_summary="",
                why_it_happens="",
                suggested_action="",
            )
        )
    return ranked


def _build_growth_stage(stats: GrowthProfile) -> GrowthStage | None:
    if not stats.growth_level:
        return None
    strongest_axis = max(stats.radar_axes, key=lambda axis: axis.score).key if stats.radar_axes else ""
    primary_gap = stats.gap_rankings[0].key if stats.gap_rankings else ""
    return GrowthStage(
        level=stats.growth_level,
        label="",
        summary="",
        strongest_axis=strongest_axis,
        primary_gap=primary_gap,
        next_breakthrough="",
    )


def _populate_session_basics(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    stats.session_count = len(sessions)
    stats.total_user_messages = sum(session.user_message_count for session in sessions)
    stats.total_messages = stats.total_user_messages + sum(
        session.assistant_message_count for session in sessions
    )
    stats.total_files_modified = sum(session.files_modified for session in sessions)

    active_days: set[str] = set()
    for session in sessions:
        active_days.update(_session_local_days(session))
    stats.active_days = len(active_days)


def _populate_rankings(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    tool_counts = Counter()
    language_counts = Counter()
    project_counts = Counter()
    error_counts = Counter()

    for session in sessions:
        tool_counts.update(session.tool_counts)
        language_counts.update(session.languages)
        error_counts.update(session.tool_error_categories)
        project = _project_key(session.project_path)
        if project:
            project_counts[project] += 1

    for skipped in _SKIPPED_TOOL_NAMES:
        tool_counts.pop(skipped, None)
    stats.top_tools = _rank_counter(tool_counts, 8)
    stats.top_languages = _rank_counter(language_counts, 6)
    stats.top_projects = _rank_counter(project_counts, 8)
    stats.tool_error_counts = dict(_rank_counter(error_counts, 6))


def _populate_time_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    hour_counts = [0] * 24
    weekday_counts = [0] * 7
    for session in sessions:
        observed_hour = False
        for hour in session.message_hours:
            if 0 <= hour < 24:
                hour_counts[hour] += 1
                observed_hour = True
        if not observed_hour:
            fallback = _safe_iso_datetime(session.start_time)
            if fallback is not None:
                hour_counts[fallback.astimezone().hour] += 1

        for day_label in _session_local_days(session):
            try:
                weekday_counts[datetime.strptime(day_label, "%Y-%m-%d").weekday()] += 1
            except Exception:
                continue
    stats.messages_by_hour = hour_counts
    stats.weekday_session_counts = weekday_counts


def _populate_read_signals(stats: GrowthProfile, session_reads: list[SessionRead]) -> None:
    valid_reads = [read for read in session_reads if not getattr(read, "extraction_failed", False)]
    for read in valid_reads:
        for category, count in read.work_intent_mix.items():
            _increment_map(stats.goal_category_counts, category, count)
        _increment_map(stats.outcome_counts, read.delivery_outcome)
        for signal in read.resistance_signals:
            _increment_map(stats.friction_type_counts, signal.category)
            _increment_map(stats.friction_by_attribution, signal.attribution)

    _aggregate_prompt_quality(stats, session_reads)


def _populate_session_friction(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    for session in sessions:
        if session.tool_errors > 0:
            _increment_map(stats.friction_type_counts, "tool-ceiling", session.tool_errors)
            _increment_map(
                stats.friction_by_attribution,
                "environmental",
                session.tool_errors,
            )


def _populate_costs_and_cache(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    total_cost = sum(
        session.total_cost_usd for session in sessions if session.total_cost_usd is not None
    )
    stats.total_cost_usd = round(total_cost, 4)
    sessions_with_cost = sum(1 for session in sessions if session.total_cost_usd is not None)
    if sessions_with_cost:
        stats.avg_cost_per_session = round(total_cost / sessions_with_cost, 4)

    stats.total_input_tokens = sum(
        session.input_tokens for session in sessions if session.input_tokens is not None
    )
    stats.total_output_tokens = sum(
        session.output_tokens for session in sessions if session.output_tokens is not None
    )
    stats.total_cache_read_tokens = sum(
        session.cache_read_tokens for session in sessions if session.cache_read_tokens is not None
    )
    stats.total_cache_write_tokens = sum(
        session.cache_write_tokens for session in sessions if session.cache_write_tokens is not None
    )

    hit_rates = [
        cache_hit_rate(
            session.cache_read_tokens,
            session.input_tokens,
            session.cache_write_tokens,
        )
        for session in sessions
        if session.cache_read_tokens and session.input_tokens
    ]
    usable_hit_rates = [value for value in hit_rates if value is not None]
    if usable_hit_rates:
        stats.avg_cache_hit_rate = round(sum(usable_hit_rates) / len(usable_hit_rates), 4)


def _populate_duration_and_rhythm(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    durations = [session.duration_minutes for session in sessions if session.duration_minutes is not None]
    if not durations:
        return
    stats.avg_session_duration_minutes = round(sum(durations) / len(durations), 1)
    stats.median_session_duration_minutes = round(median(durations), 1)
    burst_sessions = sum(1 for duration in durations if duration <= 20)
    deep_sessions = sum(1 for duration in durations if duration >= 45)
    if burst_sessions / len(durations) >= 0.6:
        stats.collaboration_rhythm_type = "burst"
    elif deep_sessions / len(durations) >= 0.4:
        stats.collaboration_rhythm_type = "deep_focus"
    else:
        stats.collaboration_rhythm_type = "balanced"


def _populate_session_capabilities(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    stats.tool_diversity_index = float(len({tool for session in sessions for tool in session.tool_counts}))
    advanced_sessions = sum(
        1
        for session in sessions
        if session.uses_mcp
        or session.uses_subagent
        or session.uses_web_search
        or session.uses_web_fetch
        or session.skill_invocation_count > 0
    )
    if stats.session_count:
        stats.advanced_feature_ratio = round(advanced_sessions / stats.session_count, 4)

    skill_sessions = sum(1 for session in sessions if session.skill_invocation_count > 0)
    if stats.session_count:
        stats.tool_build_rate = round(skill_sessions / stats.session_count, 4)
    skill_counter = Counter(
        skill
        for session in sessions
        for skill in session.unique_skills_used
    )
    stats.unique_skill_count = len(skill_counter)
    assetized_sessions = sum(
        1
        for session in sessions
        if session.skill_invocation_count > 0
        or session.skill_files_authored > 0
        or session.hook_config_modified
        or session.mcp_server_authored
    )
    if stats.session_count:
        stats.assetized_session_rate = round(assetized_sessions / stats.session_count, 4)

    committed_sessions = sum(1 for session in sessions if session.git_commits > 0)
    if stats.session_count:
        stats.commit_rate = round(committed_sessions / stats.session_count, 4)

    session_peaks = [
        max(session.autonomous_chain_lengths)
        for session in sessions
        if session.autonomous_chain_lengths
    ]
    if session_peaks:
        stats.avg_autonomous_chain_length = round(sum(session_peaks) / len(session_peaks), 1)
        stats.max_autonomous_chain_length = max(session_peaks)

    verified_sessions = sum(1 for session in sessions if session.has_verification_behavior)
    tested_sessions = sum(1 for session in sessions if session.has_test_commands)
    if stats.session_count:
        stats.verification_behavior_rate = round(verified_sessions / stats.session_count, 4)
        stats.test_run_rate = round(tested_sessions / stats.session_count, 4)

    heavy_sessions = sum(1 for session in sessions if sum(session.tool_counts.values()) >= 15)
    stats.heavy_session_count = heavy_sessions
    if stats.session_count:
        stats.heavy_session_rate = round(heavy_sessions / stats.session_count, 4)

    subagent_sessions = sum(1 for session in sessions if session.uses_subagent)
    stats.subagent_session_count = subagent_sessions
    if stats.session_count:
        stats.subagent_session_rate = round(subagent_sessions / stats.session_count, 4)
    stats.total_subagent_invocations = sum(
        session.subagent_invocation_count for session in sessions
    )

    mcp_sessions = sum(1 for session in sessions if session.uses_mcp)
    web_sessions = sum(1 for session in sessions if session.uses_web_search or session.uses_web_fetch)
    stats.mcp_session_count = mcp_sessions
    stats.web_session_count = web_sessions
    if stats.session_count:
        stats.mcp_session_rate = round(mcp_sessions / stats.session_count, 4)
        stats.web_session_rate = round(web_sessions / stats.session_count, 4)

    stats.skill_authored_count = sum(session.skill_files_authored for session in sessions)
    stats.hook_modified_session_count = sum(
        1 for session in sessions if session.hook_config_modified
    )
    stats.mcp_authored_session_count = sum(
        1 for session in sessions if session.mcp_server_authored
    )
    stats.tier_diversity_count = len(
        {
            tier
            for session in sessions
            for tier, count in session.tool_tier_counts.items()
            if count > 0
        }
    )
    stats.distinct_tool_count = len({session.tool_name for session in sessions if session.tool_name})
    stats.distinct_model_count = len(
        {model for session in sessions for model in session.models_used if model}
    )
    stats.total_token_volume = (
        stats.total_input_tokens
        + stats.total_output_tokens
        + stats.total_cache_read_tokens
        + stats.total_cache_write_tokens
    )


def _populate_workflow_read_signals(stats: GrowthProfile, session_reads: list[SessionRead]) -> None:
    seen_categories: set[str] = set()
    for read in session_reads:
        if getattr(read, "extraction_failed", False):
            continue
        if read.capability_focus and read.capability_focus != "none":
            seen_categories.add(read.capability_focus)
            if read.capability_depth == "substantial":
                stats.workflow_build_substantial_count += 1
            elif read.capability_depth == "moderate":
                stats.workflow_build_moderate_count += 1

        if read.work_style == "plan_driven":
            stats.workflow_plan_session_count += 1
            stats.workflow_structured_session_count += 1
        elif read.work_style == "spec_driven":
            stats.workflow_spec_session_count += 1
            stats.workflow_structured_session_count += 1
        elif read.work_style == "tdd":
            stats.workflow_tdd_session_count += 1
            stats.workflow_structured_session_count += 1
        elif read.work_style in {"adaptive", "method_guided"}:
            stats.workflow_structured_session_count += 1
        elif read.work_style == "exploratory":
            stats.workflow_vibe_session_count += 1
    stats.ai_authoring_distinct_categories = len(seen_categories)


def _populate_framework_fingerprints(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    framework_counter = Counter()
    for session in sessions:
        for match in detect_frameworks(session):
            framework_counter[match.framework.name] += 1
    stats.top_workflow_frameworks = framework_counter.most_common(8)


def _populate_prompt_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    constrained = sum(1 for session in sessions if session.prompt_has_constraint)
    code_context = sum(1 for session in sessions if session.prompt_has_code_context)
    prompt_lengths = [session.prompt_word_count for session in sessions if session.prompt_word_count > 0]
    if stats.session_count:
        stats.constraint_prompt_rate = round(constrained / stats.session_count, 4)
        stats.code_context_rate = round(code_context / stats.session_count, 4)
    if prompt_lengths:
        stats.avg_prompt_word_count = round(sum(prompt_lengths) / len(prompt_lengths), 1)


def _populate_code_session_metrics(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    code_sessions = [session for session in sessions if _is_code_session(session)]
    stats.code_session_count = len(code_sessions)
    if code_sessions:
        verified = sum(1 for session in code_sessions if session.has_verification_behavior)
        stats.code_verification_rate = round(verified / len(code_sessions), 4)


def _apply_asset_floor(stats: GrowthProfile) -> None:
    agent_asset = getattr(stats, "agent_asset", None)
    if agent_asset is None or not agent_asset.has_data:
        return
    if (
        agent_asset.skill_files_count >= 10
        and stats.workflow_build_substantial_count == 0
        and stats.workflow_build_moderate_count < 3
    ):
        stats.workflow_build_moderate_count = 3
    if agent_asset.skill_files_count >= 30:
        stats.workflow_build_substantial_count = max(stats.workflow_build_substantial_count, 1)
    if agent_asset.skill_files_count >= 60:
        stats.workflow_build_substantial_count = max(stats.workflow_build_substantial_count, 3)


def _valid_session_reads(session_reads: list[SessionRead]) -> list[SessionRead]:
    return [read for read in session_reads if not getattr(read, "extraction_failed", False)]


def _score_profile(stats: GrowthProfile, session_reads: list[SessionRead]) -> None:
    valid_reads = _valid_session_reads(session_reads)
    weighted_outcome_total = sum(stats.outcome_counts.values())
    if weighted_outcome_total:
        fully_achieved_rate = (
            stats.outcome_counts.get("fully_achieved", 0)
            + 0.7 * stats.outcome_counts.get("mostly_achieved", 0)
            + 0.3 * stats.outcome_counts.get("partially_achieved", 0)
        ) / weighted_outcome_total
    else:
        fully_achieved_rate = 0.0
    stats.fully_achieved_rate = round(fully_achieved_rate, 4)

    enough_data = stats.session_count >= 2 or len(valid_reads) >= MIN_SESSION_READS_FOR_MIRROR_SCORE
    if not enough_data:
        return

    verification_rate = (
        stats.code_verification_rate
        if stats.code_session_count >= 5
        else stats.verification_behavior_rate
    )
    _apply_asset_floor(stats)
    (
        stats.growth_level,
        stats.mirror_score,
        stats.agentic_sub_scores,
    ) = _compute_growth_level(
        avg_chain=stats.avg_autonomous_chain_length,
        verification_rate=verification_rate,
        heavy_session_rate=stats.heavy_session_rate,
        heavy_session_count=stats.heavy_session_count,
        total_token_volume=stats.total_token_volume,
        mcp_session_rate=stats.mcp_session_rate,
        subagent_session_rate=stats.subagent_session_rate,
        total_subagent_invocations=stats.total_subagent_invocations,
        web_session_rate=stats.web_session_rate,
        tool_build_rate=stats.tool_build_rate,
        unique_skill_count=stats.unique_skill_count,
        tier_diversity=stats.tier_diversity_count,
        distinct_tool_count=stats.distinct_tool_count,
        distinct_model_count=stats.distinct_model_count,
        workflow_build_substantial_count=stats.workflow_build_substantial_count,
        workflow_build_moderate_count=stats.workflow_build_moderate_count,
        ai_authoring_distinct_categories=stats.ai_authoring_distinct_categories,
        fully_achieved_rate=fully_achieved_rate,
        workflow_structured_count=stats.workflow_structured_session_count,
        session_count=stats.session_count,
        skill_authored_count=stats.skill_authored_count,
        hook_modified_session_count=stats.hook_modified_session_count,
        mcp_authored_session_count=stats.mcp_authored_session_count,
        assetized_session_rate=stats.assetized_session_rate,
        constraint_prompt_rate=stats.constraint_prompt_rate,
        code_context_rate=stats.code_context_rate,
        prompt_dimensions=stats.pq_avg_dimensions,
        test_run_rate=stats.test_run_rate,
        code_verification_rate=stats.code_verification_rate,
        commit_rate=stats.commit_rate,
        total_files_modified=stats.total_files_modified,
        friction_by_attribution=stats.friction_by_attribution,
    )
    stats.radar_axes = _build_radar_axes(stats)
    stats.gap_rankings = _build_gap_rankings(stats)
    stats.growth_stage = _build_growth_stage(stats)


def aggregate(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    tool_name: str = "all",
    agent_asset: Optional[AgentAssetStats] = None,
) -> GrowthProfile:
    stats = GrowthProfile(tool_name=tool_name)
    if agent_asset is not None:
        stats.agent_asset = agent_asset
    if not sessions:
        return stats

    _populate_session_basics(stats, sessions)
    _populate_rankings(stats, sessions)
    _populate_time_signals(stats, sessions)
    _populate_read_signals(stats, session_reads)
    _populate_session_friction(stats, sessions)
    _populate_costs_and_cache(stats, sessions)
    _populate_duration_and_rhythm(stats, sessions)
    _populate_session_capabilities(stats, sessions)
    _populate_workflow_read_signals(stats, session_reads)
    _populate_framework_fingerprints(stats, sessions)
    _populate_prompt_signals(stats, sessions)
    _populate_code_session_metrics(stats, sessions)
    _score_profile(stats, session_reads)
    return stats
