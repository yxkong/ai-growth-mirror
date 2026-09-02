"""Growth scoring and profile aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import median
from typing import Optional

from ..session.model import SessionRecord
from ..signals.framework import detect_frameworks, detect_local_method_frameworks, normalize_method_name
from ..signals.model import SessionRead
from .assessment import AssessmentInputs, AssessmentResult, assess_growth
from .assessment_policy import LEVEL_MIN_SCORES
from .costs import cache_hit_rate
from .model import AgentAssetStats, GrowthGap, GrowthProfile, GrowthStage, RadarAxis

MIN_SESSIONS_HARD = 5
MIN_SESSIONS_WARN = 15
MIN_SESSION_READS_FOR_MIRROR_SCORE = 5

# Canonical L1–L5 score boundaries (single source of truth for assignment + UI).
_LEVEL_ORDER = tuple(LEVEL_MIN_SCORES)


def growth_level_from_score(score: int) -> str:
    """Map mirror_score to L1–L5 using canonical boundaries."""
    bounded = max(0, min(100, int(score)))
    for level in reversed(_LEVEL_ORDER):
        if bounded >= LEVEL_MIN_SCORES[level]:
            return level
    return "L1"


def format_growth_level_score_range(level: str) -> str:
    """Return inclusive score range string for a level, e.g. ``'56-74'`` for L3."""
    if level not in LEVEL_MIN_SCORES:
        return ""
    idx = _LEVEL_ORDER.index(level)
    low = LEVEL_MIN_SCORES[level]
    high = (LEVEL_MIN_SCORES[_LEVEL_ORDER[idx + 1]] - 1) if idx < len(_LEVEL_ORDER) - 1 else 100
    return f"{low}-{high}"

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

    indexed_demoted = {"missing-context", "vague-request"}
    corrected_dimensions: dict[str, float] = {}
    for dimension in PQ_DIMENSIONS:
        values: list[float] = []
        for read in prompt_lens_reads:
            value = float(getattr(read.prompt_lens, dimension))
            findings = getattr(read.prompt_lens, "findings", []) or []
            deficit_keys = {
                finding.category
                for finding in findings
                if getattr(finding, "type", "") != "strength"
            }
            if dimension in {"context_provision", "request_specificity"} and getattr(read, "prompt_style", "") in {"indexed_prompt", "mixed_prompt"}:
                if deficit_keys & indexed_demoted:
                    value = max(value, 58.0)
            values.append(value)
        corrected_dimensions[dimension] = round(sum(values) / len(values), 1) if values else 0.0
    stats.pq_avg_dimensions = corrected_dimensions
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


def _goal_locking_speed_score(turns: Optional[int]) -> float:
    if turns is None:
        return 100.0
    if turns <= 3:
        return 100.0
    if turns >= 10:
        return 0.0
    return round(100.0 * (10 - turns) / 7.0, 1)


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
    direction_clarity_rate: float = 0.0,
    context_grounding_rate: float = 0.0,
    goal_locking_speed: float = 0.0,
    prompt_dimensions: dict[str, float] | None = None,
    test_run_rate: float = 0.0,
    code_verification_rate: float = 0.0,
    commit_rate: float = 0.0,
    total_files_modified: int = 0,
    friction_by_attribution: dict[str, int] | None = None,
    asset_maturity_bonus: float = 0.0,
    advanced_feature_ratio: float = 0.0,
    skill_usage_session_rate: float = 0.0,
    workflow_fingerprint_session_rate: float = 0.0,
    workflow_reuse_depth: int = 0,
    asset_authoring_session_rate: float = 0.0,
    has_token_data: bool = True,
    active_clarification_rate: float = 0.0,
    effective_contract_rate: float = 0.0,
    contract_compliance_rate: float = 0.0,
    contract_compliance_denominator: int = 0,
    goal_locking_evidence_count: int = 0,
    clarification_opportunity_count: int = 0,
    recovery_opportunity_count: int | None = None,
) -> tuple[str, int, dict[str, float]]:
    result = _assess_legacy_metrics(locals())
    scores = {axis.key: axis.score for axis in result.axes if axis.score is not None}
    return result.growth_level or "", result.mirror_score or 0, scores


def _assess_legacy_metrics(values: dict) -> AssessmentResult:
    """Translate existing aggregates into the canonical assessment policy.

    Raw consumption and ecosystem counts are accepted for API stability and
    context reporting, but intentionally never enter a scored observation.
    """
    sessions = max(0, int(values["session_count"]))
    structured_rate = values["workflow_structured_count"] / max(sessions, 1)
    files_per_session = values["total_files_modified"] / max(sessions, 1)
    friction = values.get("friction_by_attribution") or {}
    recovery_opportunities = values.get("recovery_opportunity_count")
    if recovery_opportunities is None:
        recovery_opportunities = int(sum(friction.values()))
    outcome_binding = max(values["fully_achieved_rate"], values["verification_rate"])
    delegation_evidence = int(values.get("delegation_evidence_count") or 0)
    clarification_evidence = int(values.get("clarification_evidence_count") or 0)
    recovery_success_evidence = int(values.get("recovery_success_evidence_count") or 0)
    correction_evidence = int(values.get("correction_evidence_count") or 0)

    return assess_growth(
        AssessmentInputs(
            session_count=sessions,
            effective_contract_rate=values["effective_contract_rate"],
            context_grounding_rate=values["context_grounding_rate"],
            goal_locking_score=(
                values["goal_locking_speed"]
                if values["goal_locking_evidence_count"] > 0
                else None
            ),
            goal_locking_evidence_count=values["goal_locking_evidence_count"],
            active_clarification_rate=(
                values["active_clarification_rate"]
                if clarification_evidence > 0
                else None
            ),
            clarification_opportunity_count=values["clarification_opportunity_count"],
            clarification_evidence_count=clarification_evidence,
            autonomous_chain_score=_soft_threshold(values["avg_chain"], 1.5, 8.0, 100.0),
            structured_workflow_rate=structured_rate,
            verified_continuation_rate=values["verification_rate"],
            delegation_success_rate=(
                values.get("delegation_success_rate") if delegation_evidence else None
            ),
            delegation_evidence_count=delegation_evidence,
            implementation_session_rate=values.get("implementation_session_rate"),
            code_verification_rate=values["code_verification_rate"],
            fully_achieved_rate=values["fully_achieved_rate"],
            files_per_session=files_per_session,
            verification_rate=values["verification_rate"],
            test_run_rate=values["test_run_rate"],
            contract_compliance_rate=(
                values["contract_compliance_rate"]
                if values["contract_compliance_denominator"] > 0
                else None
            ),
            contract_compliance_denominator=values["contract_compliance_denominator"],
            recovery_success_rate=(
                values.get("recovery_success_rate")
                if recovery_success_evidence > 0
                else None
            ),
            recovery_opportunity_count=recovery_opportunities,
            recovery_success_evidence_count=recovery_success_evidence,
            correction_quality=values.get("correction_quality"),
            correction_evidence_count=correction_evidence,
            post_friction_verification_rate=(
                values.get("post_friction_verification_rate")
                if recovery_opportunities > 0
                else None
            ),
            skill_outcome_rate=values["skill_usage_session_rate"] * outcome_binding,
            workflow_outcome_rate=values["workflow_fingerprint_session_rate"] * outcome_binding,
            structured_outcome_rate=structured_rate * outcome_binding,
            workflow_reuse_depth=values["workflow_reuse_depth"],
            asset_authoring_outcome_rate=values["asset_authoring_session_rate"] * outcome_binding,
            assetized_outcome_rate=values["assetized_session_rate"] * outcome_binding,
            advanced_feature_outcome_rate=values["advanced_feature_ratio"] * outcome_binding,
            method_saturation=min(1.0, values["workflow_fingerprint_session_rate"]) * outcome_binding,
            total_token_volume=values["total_token_volume"],
            total_files_modified=values["total_files_modified"],
            distinct_tool_count=values["distinct_tool_count"],
            distinct_model_count=values["distinct_model_count"],
            total_subagent_invocations=values["total_subagent_invocations"],
            commit_rate=values["commit_rate"],
        )
    )


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
    keys = [
        "collaboration_framing",
        "execution_driving",
        "implementation_depth",
        "delivery_closure",
        "adaptive_recovery",
        "agentic_system",
    ]
    sub_scores = stats.agentic_sub_scores or {}
    assessment_by_key = {axis.key: axis for axis in stats.axis_assessments}
    pq_evaluated = max(0, stats.pq_sessions_evaluated)
    has_outcome_signals = (
        stats.workflow_build_substantial_count
        + stats.workflow_build_moderate_count
        + (stats.avg_autonomous_chain_length or 0.0)
    ) > 0 or bool(stats.top_tools)
    axes: list[RadarAxis] = []
    for key in keys:
        assessment = assessment_by_key.get(key)
        score = round(
            assessment.score if assessment and assessment.score is not None else sub_scores.get(key, 0.0),
            1,
        )
        # Per-axis evidence rules: PQ-driven axes need PQ-evaluated sessions;
        # action-driven axes need at least some recorded tool/workflow signals.
        if assessment is not None:
            axis_has_data = assessment.score is not None
        elif key == "collaboration_framing":
            axis_has_data = pq_evaluated > 0
        elif key == "agentic_system":
            axis_has_data = "agentic_system" in sub_scores and stats.session_count > 0
        else:
            axis_has_data = stats.session_count > 0 and (
                pq_evaluated > 0 or has_outcome_signals
            )
        # Final guard: if the score is exactly zero and nothing else supports it,
        # treat as no-data so the UI shows "—" instead of fabricating "0.0".
        if axis_has_data and score == 0.0 and not has_outcome_signals and pq_evaluated == 0:
            axis_has_data = False
        axes.append(
            RadarAxis(
                key=key,
                label="",
                score=score,
                status=_axis_status(score),
                short_reason="",
                confidence=(assessment.confidence if assessment else _axis_confidence(stats)),
                has_data=axis_has_data,
                coverage=(assessment.coverage if assessment else 0.0),
                components=(
                    [
                        {
                            "key": component.key,
                            "weight": component.weight,
                            "normalized_weight": component.normalized_weight,
                            "value": component.observation.value,
                            "available": component.observation.available,
                            "evidence_count": component.observation.evidence_count,
                            "confidence": component.observation.confidence,
                            "contribution": component.contribution,
                            "reason_codes": list(component.observation.reason_codes),
                        }
                        for component in assessment.components
                    ]
                    if assessment
                    else []
                ),
                reason_codes=list(assessment.reason_codes) if assessment else [],
            )
        )
    return axes


def _build_gap_rankings(stats: GrowthProfile) -> list[GrowthGap]:
    axes = {axis.key: axis.score for axis in stats.radar_axes}
    active_keys = {axis.key for axis in stats.radar_axes if axis.has_data}

    candidates = []
    if "agentic_system" in active_keys:
        candidates.append(("agentic_system_gap", 100.0 - axes.get("agentic_system", 0.0)))
    if "collaboration_framing" in active_keys:
        candidates.append(("framing_gap", 100.0 - axes.get("collaboration_framing", 0.0)))
    if "execution_driving" in active_keys:
        candidates.append(("workflow_composition_gap", 100.0 - axes.get("execution_driving", 0.0)))
    if "implementation_depth" in active_keys:
        candidates.append(("code_penetration_gap", 100.0 - axes.get("implementation_depth", 0.0)))
    if "delivery_closure" in active_keys:
        candidates.append((
            "verification_gap",
            100.0
            - ((axes.get("delivery_closure", 0.0) * 0.65) + stats.verification_behavior_rate * 35.0),
        ))
        candidates.append(("closure_gap", 100.0 - axes.get("delivery_closure", 0.0)))
    if "adaptive_recovery" in active_keys:
        candidates.append(("debug_recovery_gap", 100.0 - axes.get("adaptive_recovery", 0.0)))

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
    active_count = sum(1 for read in valid_reads if getattr(read, "active_clarification", False))
    stats.active_clarification_count = active_count
    if valid_reads:
        stats.active_clarification_rate = round(active_count / len(valid_reads), 4)
    else:
        stats.active_clarification_rate = 0.0

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
    # Only include sessions with real (non-estimated) token data in cost/token aggregation.
    real_sessions = [s for s in sessions if not getattr(s, "tokens_estimated", False)]

    total_cost = sum(
        session.total_cost_usd for session in real_sessions if session.total_cost_usd is not None
    )
    stats.total_cost_usd = round(total_cost, 4)
    sessions_with_cost = sum(1 for session in real_sessions if session.total_cost_usd is not None)
    if sessions_with_cost:
        stats.avg_cost_per_session = round(total_cost / sessions_with_cost, 4)

    stats.total_input_tokens = sum(
        session.input_tokens for session in real_sessions if session.input_tokens is not None
    )
    stats.total_output_tokens = sum(
        session.output_tokens for session in real_sessions if session.output_tokens is not None
    )
    stats.total_cache_read_tokens = sum(
        session.cache_read_tokens for session in real_sessions if session.cache_read_tokens is not None
    )
    stats.total_cache_write_tokens = sum(
        session.cache_write_tokens for session in real_sessions if session.cache_write_tokens is not None
    )

    hit_rates = [
        cache_hit_rate(
            session.cache_read_tokens,
            session.input_tokens,
            session.cache_write_tokens,
        )
        for session in real_sessions
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
    local_counter = Counter()
    local_methods = _local_method_frameworks(stats)
    for session in sessions:
        for match in detect_frameworks(session):
            framework_counter[match.framework.name] += 1
        for name in detect_local_method_frameworks(session, local_methods):
            local_counter[name] += 1
    stats.top_workflow_frameworks = framework_counter.most_common(8)
    stats.top_local_method_frameworks = local_counter.most_common(8)


def _populate_agentic_system_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    usage_sessions = 0
    framework_sessions = 0
    public_framework_sessions = 0
    local_method_sessions = 0
    asset_authoring_sessions = 0
    human_intervention_sessions = 0
    reusable_method_counter = Counter()
    local_methods = _local_method_frameworks(stats)
    for session in sessions:
        skill_refs = _normalized_method_refs(session.unique_skills_used or [])
        slash_refs = _normalized_method_refs(session.slash_commands or [])
        framework_refs = [match.framework.name.lower() for match in detect_frameworks(session)]
        local_framework_refs = list(detect_local_method_frameworks(session, local_methods))
        if session.skill_invocation_count > 0 or skill_refs or slash_refs:
            usage_sessions += 1
        if framework_refs:
            public_framework_sessions += 1
        if local_framework_refs:
            local_method_sessions += 1
        if framework_refs or local_framework_refs:
            framework_sessions += 1
        if session.skill_files_authored > 0 or session.hook_config_modified or session.mcp_server_authored:
            asset_authoring_sessions += 1
        if session.user_interruptions >= 2:
            human_intervention_sessions += 1
        for name in set(skill_refs + [f"/{item}" for item in slash_refs] + framework_refs + local_framework_refs):
            reusable_method_counter[name] += 1

    if stats.session_count:
        stats.skill_usage_session_rate = round(usage_sessions / stats.session_count, 4)
        stats.public_framework_session_rate = round(public_framework_sessions / stats.session_count, 4)
        stats.local_method_framework_session_rate = round(local_method_sessions / stats.session_count, 4)
        stats.workflow_fingerprint_session_rate = round(framework_sessions / stats.session_count, 4)
        stats.asset_authoring_session_rate = round(asset_authoring_sessions / stats.session_count, 4)
        stats.human_intervention_session_rate = round(human_intervention_sessions / stats.session_count, 4)
    stats.human_intervention_session_count = human_intervention_sessions
    stats.workflow_reuse_depth = sum(1 for count in reusable_method_counter.values() if count >= 2)


def _local_method_frameworks(stats: GrowthProfile) -> list[str]:
    agent_asset = getattr(stats, "agent_asset", None)
    if agent_asset is None:
        return []
    return list(getattr(agent_asset, "local_method_frameworks", []) or [])


def _normalized_method_refs(values: list[str] | tuple[str, ...]) -> list[str]:
    return [normalized for item in values if (normalized := normalize_method_name(item))]


def _populate_prompt_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    constrained = sum(1 for session in sessions if session.prompt_has_constraint)
    code_context = sum(1 for session in sessions if session.prompt_has_code_context)
    prompt_lengths = [session.prompt_word_count for session in sessions if session.prompt_word_count > 0]
    if stats.session_count:
        stats.constraint_prompt_rate = round(constrained / stats.session_count, 4)
        stats.code_context_rate = round(code_context / stats.session_count, 4)
    if prompt_lengths:
        stats.avg_prompt_word_count = round(sum(prompt_lengths) / len(prompt_lengths), 1)


def _populate_task_contract_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    source_counter = Counter()
    explicit_count = 0
    effective_count = 0
    skill_count = 0
    agent_derived_count = 0
    late_count = 0
    compliant_count = 0
    missing_count = 0

    for session in sessions:
        sources = list(getattr(session, "task_contract_sources", []) or [])
        for source in sources:
            source_counter[source] += 1
        if "explicit_user" in sources:
            explicit_count += 1
        if any(source in sources for source in ("skill_read", "workflow_rule", "attached_skill")):
            skill_count += 1
        if "agent_derived" in sources:
            agent_derived_count += 1
        if getattr(session, "pre_execution_contract_present", False):
            effective_count += 1
        if getattr(session, "late_contract_correction", False) or "late_user" in sources:
            late_count += 1
        if getattr(session, "agent_contract_compliance", "") == "met":
            compliant_count += 1
        if "missing" in sources or getattr(session, "acceptance_contract_source", "") == "missing":
            missing_count += 1

    stats.task_contract_source_counts = dict(source_counter)
    if stats.session_count:
        stats.explicit_contract_rate = round(explicit_count / stats.session_count, 4)
        stats.effective_contract_rate = round(effective_count / stats.session_count, 4)
        stats.skill_contract_rate = round(skill_count / stats.session_count, 4)
        stats.agent_derived_contract_rate = round(agent_derived_count / stats.session_count, 4)
        stats.late_contract_correction_rate = round(late_count / stats.session_count, 4)
        stats.contract_compliance_denominator = effective_count
        if effective_count > 0:
            stats.contract_compliance_rate = round(compliant_count / effective_count, 4)
        else:
            stats.contract_compliance_rate = 0.0
        stats.contract_missing_rate = round(missing_count / stats.session_count, 4)


def _populate_advanced_feature_signals(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    feature_counter = Counter()
    for session in sessions:
        for feature in getattr(session, "advanced_features", []) or []:
            feature_counter[feature] += 1
    stats.advanced_feature_counts = dict(feature_counter)


def _populate_code_session_metrics(stats: GrowthProfile, sessions: list[SessionRecord]) -> None:
    code_sessions = [session for session in sessions if _is_code_session(session)]
    stats.code_session_count = len(code_sessions)
    if code_sessions:
        verified = sum(1 for session in code_sessions if session.has_verification_behavior)
        stats.code_verification_rate = round(verified / len(code_sessions), 4)


def _valid_session_reads(session_reads: list[SessionRead]) -> list[SessionRead]:
    return [read for read in session_reads if not getattr(read, "extraction_failed", False)]


def _delivery_outcome_score(read: SessionRead) -> Optional[float]:
    return {
        "fully_achieved": 1.0,
        "mostly_achieved": 0.7,
        "partially_achieved": 0.3,
        "ongoing": 0.0,
    }.get(read.delivery_outcome)


def _score_profile(stats: GrowthProfile, session_reads: list[SessionRead], sessions: list[SessionRecord]) -> None:
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
    read_by_id = {r.session_id: r for r in valid_reads}
    session_by_id = {session.session_id: session for session in sessions}
    locking_speeds = []
    for s in sessions:
        if s.turns_until_first_file_write is not None:
            turns = s.turns_until_first_file_write
            if (
                getattr(s, "pre_write_read_count", 0) > 0
                and getattr(s, "pre_write_non_read_tool_count", 0) == 0
            ):
                turns = min(turns, 3)
            read = read_by_id.get(s.session_id)
            if read and getattr(read, "active_clarification", False):
                turns = max(1, turns - 1)
            locking_speeds.append(_goal_locking_speed_score(turns))
    goal_locking_speed = sum(locking_speeds) / len(locking_speeds) if locking_speeds else 0.0
    clarification_ids = {
        session.session_id for session in sessions if session.user_message_count > 1
    }
    clarification_reads = [read_by_id[item] for item in clarification_ids if item in read_by_id]
    clarification_rate = (
        sum(bool(read.active_clarification) for read in clarification_reads)
        / len(clarification_reads)
        if clarification_reads
        else None
    )

    delegation_ids = {session.session_id for session in sessions if session.uses_subagent}
    delegation_outcomes = [
        score
        for item in delegation_ids
        if (read := read_by_id.get(item)) is not None
        if (score := _delivery_outcome_score(read)) is not None
    ]

    recovery_ids = {
        session.session_id
        for session in sessions
        if session.tool_errors > 0 or session.user_interruptions > 0
    }
    recovery_ids.update(read.session_id for read in valid_reads if read.resistance_signals)
    recovery_outcomes = [
        score
        for item in recovery_ids
        if (read := read_by_id.get(item)) is not None
        if (score := _delivery_outcome_score(read)) is not None
    ]
    recovery_corrections = [
        float(read_by_id[item].prompt_lens.correction_quality)
        for item in recovery_ids
        if item in read_by_id and read_by_id[item].prompt_lens is not None
    ]
    post_friction_sessions = [session_by_id[item] for item in recovery_ids if item in session_by_id]
    post_friction_verification_rate = (
        sum(
            bool(session.has_verification_behavior or session.has_test_commands)
            for session in post_friction_sessions
        )
        / len(post_friction_sessions)
        if post_friction_sessions
        else None
    )
    implementation_session_rate = (
        sum(session.files_modified > 0 for session in sessions) / len(sessions)
        if sessions
        else None
    )
    values = {
        "avg_chain": stats.avg_autonomous_chain_length,
        "verification_rate": verification_rate,
        "heavy_session_rate": stats.heavy_session_rate,
        "heavy_session_count": stats.heavy_session_count,
        "total_token_volume": stats.total_token_volume,
        "mcp_session_rate": stats.mcp_session_rate,
        "subagent_session_rate": stats.subagent_session_rate,
        "total_subagent_invocations": stats.total_subagent_invocations,
        "web_session_rate": stats.web_session_rate,
        "tool_build_rate": stats.tool_build_rate,
        "unique_skill_count": stats.unique_skill_count,
        "tier_diversity": stats.tier_diversity_count,
        "distinct_tool_count": stats.distinct_tool_count,
        "distinct_model_count": stats.distinct_model_count,
        "workflow_build_substantial_count": stats.workflow_build_substantial_count,
        "workflow_build_moderate_count": stats.workflow_build_moderate_count,
        "ai_authoring_distinct_categories": stats.ai_authoring_distinct_categories,
        "fully_achieved_rate": fully_achieved_rate,
        "workflow_structured_count": stats.workflow_structured_session_count,
        "session_count": stats.session_count,
        "skill_authored_count": stats.skill_authored_count,
        "hook_modified_session_count": stats.hook_modified_session_count,
        "mcp_authored_session_count": stats.mcp_authored_session_count,
        "assetized_session_rate": stats.assetized_session_rate,
        "direction_clarity_rate": stats.constraint_prompt_rate,
        "context_grounding_rate": stats.code_context_rate,
        "goal_locking_speed": goal_locking_speed,
        "prompt_dimensions": stats.pq_avg_dimensions,
        "test_run_rate": stats.test_run_rate,
        "code_verification_rate": stats.code_verification_rate,
        "commit_rate": stats.commit_rate,
        "total_files_modified": stats.total_files_modified,
        "friction_by_attribution": stats.friction_by_attribution,
        "asset_maturity_bonus": 0.0,
        "advanced_feature_ratio": stats.advanced_feature_ratio,
        "skill_usage_session_rate": stats.skill_usage_session_rate,
        "workflow_fingerprint_session_rate": stats.workflow_fingerprint_session_rate,
        "workflow_reuse_depth": stats.workflow_reuse_depth,
        "asset_authoring_session_rate": stats.asset_authoring_session_rate,
        "has_token_data": any(s.input_tokens is not None for s in sessions),
        "active_clarification_rate": clarification_rate,
        "effective_contract_rate": stats.effective_contract_rate,
        "contract_compliance_rate": stats.contract_compliance_rate,
        "contract_compliance_denominator": stats.contract_compliance_denominator,
        "goal_locking_evidence_count": len(locking_speeds),
        "clarification_opportunity_count": len(clarification_ids),
        "clarification_evidence_count": len(clarification_reads),
        "delegation_success_rate": (
            sum(delegation_outcomes) / len(delegation_outcomes)
            if delegation_outcomes
            else None
        ),
        "delegation_evidence_count": len(delegation_outcomes),
        "implementation_session_rate": implementation_session_rate,
        "recovery_opportunity_count": len(recovery_ids),
        "recovery_success_rate": (
            sum(recovery_outcomes) / len(recovery_outcomes)
            if recovery_outcomes
            else None
        ),
        "recovery_success_evidence_count": len(recovery_outcomes),
        "correction_quality": (
            sum(recovery_corrections) / len(recovery_corrections)
            if recovery_corrections
            else None
        ),
        "correction_evidence_count": len(recovery_corrections),
        "post_friction_verification_rate": post_friction_verification_rate,
    }
    assessment = _assess_legacy_metrics(values)
    stats.growth_level = assessment.growth_level or ""
    stats.mirror_score = assessment.mirror_score or 0
    stats.agentic_sub_scores = {
        axis.key: axis.score for axis in assessment.axes if axis.score is not None
    }
    stats.assessment_policy_version = assessment.policy_version
    stats.axis_assessments = list(assessment.axes)
    stats.agentic_system_score = round(stats.agentic_sub_scores.get("agentic_system", 0.0), 1)
    stats.goal_locking_speed = round(goal_locking_speed, 1)
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
    _populate_agentic_system_signals(stats, sessions)
    _populate_prompt_signals(stats, sessions)
    _populate_task_contract_signals(stats, sessions)
    _populate_advanced_feature_signals(stats, sessions)
    _populate_code_session_metrics(stats, sessions)
    _score_profile(stats, session_reads, sessions)
    return stats
