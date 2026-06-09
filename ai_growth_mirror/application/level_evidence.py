"""Application-owned Level Evidence section assembly."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.growth.model import GrowthProfile
from ..domain.growth.scorer import MIN_SESSION_READS_FOR_MIRROR_SCORE
from .label_catalogs import ReportLabelCatalogs


@dataclass
class LevelEvidenceMetricView:
    label: str
    current_value: str
    target_value: str
    status: str
    explanation: str
    raw_signal: str
    kind: str = "axis"


@dataclass
class LevelEvidenceSectionView:
    headline: str
    verdict: str
    blockers: list[str] = field(default_factory=list)
    metrics: list[LevelEvidenceMetricView] = field(default_factory=list)
    next_step: str = ""
    current_level: str = ""
    target_level: str = ""
    target_caption: str = ""
    blocker_title: str = ""
    progress_summary: str = ""
    source_note: str = ""
    methodology_title: str = ""
    methodology_lines: list[str] = field(default_factory=list)


_CAPABILITY_ORDER = [
    "collaboration_framing",
    "execution_driving",
    "implementation_depth",
    "delivery_closure",
    "adaptive_recovery",
    "agentic_system",
]

_LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}


def _view_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.view_model


def _level_name(level_num: int) -> str:
    return f"L{max(1, min(level_num, 5))}"


def _mirror_methodology(catalogs: ReportLabelCatalogs) -> tuple[str, list[str]]:
    methodology = _view_i18n(catalogs).get("methodology", {})
    return methodology.get("title", ""), methodology.get("lines", [])


def _build_agentic_current_value(
    *,
    templates: dict,
    score: int,
    skill_usage_rate: int,
    public_framework_rate: int,
    local_method_rate: int,
    workflow_fingerprint_rate: int,
    workflow_reuse_depth: int,
    asset_authoring_rate: int,
    advanced_feature_rate: int,
    has_asset_roots: bool,
    raw_local_method_rate: float = 0.0,
    raw_fingerprint_rate: float = 0.0,
) -> str:
    """Build the agentic system current-value string (i18n-driven).

    When fingerprint rates round to 0% but raw values are positive, show a
    "< 1%" label instead of the misleading detection-gap note. When truly 0 but
    assets exist, show an explanatory note about detection mechanics. All
    user-facing text comes from the i18n catalog so EN reports stay in English.

    The note text reflects the current detection mechanism: the reader watches
    for ReadFile/Read calls to SKILL.md files inside skill directories. Old
    cached sessions may not carry this signal until the cache is refreshed.
    """
    base_template = templates.get("agentic_system", "")
    fingerprint_template = templates.get("agentic_system_with_fingerprint", base_template)
    detection_gap_template = templates.get("agentic_system_detection_gap", base_template)
    detection_note = templates.get("agentic_detection_note", "")

    # Use raw rates for the conditional so that values like 0.36% don't trigger
    # the detection-gap branch just because they round to 0.
    effective_fingerprint = raw_fingerprint_rate or raw_local_method_rate
    if workflow_fingerprint_rate > 0 or local_method_rate > 0 or effective_fingerprint > 0:
        # At least one signal is present; use clamped display values.
        display_local = local_method_rate if local_method_rate > 0 else ("<1" if raw_local_method_rate > 0 else "0")
        display_fp = workflow_fingerprint_rate if workflow_fingerprint_rate > 0 else ("<1" if raw_fingerprint_rate > 0 else "0")
        return fingerprint_template.format(
            score=score,
            skill_usage_rate=skill_usage_rate,
            public_framework_rate=public_framework_rate,
            local_method_rate=display_local,
            workflow_fingerprint_rate=display_fp,
            workflow_reuse_depth=workflow_reuse_depth,
            asset_authoring_rate=asset_authoring_rate,
            advanced_feature_rate=advanced_feature_rate,
        )
    # Fingerprint is 0 but skills ARE used — detection gap (e.g., cached sessions
    # parsed before skill-read detection was added; will improve after cache refresh)
    if skill_usage_rate > 0 or has_asset_roots:
        return detection_gap_template.format(
            score=score,
            skill_usage_rate=skill_usage_rate,
            note=detection_note,
            workflow_reuse_depth=workflow_reuse_depth,
            asset_authoring_rate=asset_authoring_rate,
            advanced_feature_rate=advanced_feature_rate,
        )
    # Everything is 0 — no asset data at all
    return base_template.format(
        score=score,
        skill_usage_rate=skill_usage_rate,
        public_framework_rate=public_framework_rate,
        local_method_rate=local_method_rate,
        workflow_fingerprint_rate=workflow_fingerprint_rate,
        workflow_reuse_depth=workflow_reuse_depth,
        asset_authoring_rate=asset_authoring_rate,
        advanced_feature_rate=advanced_feature_rate,
    )


def _build_level_axis_metrics(
    stats: GrowthProfile,
    target_level: str,
    catalogs: ReportLabelCatalogs,
) -> list[LevelEvidenceMetricView]:
    axis_scores = {axis.key: axis.score for axis in stats.radar_axes}
    capability_meta = _view_i18n(catalogs).get("capability_meta", {})
    metrics_i18n = _view_i18n(catalogs).get("level_axis_metrics", {})
    explanations = metrics_i18n.get("explanations", {})
    current_value_templates = metrics_i18n.get("current_values", {})
    target_profile = metrics_i18n.get("targets", {}).get(target_level, {})
    thresholds = metrics_i18n.get("thresholds", {}).get(target_level, {})
    structured_rate_pct = round(
        getattr(stats, "workflow_structured_session_count", 0) / max(stats.session_count, 1) * 100
    )
    verification_rate = round((stats.verification_behavior_rate or 0.0) * 100)
    test_rate = round((stats.test_run_rate or 0.0) * 100)
    code_verification_rate_pct = round((getattr(stats, "code_verification_rate", 0.0) or 0.0) * 100)
    prompt_dims = stats.pq_avg_dimensions or {}
    correction_quality = round(prompt_dims.get("correction_quality", 50.0))
    files_per_session = round(stats.total_files_modified / max(stats.session_count, 1), 1)
    token_volume_m = round((getattr(stats, "total_token_volume", 0) or 0) / 1_000_000, 1)
    mcp_rate = round((getattr(stats, "mcp_session_rate", 0.0) or 0.0) * 100)
    subagent_count = getattr(stats, "subagent_session_count", 0)
    tool_build_rate = round((getattr(stats, "tool_build_rate", 0.0) or 0.0) * 100)
    skill_usage_rate = round((getattr(stats, "skill_usage_session_rate", 0.0) or 0.0) * 100)
    public_framework_rate = round((getattr(stats, "public_framework_session_rate", 0.0) or 0.0) * 100)
    _raw_local_method_rate = (getattr(stats, "local_method_framework_session_rate", 0.0) or 0.0)
    _raw_fingerprint_rate = (getattr(stats, "workflow_fingerprint_session_rate", 0.0) or 0.0)
    local_method_rate = round(_raw_local_method_rate * 100)
    workflow_fingerprint_rate = round(_raw_fingerprint_rate * 100)
    asset_authoring_rate = round((getattr(stats, "asset_authoring_session_rate", 0.0) or 0.0) * 100)
    agentic_system_score = round(getattr(stats, "agentic_system_score", 0.0) or 0.0)
    authored_assets = (
        getattr(stats, "skill_authored_count", 0)
        + getattr(stats, "hook_modified_session_count", 0)
        + getattr(stats, "mcp_authored_session_count", 0)
    )
    user_actionable = round(
        (
            (stats.friction_by_attribution.get("user-actionable", 0) / max(sum(stats.friction_by_attribution.values()), 1))
            if stats.friction_by_attribution
            else 0.0
        )
        * 100
    )
    current_values = {
        "collaboration_framing": current_value_templates.get("collaboration_framing", "").format(
            score=round(axis_scores.get("collaboration_framing", 0.0)),
            direction_clarity_rate=round((stats.constraint_prompt_rate or 0.0) * 100),
            context_grounding_rate=round((stats.code_context_rate or 0.0) * 100),
            goal_locking_speed=round((getattr(stats, "goal_locking_speed", 0.0) or 0.0), 1),
            active_clarification_rate=round((stats.active_clarification_rate or 0.0) * 100),
        ),
        "execution_driving": current_value_templates.get("execution_driving", "").format(
            score=round(axis_scores.get("execution_driving", 0.0)),
            avg_chain=round(stats.avg_autonomous_chain_length or 0.0, 1),
            heavy_sessions=stats.heavy_session_count,
            subagent_count=subagent_count,
            mcp_rate=mcp_rate,
        ),
        "implementation_depth": current_value_templates.get("implementation_depth", "").format(
            score=round(axis_scores.get("implementation_depth", 0.0)),
            files_per_session=files_per_session,
            token_volume_m=token_volume_m,
            code_verification_rate_pct=code_verification_rate_pct,
        ),
        "delivery_closure": current_value_templates.get("delivery_closure", "").format(
            score=round(axis_scores.get("delivery_closure", 0.0)),
            completion_rate=round((getattr(stats, "fully_achieved_rate", 0.0) or 0.0) * 100),
            verification_rate=verification_rate,
            test_rate=test_rate,
        ),
        "adaptive_recovery": current_value_templates.get("adaptive_recovery", "").format(
            score=round(axis_scores.get("adaptive_recovery", 0.0)),
            correction_quality=correction_quality,
            structured_rate_pct=structured_rate_pct,
            user_actionable_ratio_pct=user_actionable,
            tool_build_rate=tool_build_rate,
            authored_assets=authored_assets,
        ),
        "agentic_system": _build_agentic_current_value(
            templates=current_value_templates,
            score=agentic_system_score,
            skill_usage_rate=skill_usage_rate,
            public_framework_rate=public_framework_rate,
            local_method_rate=local_method_rate,
            workflow_fingerprint_rate=workflow_fingerprint_rate,
            workflow_reuse_depth=getattr(stats, "workflow_reuse_depth", 0),
            asset_authoring_rate=asset_authoring_rate,
            advanced_feature_rate=round((getattr(stats, "advanced_feature_ratio", 0.0) or 0.0) * 100),
            has_asset_roots=bool(getattr(stats, "agent_asset", None) and getattr(stats.agent_asset, "has_data", False)),
            raw_local_method_rate=_raw_local_method_rate,
            raw_fingerprint_rate=_raw_fingerprint_rate,
        ),
    }
    raw_signals = dict(current_values)
    ordered_keys = tuple(_CAPABILITY_ORDER)
    metrics: list[LevelEvidenceMetricView] = []
    for key in ordered_keys:
        if key == "agentic_system":
            continue
        metric_copy = target_profile.get(key, {})
        target_value = metric_copy.get("target", "")
        level_hint = metric_copy.get("hint", "")
        required_score = float(thresholds.get(key, 0))
        passed = axis_scores.get(key, 0.0) >= required_score
        metrics.append(
            _level_metric(
                label=capability_meta.get(key, {}).get("label", key),
                current=current_values[key],
                target=target_value,
                passed=passed,
                explanation=f"{explanations.get(key, '')} {level_hint}".strip(),
                raw_signal=raw_signals[key],
                catalogs=catalogs,
            )
        )
    system_profile = target_profile.get("agentic_system", {})
    if system_profile:
        required_score = float(thresholds.get("agentic_system", 0))
        metrics.append(
            _level_metric(
                label=metrics_i18n.get("labels", {}).get("agentic_system", "Agentic system"),
                current=current_values["agentic_system"],
                target=system_profile.get("target", ""),
                passed=(getattr(stats, "agentic_system_score", 0.0) or 0.0) >= required_score,
                explanation=f"{explanations.get('agentic_system', '')} {system_profile.get('hint', '')}".strip(),
                raw_signal=raw_signals["agentic_system"],
                catalogs=catalogs,
                kind="system_layer",
            )
        )
    return metrics


def _level_metric(
    label: str,
    current: str,
    target: str,
    passed: bool,
    explanation: str,
    raw_signal: str,
    *,
    catalogs: ReportLabelCatalogs,
    kind: str = "axis",
) -> LevelEvidenceMetricView:
    ev = _view_i18n(catalogs).get("level_evidence", {})
    status_met = ev.get("status_met", "Met")
    status_unmet = ev.get("status_unmet", "Not Met")
    return LevelEvidenceMetricView(
        label=label,
        current_value=current,
        target_value=target,
        status=status_met if passed else status_unmet,
        explanation=explanation,
        raw_signal=raw_signal,
        kind=kind,
    )


def build_level_evidence_section(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
) -> LevelEvidenceSectionView:
    ev_i18n = _view_i18n(catalogs).get("level_evidence", {})
    observed_session_reads = sum(stats.outcome_counts.values())
    has_formal_level = bool(stats.growth_level)
    if has_formal_level:
        current_level = stats.growth_level
        current_num = _LEVEL_ORDER.get(current_level, 2)
        target_level = current_level if current_level == "L5" else _level_name(current_num + 1)
    else:
        current_level = ev_i18n.get("growth_level_unrated", "Unrated")
        current_num = 1
        target_level = "L2"
    metrics = _build_level_axis_metrics(stats, target_level, catalogs)
    status_met = ev_i18n.get("status_met", "Met")
    misses = [item for item in metrics if item.status != status_met]
    blockers = [f"{item.label}：{item.raw_signal}" for item in misses[:3]]
    met_count = len(metrics) - len(misses)
    methodology_title, methodology_lines = _mirror_methodology(catalogs)

    fmt = {"current_level": current_level, "next_level": target_level}
    if not has_formal_level:
        headline = ev_i18n.get("headline_unrated", "")
        verdict = ev_i18n.get("verdict_unrated", "").format(min_session_reads=MIN_SESSION_READS_FOR_MIRROR_SCORE)
        target_caption = ev_i18n.get("target_caption_unrated", "")
        blocker_title = ev_i18n.get("blocker_title_unrated", "")
    elif current_level == "L5":
        headline = ev_i18n.get("headline_l5", "")
        verdict = ev_i18n.get("verdict_l5", "")
        target_caption = ev_i18n.get("target_caption_l5", "")
        blocker_title = ev_i18n.get("blocker_title_l5", "")
    elif misses and current_num <= 2:
        headline = ev_i18n.get("headline_low_gap", "").format(**fmt)
        verdict = ev_i18n.get("verdict_low_gap", "").format(**fmt)
        target_caption = ev_i18n.get("target_caption_upgrade", "").format(target_level=target_level)
        blocker_title = ev_i18n.get("blocker_title_low", "")
    elif misses and current_num == 3:
        headline = ev_i18n.get("headline_level_gap", "").format(**fmt)
        verdict = ev_i18n.get("verdict_level3_gap", "").format(**fmt)
        target_caption = ev_i18n.get("target_caption_upgrade", "").format(target_level=target_level)
        blocker_title = ev_i18n.get("blocker_title_level3", "")
    elif misses and current_num >= 4:
        headline = ev_i18n.get("headline_level_gap", "").format(**fmt)
        verdict = ev_i18n.get("verdict_level4_gap", "").format(**fmt)
        target_caption = ev_i18n.get("target_caption_upgrade", "").format(target_level=target_level)
        blocker_title = ev_i18n.get("blocker_title_level4", "")
    else:
        headline = (
            ev_i18n.get("headline_baseline_met", "").format(current_level=target_level, next_level=target_level)
            if current_level != "L5"
            else ev_i18n.get("headline_l5_baseline_met", "")
        )
        verdict = (
            ev_i18n.get("verdict_baseline_met", "").format(current_level=target_level, next_level=target_level)
            if current_level != "L5"
            else ev_i18n.get("verdict_l5_baseline_met", "")
        )
        target_caption = (
            ev_i18n.get("target_caption_upgrade", "").format(target_level=target_level)
            if current_level != "L5"
            else ev_i18n.get("target_caption_l5", "")
        )
        blocker_title = ev_i18n.get("blocker_title_no_blockers", "")
    next_step = blockers[0] if blockers else ev_i18n.get("next_step_default", "")
    if not has_formal_level:
        progress_summary = ev_i18n.get("progress_summary_unrated", "").format(
            observed_session_reads=observed_session_reads,
            target_caption=target_caption,
        )
    else:
        progress_summary = ev_i18n.get("progress_summary_rated", "").format(
            met_count=met_count,
            total_metrics=len(metrics),
            target_caption=target_caption,
        )
    source_note = ev_i18n.get("source_note_base", "")
    if session_read_mode == "heuristic":
        source_note += ev_i18n.get("source_note_heuristic_suffix", "")
    else:
        source_note += ev_i18n.get("source_note_llm_suffix", "")
    return LevelEvidenceSectionView(
        headline=headline,
        verdict=verdict,
        blockers=blockers,
        metrics=metrics,
        next_step=next_step,
        current_level=current_level,
        target_level=target_level,
        target_caption=target_caption,
        blocker_title=blocker_title,
        progress_summary=progress_summary,
        source_note=source_note,
        methodology_title=methodology_title,
        methodology_lines=methodology_lines,
    )
