"""Personal AI growth report view assembly (application layer)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..domain.session.model import SessionRecord
from ..domain.signals.model import SessionRead
from ..domain.growth.model import (
    AgentAssetStats,
    GrowthGap,
    GrowthProfile,
    GrowthStage,
    RadarAxis,
)
from ..domain.growth.capability import compute_capability_scores
from ..domain.growth.scorer import (
    MIN_SESSION_READS_FOR_MIRROR_SCORE,
    format_growth_level_score_range,
)
from ..domain.growth.coaching import CoachingContent
from ..domain.growth.evidence import clean_project_name
from ..domain.snapshots.model import SnapshotSource
from ..domain.signals.collab import CollaborationStyleResult, compute_collaboration_style
from ..domain.growth.highlights import Exemplar, pattern_label, surface_highlights
from ..domain.snapshots.trajectory import build_snapshot_trajectory_window
from .growth_trajectory import (
    GrowthTrajectoryView,
    build_growth_trajectory_view,
    build_runtime_snapshot_source,
)
from .growth_plan import GrowthPlanView, GrowthPriorityView, build_growth_plan
from .label_catalogs import ReportLabelCatalogs
from .prompt_coach import build_prompt_coach_view


def _view_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.view_model


def _level_guide_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.level_guide


def _template_labels(catalogs: ReportLabelCatalogs) -> dict[str, str]:
    return catalogs.template_labels


def _guidance_labels(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.guidance_labels


def _pattern_label(pattern: str, catalogs: ReportLabelCatalogs) -> str:
    labels = _view_i18n(catalogs).get("pattern_labels", {})
    return pattern_label(pattern, labels)


_CAPABILITY_ORDER = [
    "collaboration_framing",
    "execution_driving",
    "implementation_depth",
    "delivery_closure",
    "adaptive_recovery",
    "agentic_system",
]


def _localize_radar_axes(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> list[RadarAxis]:
    capability_meta = _view_i18n(catalogs).get("capability_meta", {})
    radar_i18n = _view_i18n(catalogs).get("radar_axes", {})
    axes: list[RadarAxis] = []
    for axis in stats.radar_axes:
        axis_i18n = radar_i18n.get(axis.key, {})
        short_reason = axis_i18n.get(
            "reason_high" if axis.score >= 65 else "reason_low",
            "",
        )
        if axis.key == "collaboration_framing":
            tooltip_template = axis_i18n.get("tooltip", "")
            if tooltip_template:
                short_reason = tooltip_template.format(
                    score=round(axis.score, 1),
                    direction_clarity_rate=round(stats.constraint_prompt_rate * 100),
                    context_grounding_rate=round(stats.code_context_rate * 100),
                    goal_locking_speed=round(stats.goal_locking_speed, 1),
                    active_clarification_rate=round(stats.active_clarification_rate * 100),
                )
        elif axis.key == "agentic_system":
            tooltip_template = axis_i18n.get("tooltip", "")
            if tooltip_template:
                short_reason = tooltip_template.format(
                    score=round(axis.score, 1),
                    skill_usage_pct=round(stats.skill_usage_session_rate * 100),
                    structured_pct=round(stats.workflow_fingerprint_session_rate * 100),
                    asset_authoring_pct=round(stats.asset_authoring_session_rate * 100),
                )
        axes.append(
            RadarAxis(
                key=axis.key,
                label=capability_meta.get(axis.key, {}).get("label", axis.key),
                score=axis.score,
                status=axis.status,
                short_reason=short_reason,
                confidence=axis.confidence,
                has_data=getattr(axis, "has_data", True),
            )
        )
    return axes


def _localize_gap_rankings(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> list[GrowthGap]:
    gaps_i18n = _view_i18n(catalogs).get("growth_gaps", {})
    localized: list[GrowthGap] = []
    for gap in stats.gap_rankings:
        meta = gaps_i18n.get(gap.key, {})
        localized.append(
            GrowthGap(
                key=gap.key,
                label=meta.get("label", gap.key),
                severity=gap.severity,
                rank=gap.rank,
                evidence_summary=meta.get("evidence_summary", ""),
                why_it_happens=meta.get("why_it_happens", ""),
                suggested_action=meta.get("suggested_action", ""),
            )
        )
    return localized


def _localize_growth_stage(
    stats: GrowthProfile,
    localized_axes: list[RadarAxis],
    localized_gaps: list[GrowthGap],
    catalogs: ReportLabelCatalogs,
) -> GrowthStage | None:
    if stats.growth_stage is None:
        return None
    stage_i18n = _view_i18n(catalogs).get("growth_stage", {})
    meta = stage_i18n.get(stats.growth_stage.level, {})
    primary_gap = next((gap.label for gap in localized_gaps if gap.key == stats.growth_stage.primary_gap), stats.growth_stage.primary_gap)
    strongest_axis = next((axis.label for axis in localized_axes if axis.key == stats.growth_stage.strongest_axis), stats.growth_stage.strongest_axis)
    next_breakthrough = localized_gaps[0].suggested_action if localized_gaps else ""
    return GrowthStage(
        level=stats.growth_stage.level,
        label=meta.get("label", stats.growth_stage.level),
        summary=meta.get("summary", ""),
        strongest_axis=strongest_axis,
        primary_gap=primary_gap,
        next_breakthrough=next_breakthrough,
    )


def _build_radar_chart(axes: list[RadarAxis]) -> RadarChartView:
    size = 320
    center = size // 2
    outer_radius = 110
    count = max(len(axes), 1)

    def _point(axis_index: int, radius: float) -> tuple[float, float]:
        angle = (-math.pi / 2) + (2 * math.pi * axis_index / count)
        x = center + radius * math.cos(angle)
        y = center + radius * math.sin(angle)
        return round(x, 1), round(y, 1)

    grid_polygons: list[str] = []
    for step in range(1, 6):
        radius = outer_radius * step / 5
        grid_polygons.append(" ".join(f"{x},{y}" for x, y in (_point(i, radius) for i in range(count))))

    axis_lines = [
        f"{center},{center} {x},{y}"
        for x, y in (_point(i, outer_radius) for i in range(count))
    ]
    label_positions: list[dict] = []
    for index, axis in enumerate(axes):
        x, y = _point(index, outer_radius + 24)
        label_positions.append({"x": x, "y": y, "label": axis.label})

    polygon_points = " ".join(
        f"{x},{y}"
        for x, y in (
            _point(index, outer_radius * max(0.0, min(100.0, axis.score)) / 100.0)
            for index, axis in enumerate(axes)
        )
    )

    hover_zones: list[dict] = []
    hover_radius = outer_radius + 15
    for index, axis in enumerate(axes):
        angle_prev = (-math.pi / 2) + (2 * math.pi * (index - 0.5) / count)
        angle_next = (-math.pi / 2) + (2 * math.pi * (index + 0.5) / count)
        
        x1 = center + hover_radius * math.cos(angle_prev)
        y1 = center + hover_radius * math.sin(angle_prev)
        x2 = center + hover_radius * math.cos(angle_next)
        y2 = center + hover_radius * math.sin(angle_next)
        
        pts = f"{center},{center} {round(x1, 1)},{round(y1, 1)} {round(x2, 1)},{round(y2, 1)}"
        hover_zones.append({
            "key": axis.key,
            "label": axis.label,
            "score": axis.score,
            "short_reason": axis.short_reason,
            "points": pts
        })

    return RadarChartView(
        size=size,
        center=center,
        outer_radius=outer_radius,
        grid_polygons=grid_polygons,
        axis_lines=axis_lines,
        label_positions=label_positions,
        polygon_points=polygon_points,
        hover_zones=hover_zones,
    )


@dataclass
class PersonalStatChip:
    label: str
    value: str


@dataclass
class ReportSectionLinkView:
    id: str
    label: str
    nav_visible: bool = True
    kind: str = "main"


@dataclass
class PersonalSummaryView:
    title: str
    subtitle: str
    headline: str
    growth_level: str
    mirror_score: int
    session_count: int
    active_days: int
    strongest_signal: str
    next_focus: str
    score_display: str = ""
    source_note: str = ""
    share_title: str = ""
    share_lines: list[str] = field(default_factory=list)
    chips: list[PersonalStatChip] = field(default_factory=list)
    top_projects: list[str] = field(default_factory=list)


@dataclass
class CapabilityDimensionView:
    key: str
    label: str
    score: float
    explanation: str
    next_action: str
    has_data: bool = True


@dataclass
class CapabilitySectionView:
    strongest_label: str
    weakest_label: str
    dimensions: list[CapabilityDimensionView] = field(default_factory=list)
    advanced_features: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class PromptCoachTakeawayView:
    label: str
    kind: str
    evidence: str
    message: str
    action: str
    better_prompt: str = ""


@dataclass
class PromptCoachDimensionView:
    label: str
    score: float


@dataclass
class PromptCoachSourceSummaryView:
    llm_session_count: int = 0
    heuristic_session_count: int = 0
    light_session_count: int = 0
    evaluated_user_messages: int = 0
    run_mode: str = "llm"
    llm_evaluated_count: int = 0
    insufficient_count: int = 0
    llm_failed_count: int = 0
    llm_unavailable_count: int = 0


@dataclass
class PromptCoachDeficitView:
    id: str
    category: str
    label: str
    description: str
    impact: str
    confidence: str
    evidence_refs: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class PromptCoachRewriteCardView:
    id: str
    scene: str
    original: str
    problem: str
    better_prompt: str
    why: str
    category: str
    confidence: str
    evidence_refs: list[str] = field(default_factory=list)
    source_note: str = ""


@dataclass
class PromptCoachTemplateView:
    id: str
    title: str
    scene: str
    common_gap: str
    template: str


@dataclass
class PromptCoachChecklistItemView:
    id: str
    text: str
    related_deficit_id: str


@dataclass
class PromptCoachPromptStyleView:
    type: str
    label: str
    evidence: list[str] = field(default_factory=list)
    coaching_message: str = ""
    suggested_next_prompt: str = ""
    trigger_maturity: list[str] = field(default_factory=list)


@dataclass
class PromptCoachClosureGuidanceView:
    id: str
    task_type: str
    label: str
    mode: str = "engineered"
    expected_closure_methods: list[str] = field(default_factory=list)
    missing_closure_methods: list[str] = field(default_factory=list)
    coaching_message: str = ""


@dataclass
class PromptCoachFrictionSynthesisView:
    id: str
    label: str
    explanation: str
    next_action: str
    confidence: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    generated_by: str = "rule"


@dataclass
class PromptCoachView:
    available: bool
    headline: str
    strongest_label: str
    weakest_label: str
    evidence_summary: str
    strength_habit: str
    source_note: str = ""
    weak_dimensions: list[str] = field(default_factory=list)
    deficits: list[str] = field(default_factory=list)
    dimension_scores: list[PromptCoachDimensionView] = field(default_factory=list)
    takeaways: list[PromptCoachTakeawayView] = field(default_factory=list)
    source_summary: PromptCoachSourceSummaryView = field(default_factory=PromptCoachSourceSummaryView)
    top_deficits: list[PromptCoachDeficitView] = field(default_factory=list)
    rewrite_cards: list[PromptCoachRewriteCardView] = field(default_factory=list)
    universal_template: Optional[PromptCoachTemplateView] = None
    scenario_templates: list[PromptCoachTemplateView] = field(default_factory=list)
    preflight_checklist: list[PromptCoachChecklistItemView] = field(default_factory=list)
    prompt_style: Optional[PromptCoachPromptStyleView] = None
    closure_guidance: Optional[PromptCoachClosureGuidanceView] = None
    recommended_training_inputs: list[str] = field(default_factory=list)
    friction_synthesis: list[PromptCoachFrictionSynthesisView] = field(default_factory=list)
    light_state_note: str = ""


@dataclass
class FrictionCategoryView:
    label: str
    count: int


@dataclass
class FrictionSectionView:
    headline: str
    primary_source: str
    categories: list[FrictionCategoryView] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class PersonalExemplarView:
    category_label: str
    score: float
    project_name: str
    summary: str
    facts: str
    why_keep: str = ""
    technique: str = ""


@dataclass
class UsageStatView:
    label: str
    value: str
    detail: str = ""


@dataclass
class UsageSectionView:
    headline: str
    summary: str
    hero_support_line: str = ""
    coverage_note: str = ""
    memory_note: str = ""
    stats: list[UsageStatView] = field(default_factory=list)


@dataclass
class StyleLensDimensionView:
    label: str
    left_pole: str
    right_pole: str
    pct: float
    interpretation: str


@dataclass
class StyleLensSectionView:
    archetype_name: str
    archetype_tag: str
    slogan: str
    description: str
    strengths: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)
    dimensions: list[StyleLensDimensionView] = field(default_factory=list)


@dataclass
class CollaborationRhythmStatView:
    label: str
    value: str
    detail: str = ""


@dataclass
class CollaborationRhythmSectionView:
    headline: str
    rhythm_label: str
    rhythm_summary: str
    next_action: str
    stats: list[CollaborationRhythmStatView] = field(default_factory=list)


@dataclass
class FocusAreaView:
    label: str
    count: int
    detail: str = ""


@dataclass
class WorkFocusSectionView:
    headline: str
    recent_work: list[str] = field(default_factory=list)
    goal_mix: list[FocusAreaView] = field(default_factory=list)
    tools: list[FocusAreaView] = field(default_factory=list)
    languages: list[FocusAreaView] = field(default_factory=list)


@dataclass
class WinCardView:
    title: str
    evidence: str
    why_it_matters: str
    next_action: str


@dataclass
class WinsSectionView:
    headline: str
    wins: list[WinCardView] = field(default_factory=list)


@dataclass
class LevelGuideItemView:
    level: str
    score_range: str
    title: str
    description: str
    signals: list[str] = field(default_factory=list)
    next_step: str = ""
    current: bool = False


@dataclass
class LevelGuideSectionView:
    headline: str
    current_level: str
    current_score: int
    items: list[LevelGuideItemView] = field(default_factory=list)


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


@dataclass
class AgentAssetItemView:
    label: str
    count: int


@dataclass
class AgentAssetFootprintView:
    headline: str
    skill_count: int
    prompt_count: int
    rule_count: int
    project_keys: list[str] = field(default_factory=list)
    recently_modified: list[str] = field(default_factory=list)
    summary_line: str = ""


@dataclass
class RadarChartView:
    size: int
    center: int
    outer_radius: int
    grid_polygons: list[str] = field(default_factory=list)
    axis_lines: list[str] = field(default_factory=list)
    label_positions: list[dict] = field(default_factory=list)
    polygon_points: str = ""
    hover_zones: list[dict] = field(default_factory=list)


@dataclass
class PersonalReportView:
    report_title: str
    tool_display_name: str
    date_range: str
    sections: list[ReportSectionLinkView]
    summary: PersonalSummaryView
    capability: CapabilitySectionView
    level_guide: LevelGuideSectionView
    level_evidence: LevelEvidenceSectionView
    collaboration_rhythm: CollaborationRhythmSectionView
    usage: UsageSectionView
    work_focus: WorkFocusSectionView
    wins: WinsSectionView
    prompt_coach: PromptCoachView
    friction: FrictionSectionView
    exemplars: list[PersonalExemplarView]
    style_lens: StyleLensSectionView
    growth_plan: GrowthPlanView
    generated_at: str
    agent_asset: Optional[AgentAssetFootprintView] = None
    growth_trajectory: Optional[GrowthTrajectoryView] = None
    radar_axes: list[RadarAxis] = field(default_factory=list)
    radar_chart: Optional[RadarChartView] = None
    gap_rankings: list[GrowthGap] = field(default_factory=list)
    growth_stage: Optional[GrowthStage] = None
    labels: dict = field(default_factory=dict)
    hide_wechat: bool = False
    hide_email: bool = False
    active_clarification_rate: float = 0.0
    goal_locking_speed: float = 0.0


def build_agent_asset_footprint(
    asset_stats: Optional[AgentAssetStats],
    *,
    catalogs: ReportLabelCatalogs,
) -> Optional[AgentAssetFootprintView]:
    """Build the agent asset footprint card from enricher stats."""
    if asset_stats is None or not asset_stats.has_data:
        return None
    aa_i18n = _view_i18n(catalogs).get("agent_asset", {})
    total = asset_stats.total_asset_files
    headline = aa_i18n.get("headline", "").format(total=total)
    summary = aa_i18n.get("summary", "").format(
        skill_count=asset_stats.skill_files_count,
        prompt_count=asset_stats.prompt_files_count,
        rule_count=asset_stats.rule_files_count,
    )
    return AgentAssetFootprintView(
        headline=headline,
        skill_count=asset_stats.skill_files_count,
        prompt_count=asset_stats.prompt_files_count,
        rule_count=asset_stats.rule_files_count,
        project_keys=asset_stats.hub_project_keys[:10],
        recently_modified=list(dict.fromkeys(asset_stats.recently_modified_assets))[:10],
        summary_line=summary,
    )


def build_personal_report_view(
    *,
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    stats: GrowthProfile,
    tool_display_name: str,
    catalogs: ReportLabelCatalogs,
    redact: bool = False,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    asset_stats: Optional[AgentAssetStats] = None,
    previous_snapshot: SnapshotSource | None = None,
    historical_snapshots: list[SnapshotSource] | None = None,
    coaching: CoachingContent | None = None,
    session_read_mode: str = "heuristic",
    quality_eligible: int = 0,
    extraction_failed: int = 0,
    hide_wechat: bool = False,
    hide_email: bool = False,
) -> PersonalReportView:
    capability_scores = compute_capability_scores(stats)
    capability = _build_capability_section(capability_scores, catalogs, stats=stats)
    capability.advanced_features = sorted(
        ((key, int(value)) for key, value in (stats.advanced_feature_counts or {}).items() if value),
        key=lambda item: (-item[1], item[0]),
    )
    exemplars = _build_exemplars(sessions, session_reads, redact, catalogs)
    prompt_coach = build_prompt_coach_view(
        stats=stats,
        sessions=sessions,
        session_reads=session_reads,
        session_read_mode=session_read_mode,
        catalogs=catalogs,
        coaching=coaching,
    )
    friction = _build_friction(stats, catalogs)
    localized_radar_axes = _localize_radar_axes(stats, catalogs)
    localized_gap_rankings = _localize_gap_rankings(stats, catalogs)
    localized_growth_stage = _localize_growth_stage(
        stats,
        localized_radar_axes,
        localized_gap_rankings,
        catalogs,
    )
    growth_plan = build_growth_plan(
        stats=stats,
        capability_scores=capability_scores,
        catalogs=catalogs,
        prompt_coach=prompt_coach,
        growth_trajectory=None,
    )
    summary = _build_summary(
        stats=stats,
        tool_display_name=tool_display_name,
        date_range=_compute_date_range(sessions, since=since, until=until),
        capability=capability,
        growth_plan=growth_plan,
        redact=redact,
        coaching=coaching,
        session_read_mode=session_read_mode,
        catalogs=catalogs,
    )
    level_guide = _build_level_guide(stats, catalogs)
    level_evidence = _build_level_evidence(stats, capability_scores, session_read_mode, catalogs)
    collaboration_rhythm = _build_collaboration_rhythm(stats, catalogs)
    usage = _build_usage_section(stats, catalogs)
    usage.coverage_note = _build_usage_coverage_note(sessions, catalogs)
    work_focus = _build_work_focus(stats, sessions, session_reads, redact, catalogs)
    style_lens = _build_style_lens(stats, capability_scores, agent_asset=asset_stats, catalogs=catalogs)
    wins = _build_wins(
        stats=stats,
        capability=capability,
        prompt_coach=prompt_coach,
        style_lens=style_lens,
        exemplars=exemplars,
        catalogs=catalogs,
    )
    agent_asset = build_agent_asset_footprint(asset_stats, catalogs=catalogs)
    labels = _template_labels(catalogs)
    history_sources = list(historical_snapshots or [])
    if previous_snapshot is None and history_sources:
        previous_snapshot = history_sources[-1]
    current_snapshot = build_runtime_snapshot_source(
        stats=stats,
        session_reads=session_reads,
        summary=summary,
        capability=capability,
        prompt_coach=prompt_coach,
        growth_plan=growth_plan,
        agent_asset=agent_asset,
        exemplars=exemplars,
        tool_display_name=tool_display_name,
        date_range=_compute_date_range(sessions, since=since, until=until),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        quality_eligible=quality_eligible,
        extraction_failed=extraction_failed,
    )
    growth_trajectory = build_growth_trajectory_view(
        current_source=current_snapshot,
        previous_source=previous_snapshot,
        history_sources=history_sources,
        catalogs=catalogs,
    )
    growth_plan = build_growth_plan(
        stats=stats,
        capability_scores=capability_scores,
        catalogs=catalogs,
        prompt_coach=prompt_coach,
        growth_trajectory=growth_trajectory,
    )
    summary = _build_summary(
        stats=stats,
        tool_display_name=tool_display_name,
        date_range=_compute_date_range(sessions, since=since, until=until),
        capability=capability,
        growth_plan=growth_plan,
        redact=redact,
        coaching=coaching,
        session_read_mode=session_read_mode,
        catalogs=catalogs,
    )
    current_snapshot = build_runtime_snapshot_source(
        stats=stats,
        session_reads=session_reads,
        summary=summary,
        capability=capability,
        prompt_coach=prompt_coach,
        growth_plan=growth_plan,
        agent_asset=agent_asset,
        exemplars=exemplars,
        tool_display_name=tool_display_name,
        date_range=_compute_date_range(sessions, since=since, until=until),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        quality_eligible=quality_eligible,
        extraction_failed=extraction_failed,
    )
    growth_trajectory = build_growth_trajectory_view(
        current_source=current_snapshot,
        previous_source=previous_snapshot,
        history_sources=history_sources,
        catalogs=catalogs,
    )
    sections = _build_report_sections(
        labels,
        has_agent_asset=agent_asset is not None,
        has_growth_delta=bool(growth_trajectory and growth_trajectory.available),
    )
    return PersonalReportView(
        report_title=labels.get("report_title", "AI 成长镜"),
        tool_display_name=tool_display_name,
        date_range=_compute_date_range(sessions, since=since, until=until),
        sections=sections,
        summary=summary,
        capability=capability,
        level_guide=level_guide,
        level_evidence=level_evidence,
        collaboration_rhythm=collaboration_rhythm,
        usage=usage,
        work_focus=work_focus,
        wins=wins,
        prompt_coach=prompt_coach,
        friction=friction,
        exemplars=exemplars,
        style_lens=style_lens,
        growth_plan=growth_plan,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        agent_asset=agent_asset,
        growth_trajectory=growth_trajectory,
        radar_axes=localized_radar_axes,
        radar_chart=_build_radar_chart(localized_radar_axes),
        gap_rankings=localized_gap_rankings,
        growth_stage=localized_growth_stage,
        labels=labels,
        hide_wechat=hide_wechat,
        hide_email=hide_email,
        active_clarification_rate=stats.active_clarification_rate,
        goal_locking_speed=getattr(stats, "goal_locking_speed", 0.0),
    )


def _build_capability_section(
    capability_scores: dict[str, float],
    catalogs: ReportLabelCatalogs,
    *,
    stats: Optional[GrowthProfile] = None,
) -> CapabilitySectionView:
    meta = _view_i18n(catalogs)["capability_meta"]
    # Mirror the rule used in scorer._build_radar_axes so the capability cards
    # and the radar always agree on whether a dimension actually has support.
    pq_evaluated = max(0, getattr(stats, "pq_sessions_evaluated", 0)) if stats else 0
    has_outcome_signals = False
    if stats is not None:
        has_outcome_signals = (
            stats.workflow_build_substantial_count
            + stats.workflow_build_moderate_count
            + (stats.avg_autonomous_chain_length or 0.0)
        ) > 0 or bool(stats.top_tools)
    session_count = stats.session_count if stats else 0
    dims: list[CapabilityDimensionView] = []
    for key in _CAPABILITY_ORDER:
        entry = meta.get(key, {"label": key, "explanation": "", "next_action": ""})
        label = entry["label"]
        explanation = entry["explanation"]
        next_action = entry["next_action"]
        score = capability_scores.get(key, 0.0)
        if stats is None:
            has_data = True
        elif key == "collaboration_framing":
            has_data = pq_evaluated > 0
        elif key == "agentic_system":
            has_data = stats is not None and "agentic_system" in stats.agentic_sub_scores and stats.session_count > 0
        else:
            has_data = session_count > 0 and (pq_evaluated > 0 or has_outcome_signals)
        if has_data and score == 0.0 and not has_outcome_signals and pq_evaluated == 0:
            has_data = False
        dims.append(
            CapabilityDimensionView(
                key=key,
                label=label,
                score=score,
                explanation=explanation,
                next_action=next_action,
                has_data=has_data,
            )
        )
    strongest = max(dims, key=lambda item: item.score)
    weakest = min(dims, key=lambda item: item.score)
    return CapabilitySectionView(strongest_label=strongest.label, weakest_label=weakest.label, dimensions=dims)


def _build_prompt_coach_from_coaching(
    coaching: CoachingContent,
    stats: GrowthProfile,
    catalogs: ReportLabelCatalogs,
) -> PromptCoachView:
    """Build prompt coach view from LLM-generated coaching content."""
    dim_labels = _view_i18n(catalogs)["pq_dim_labels"]
    dims = stats.pq_avg_dimensions or {}
    if dims:
        sorted_dims = sorted(dims.items(), key=lambda item: item[1])
        weakest = sorted_dims[0]
        strongest = max(dims.items(), key=lambda item: item[1])
        weakest_label = dim_labels.get(weakest[0], weakest[0])
        strongest_label = dim_labels.get(strongest[0], strongest[0])
        weak_dimensions = [dim_labels.get(name, name) for name, _ in sorted_dims[:2]]
        deficits = [
            _pq_deficit_display(name, count, catalogs)
            for name, count in sorted(stats.pq_deficit_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]
    else:
        weakest_label = coaching.framing_evidence_takeaways[0].label if coaching.framing_evidence_takeaways else ""
        strongest_label = ""
        weak_dimensions = [weakest_label] if weakest_label else []
        deficits = []

    takeaways = [
        PromptCoachTakeawayView(
            label=t.label,
            kind=t.kind,
            evidence=t.evidence,
            message=t.message,
            action=t.action,
            better_prompt=t.better_prompt,
        )
        for t in coaching.framing_evidence_takeaways
    ]
    pc_i18n = _view_i18n(catalogs).get("prompt_coach", {}).get("from_coaching", {})
    return PromptCoachView(
        available=True,
        headline=coaching.framing_evidence_headline,
        strongest_label=strongest_label,
        weakest_label=weakest_label,
        evidence_summary=coaching.framing_evidence_summary,
        strength_habit="",
        source_note=_prompt_quality_source_note(stats, pc_i18n.get("source_note", ""), catalogs),
        weak_dimensions=weak_dimensions,
        deficits=deficits,
        takeaways=takeaways,
    )


def _build_summary(
    *,
    stats: GrowthProfile,
    tool_display_name: str,
    date_range: str,
    capability: CapabilitySectionView,
    growth_plan: GrowthPlanView,
    redact: bool,
    catalogs: ReportLabelCatalogs,
    coaching: CoachingContent | None = None,
    session_read_mode: str = "heuristic",
) -> PersonalSummaryView:
    s_i18n = _view_i18n(catalogs).get("summary", {})
    strongest = capability.strongest_label
    weakest = capability.weakest_label
    score_ready = bool(stats.growth_level)
    growth_level_display = (
        stats.growth_level
        if score_ready
        else s_i18n.get("growth_level_unrated", "Unrated")
    )
    score_display = str(stats.mirror_score) if score_ready else "--"
    source_notes = s_i18n.get("source_note", {})
    source_note = source_notes.get("heuristic" if session_read_mode == "heuristic" else "llm", "")
    if session_read_mode == "heuristic" and coaching is not None:
        source_note += source_notes.get("coaching_suffix_heuristic", "")
    headlines = s_i18n.get("headline", {})
    headline = (
        headlines.get("ready", "").format(growth_level=growth_level_display, weakest=weakest)
        if score_ready
        else headlines.get("unrated", "").format(weakest=weakest)
    )
    chips_i18n = s_i18n.get("chips", {})
    capability_meta = _view_i18n(catalogs).get("capability_meta", {})
    delivery_label = capability_meta.get("delivery_closure", {}).get("label", "Delivery closure")
    completion_pct = round((getattr(stats, "fully_achieved_rate", 0.0) or 0.0) * 100)
    chips = [
        PersonalStatChip(chips_i18n.get("date_range", "Date range"), date_range or chips_i18n.get("unknown", "unknown")),
        PersonalStatChip(chips_i18n.get("active_days", "Active days"), str(stats.active_days)),
        PersonalStatChip(chips_i18n.get("code_sessions", "Code sessions"), str(stats.code_session_count or stats.session_count)),
        PersonalStatChip(delivery_label, f"{completion_pct}%"),
    ]
    projects = [] if redact else [_display_project_name(name) for name, _ in stats.top_projects[:3]]
    share_i18n = s_i18n.get("share_lines", {})
    share_fmt = {
        "session_count": stats.session_count,
        "active_days": stats.active_days,
        "heavy_session_count": stats.heavy_session_count,
        "strongest": strongest,
        "weakest": weakest,
        "next_focus": growth_plan.next_focus,
    }
    share_lines = [
        share_i18n.get("line1", "").format(**share_fmt),
        share_i18n.get("line2", "").format(**share_fmt),
        share_i18n.get("line3", "").format(**share_fmt),
    ]
    return PersonalSummaryView(
        title=s_i18n.get("title", ""),
        subtitle=tool_display_name,
        headline=headline,
        score_display=score_display,
        source_note=source_note,
        share_title=s_i18n.get("share_title", ""),
        share_lines=share_lines,
        growth_level=growth_level_display,
        mirror_score=stats.mirror_score,
        session_count=stats.session_count,
        active_days=stats.active_days,
        strongest_signal=s_i18n.get("strongest_signal", "").format(strongest=strongest),
        next_focus=growth_plan.next_focus,
        chips=chips,
        top_projects=projects,
    )


def _build_report_sections(
    labels: dict[str, str],
    *,
    has_agent_asset: bool,
    has_growth_delta: bool,
) -> list[ReportSectionLinkView]:
    # Order MUST match report.html.j2 DOM order so sidebar nav, scroll-spy,
    # and click targets stay aligned.
    primary_sections = [
        ReportSectionLinkView(
            "section-summary",
            labels.get("section_report_title", labels.get("report_title", "AI 成长镜")),
            nav_visible=False,
        ),
        ReportSectionLinkView(
            "section-growth-signals",
            labels.get("section_growth_signals", "Growth signal overview"),
        ),
        ReportSectionLinkView(
            "section-level-evidence",
            labels.get("section_level_evidence", "Stage assessment"),
        ),
    ]
    if has_growth_delta:
        primary_sections.append(
            ReportSectionLinkView(
                "section-growth-delta",
                labels.get("section_growth_delta", "Growth trajectory"),
            )
        )
    primary_sections.append(
        ReportSectionLinkView(
            "section-growth-plan",
            labels.get("section_growth_plan", "Next practice sprint"),
        ),
    )
    appendix_sections = [
        ReportSectionLinkView("section-level-guide", labels.get("section_level_guide", "Collaboration level guide"), nav_visible=False, kind="appendix"),
        ReportSectionLinkView("section-friction", labels.get("section_friction", "Friction map"), nav_visible=False, kind="appendix"),
        ReportSectionLinkView("section-exemplars", labels.get("section_exemplars", "Methods worth keeping"), nav_visible=False, kind="appendix"),
        ReportSectionLinkView("section-focus", labels.get("section_work_focus", "What you are using AI for"), nav_visible=False, kind="appendix"),
        ReportSectionLinkView("section-rhythm", labels.get("section_rhythm", "Collaboration rhythm"), nav_visible=False, kind="appendix"),
        ReportSectionLinkView("section-wins", labels.get("section_wins", "Highlights this period"), nav_visible=False, kind="appendix"),
    ]
    if has_agent_asset:
        appendix_sections.append(
            ReportSectionLinkView("section-agent-asset", labels.get("section_agent_asset", "Agent asset footprint"), nav_visible=False, kind="appendix")
        )
    appendix_sections.append(
        ReportSectionLinkView("section-style-lens", labels.get("section_style_lens", "Collaboration style lens"), nav_visible=False, kind="appendix")
    )
    return primary_sections + appendix_sections


def _build_heuristic_prompt_coach(
    stats: GrowthProfile,
    catalogs: ReportLabelCatalogs,
) -> PromptCoachView:
    """Build a prompt-quality view from proxy-only signals when session PQ is unavailable."""
    constraint_rate = (
        getattr(stats, "prompt_has_constraint_rate", None)
        or getattr(stats, "constraint_prompt_rate", 0.0)
        or 0.0
    )
    code_ctx_rate = (
        getattr(stats, "prompt_has_code_context_rate", None)
        or getattr(stats, "code_context_rate", 0.0)
        or 0.0
    )
    tool_error_rate = getattr(stats, "tool_error_rate", None)
    if tool_error_rate is None:
        tool_error_count = getattr(stats, "tool_error_count", None)
        if tool_error_count is None:
            tool_error_counts = getattr(stats, "tool_error_counts", {}) or {}
            tool_error_count = sum(tool_error_counts.values())
        tool_error_rate = (tool_error_count or 0) / max(stats.session_count, 1)
    else:
        tool_error_rate = tool_error_rate or 0.0
    heavy_rate = getattr(stats, "heavy_session_rate", 0.0) or 0.0

    dim_scores = {
        "constraint": constraint_rate,
        "context": code_ctx_rate,
        "clarity": max(0.0, 1.0 - tool_error_rate * 2),
        "depth": heavy_rate,
    }

    if all(v == 0.0 for v in dim_scores.values()):
        h_i18n = _view_i18n(catalogs).get("prompt_coach", {}).get("heuristic", {})
        return PromptCoachView(
            available=False,
            headline=h_i18n.get("unavailable_headline", ""),
            strongest_label="",
            weakest_label="",
            evidence_summary="",
            strength_habit="",
            source_note=h_i18n.get("unavailable_source_note", ""),
        )

    pc_i18n = _view_i18n(catalogs).get("prompt_coach", {})
    dim_labels = pc_i18n.get("heuristic_dim_labels", {})

    sorted_dims = sorted(dim_scores.items(), key=lambda kv: kv[1])
    weakest_key, weakest_val = sorted_dims[0]
    strongest_key, strongest_val = max(dim_scores.items(), key=lambda kv: kv[1])

    cards: list[PromptCoachTakeawayView] = []
    tl = _template_labels(catalogs)
    h_i18n = pc_i18n.get("heuristic", {})
    weakest_pct = round(weakest_val * 100)
    strongest_pct = round(strongest_val * 100)

    weakest_card = pc_i18n.get("heuristic_cards", {}).get(weakest_key, {})
    cards.append(
        PromptCoachTakeawayView(
            label=dim_labels.get(weakest_key, weakest_key),
            kind=tl.get("label_kind_gap", "Gap"),
            evidence=h_i18n.get("card_evidence_gap", "").format(pct=weakest_pct),
            message=weakest_card.get("message", ""),
            action=weakest_card.get("action", ""),
        )
    )

    reinforce_cfg = pc_i18n.get("heuristic_reinforce", {})
    if strongest_key == "context" and strongest_val > 0.5:
        reinforce = reinforce_cfg.get("context", {})
    elif strongest_key == "constraint" and strongest_val > 0.5:
        reinforce = reinforce_cfg.get("constraint", {})
    else:
        reinforce = reinforce_cfg.get("default", {})
    strongest_label = dim_labels.get(strongest_key, strongest_key)
    cards.append(
        PromptCoachTakeawayView(
            label=tl.get("label_reinforce_prefix", "Reinforce: ") + strongest_label,
            kind=tl.get("label_kind_strength", "Strength"),
            evidence=h_i18n.get("card_evidence_strength", "").format(pct=strongest_pct),
            message=reinforce.get("message", "").format(label=strongest_label),
            action=reinforce.get("action", "").format(label=strongest_label),
        )
    )

    headline = h_i18n.get("headline", "").format(label=dim_labels.get(weakest_key, weakest_key), pct=weakest_pct)
    evidence_summary = h_i18n.get("evidence_summary", "").format(
        constraint_pct=round(constraint_rate * 100),
        context_pct=round(code_ctx_rate * 100),
        tool_error_pct=round(tool_error_rate * 100),
    )
    strength_habit = h_i18n.get("strength_habit", "").format(label=dim_labels[strongest_key], pct=strongest_pct)

    return PromptCoachView(
        available=True,
        headline=headline,
        strongest_label=dim_labels[strongest_key],
        weakest_label=dim_labels[weakest_key],
        evidence_summary=evidence_summary,
        strength_habit=strength_habit,
        source_note=_prompt_quality_source_note(stats, h_i18n.get("source_note", ""), catalogs),
        dimension_scores=_build_prompt_dimension_scores(stats, catalogs),
        takeaways=cards[:3],
    )


def _build_prompt_coach(
    stats: GrowthProfile,
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
) -> PromptCoachView:
    if stats.pq_sessions_evaluated <= 0 or not stats.pq_avg_dimensions:
        return _build_heuristic_prompt_coach(stats, catalogs)

    dim_labels = _view_i18n(catalogs)["pq_dim_labels"]
    dims = stats.pq_avg_dimensions
    sorted_dims = sorted(dims.items(), key=lambda item: item[1])
    weakest = sorted_dims[0]
    strongest = max(dims.items(), key=lambda item: item[1])
    weak_dimensions = [dim_labels.get(name, name) for name, _ in sorted_dims[:2]]
    deficits = [
        _pq_deficit_display(name, count, catalogs)
        for name, count in sorted(stats.pq_deficit_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]
    pq_i18n = _view_i18n(catalogs).get("prompt_coach", {}).get("pq", {})
    evidence_key = "evidence_summary_heuristic" if session_read_mode == "heuristic" else "evidence_summary_llm"
    evidence_summary = pq_i18n.get(evidence_key, "").format(
        sessions=stats.pq_sessions_evaluated,
        score=stats.pq_avg_efficiency_score,
    )
    strongest_label = dim_labels.get(strongest[0], strongest[0])
    strength_habit = pq_i18n.get("strength_habit", "").format(label=strongest_label)
    headline = pq_i18n.get("headline", "").format(label=dim_labels.get(weakest[0], weakest[0]))
    if stats.pq_llm_session_count and stats.pq_heuristic_session_count:
        source_note = pq_i18n.get("source_note_mixed", "")
    elif stats.pq_llm_session_count:
        source_note = pq_i18n.get("source_note_llm", "")
    else:
        source_note = pq_i18n.get("source_note_heuristic", "")

    cards: list[PromptCoachTakeawayView] = _prompt_takeaways_from_real_samples(stats, catalogs)
    seen: set[str] = set()
    seen.update(item.label for item in cards)
    if not cards:
        primary_gap = _prompt_dimension_card(weakest[0], catalogs)
        seen.add(primary_gap.label)
        cards.append(primary_gap)
    overlap_deficits = _prompt_overlap_deficits(weakest[0])
    for deficit_key, count in sorted(stats.pq_deficit_counts.items(), key=lambda item: (-item[1], item[0])):
        if len(cards) >= 2:
            break
        if deficit_key in overlap_deficits and len(stats.pq_deficit_counts) > 1:
            continue
        card = _prompt_deficit_card(deficit_key, count, catalogs)
        if card.label not in seen:
            seen.add(card.label)
            cards.append(card)
    if len(cards) < 2:
        for dim_key, _score in sorted_dims:
            candidate = _prompt_dimension_card(dim_key, catalogs)
            if candidate.label not in seen:
                seen.add(candidate.label)
                cards.append(candidate)
            if len(cards) >= 2:
                break
    reinforce = _prompt_strength_card(strongest[0], catalogs)
    if reinforce.label not in seen:
        cards.append(reinforce)
    cards = cards[:3]

    return PromptCoachView(
        available=True,
        headline=headline,
        strongest_label=dim_labels.get(strongest[0], strongest[0]),
        weakest_label=dim_labels.get(weakest[0], weakest[0]),
        evidence_summary=evidence_summary,
        strength_habit=strength_habit,
        source_note=_prompt_quality_source_note(stats, source_note, catalogs),
        weak_dimensions=weak_dimensions,
        deficits=deficits,
        dimension_scores=_build_prompt_dimension_scores(stats, catalogs),
        takeaways=cards,
    )


def _prompt_quality_source_note(
    stats: GrowthProfile,
    base_note: str,
    catalogs: ReportLabelCatalogs,
) -> str:
    breakdown = _view_i18n(catalogs).get("prompt_coach", {}).get("source_breakdown", {})
    template = (
        breakdown.get("mixed")
        if stats.pq_llm_session_count and stats.pq_heuristic_session_count
        else breakdown.get("llm_only")
        if stats.pq_llm_session_count
        else breakdown.get("heuristic_only")
    )
    if not template:
        return base_note
    detail = template.format(
        total=stats.pq_sessions_evaluated,
        llm=stats.pq_llm_session_count,
        heuristic=stats.pq_heuristic_session_count,
        light=stats.pq_light_session_count,
    )
    return " ".join(part for part in (base_note, detail) if part).strip()


def _build_friction(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> FrictionSectionView:
    friction_i18n = _view_i18n(catalogs).get("friction", {})
    attribution = stats.friction_by_attribution
    total = sum(attribution.values())
    if total <= 0:
        return FrictionSectionView(
            headline=friction_i18n.get("empty_headline", ""),
            primary_source="",
        )
    primary = max(attribution.items(), key=lambda item: item[1])[0]
    tl = _template_labels(catalogs)
    primary_label_map = {
        "environmental": tl.get("friction_env", "Environment / tooling"),
        "ai-capability": tl.get("friction_ai", "AI capability"),
        "user-actionable": tl.get("friction_user", "User-actionable issues"),
    }
    primary_label = primary_label_map.get(primary, primary)
    categories = [
        FrictionCategoryView(label=_friction_label(label, catalogs), count=count)
        for label, count in sorted(stats.friction_type_counts.items(), key=lambda item: -item[1])[:4]
    ]
    actions = _friction_actions(primary, catalogs)
    headline = friction_i18n.get("primary_headline", "").format(primary_label=primary_label)
    return FrictionSectionView(headline=headline, primary_source=primary_label, categories=categories, actions=actions)


def _build_exemplars(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    redact: bool,
    catalogs: ReportLabelCatalogs,
) -> list[PersonalExemplarView]:
    result: list[PersonalExemplarView] = []
    seen_categories: set[str] = set()
    for exemplar in surface_highlights(sessions, session_reads, limit=8, include_ungrouped=True):
        category_label = _pattern_label(exemplar.pattern, catalogs)
        if category_label in seen_categories:
            continue
        meta = exemplar.meta
        project_name = "" if redact else (Path(meta.project_path).name if meta.project_path else "")
        result.append(
            PersonalExemplarView(
                category_label=category_label,
                score=round(exemplar.score, 2),
                project_name=project_name,
                summary=(
                    ""
                    if redact
                    else (
                        exemplar.facets.session_takeaway
                        if exemplar.facets.session_takeaway
                        else _build_heuristic_exemplar_summary(exemplar.meta, exemplar.facets.delivery_outcome, catalogs)
                    )
                ),
                facts=_exemplar_facts(exemplar, catalogs),
                why_keep=_exemplar_why_keep(exemplar, catalogs),
                technique=_exemplar_next_reuse(exemplar, catalogs),
            )
        )
        seen_categories.add(category_label)
        if len(result) >= 4:
            break
    return result


def _build_style_lens(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    agent_asset=None,
    *,
    catalogs: ReportLabelCatalogs,
) -> StyleLensSectionView:
    style: CollaborationStyleResult = compute_collaboration_style(
        stats,
        capability_scores,
        style_labels=catalogs.collaboration_style,
        agent_asset=agent_asset,
    )
    return StyleLensSectionView(
        archetype_name=style.archetype_name,
        archetype_tag=style.archetype_tag,
        slogan=style.slogan,
        description=style.description,
        strengths=style.strengths[:4],
        growth_areas=style.growth_areas[:4],
        dimensions=[
            StyleLensDimensionView(
                label=item.label,
                left_pole=item.left_pole,
                right_pole=item.right_pole,
                pct=item.pct,
                interpretation=item.interpretation,
            )
            for item in style.dimensions
        ],
    )


def _build_collaboration_rhythm(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> CollaborationRhythmSectionView:
    rhythm_i18n = _view_i18n(catalogs).get("collaboration_rhythm", {})
    rhythm_types = rhythm_i18n.get("types", {})
    rhythm_label_map = {key: data.get("label", key) for key, data in rhythm_types.items()}
    rhythm_summary_map = {key: data.get("summary", "") for key, data in rhythm_types.items()}
    next_action_map = {key: data.get("next_action", "") for key, data in rhythm_types.items()}

    rhythm_key = stats.collaboration_rhythm_type or "balanced"
    peak_hours = _top_hours(stats.messages_by_hour)
    weekday_name = _top_weekday(stats.weekday_session_counts, catalogs)
    tl = _template_labels(catalogs)
    stat_cards = [
        CollaborationRhythmStatView(
            label=tl.get("rhythm_stat_median", "Median session length"),
            value=f"{int(round(stats.median_session_duration_minutes or 0))} min",
            detail=tl.get("rhythm_detail_median", ""),
        ),
        CollaborationRhythmStatView(
            label=tl.get("rhythm_stat_peak", "Peak hours"),
            value=peak_hours,
            detail=tl.get("rhythm_detail_peak", ""),
        ),
        CollaborationRhythmStatView(
            label=tl.get("rhythm_stat_weekday", "Most active day"),
            value=weekday_name,
            detail=tl.get("rhythm_detail_weekday", ""),
        ),
    ]
    rhythm_label = rhythm_label_map.get(rhythm_key, rhythm_key)
    headline = rhythm_i18n.get("headline", "").format(rhythm_label=rhythm_label)
    return CollaborationRhythmSectionView(
        headline=headline,
        rhythm_label=rhythm_label,
        rhythm_summary=rhythm_summary_map.get(rhythm_key, ""),
        next_action=next_action_map.get(rhythm_key, ""),
        stats=stat_cards,
    )


def _format_compact_number(value: int | float, language: str) -> str:
    absolute = abs(float(value))
    if language == "zh":
        for threshold, suffix in ((100_000_000, "亿"), (10_000, "万")):
            if absolute >= threshold:
                scaled = value / threshold
                digits = 1 if abs(scaled) < 100 else 0
                return f"{scaled:.{digits}f}".rstrip("0").rstrip(".") + suffix
        return f"{int(round(value))}"

    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if absolute >= threshold:
            scaled = value / threshold
            digits = 1 if abs(scaled) < 100 else 0
            return f"{scaled:.{digits}f}".rstrip("0").rstrip(".") + suffix
    return f"{int(round(value))}"


def _format_currency_compact(amount: float | None) -> str:
    if amount is None or amount <= 0:
        return "--"
    absolute = abs(amount)
    if absolute >= 1_000_000:
        scaled, suffix = amount / 1_000_000, "M"
    elif absolute >= 1_000:
        scaled, suffix = amount / 1_000, "k"
    else:
        return f"${amount:.2f}".rstrip("0").rstrip(".")
    digits = 1 if abs(scaled) < 100 else 0
    return f"${scaled:.{digits}f}".rstrip("0").rstrip(".") + suffix


def _build_prompt_dimension_scores(
    stats: GrowthProfile,
    catalogs: ReportLabelCatalogs,
) -> list[PromptCoachDimensionView]:
    dims = stats.pq_avg_dimensions or {}
    if not dims:
        return []
    dim_labels = _view_i18n(catalogs).get("pq_dim_labels", {})
    ordered = sorted(dims.items(), key=lambda item: item[1])
    return [
        PromptCoachDimensionView(
            label=dim_labels.get(key, key),
            score=round(float(score), 1),
        )
        for key, score in ordered
    ]


def _build_usage_coverage_note(
    sessions: list[SessionRecord],
    catalogs: ReportLabelCatalogs,
) -> str:
    usage_i18n = _view_i18n(catalogs).get("usage_overview", {})
    tool_labels = {
        "codex": "Codex CLI",
        "cursor": "Cursor",
        "claude": "Claude Code",
        "claude_code": "Claude Code",
        "trae": "Trae",
        "qoder": "Qoder",
        "cline": "Cline",
        "kilo": "Kilo Code",
    }
    tool_has_usage: dict[str, bool] = {}
    for session in sessions:
        tool = session.tool_name or "unknown"
        has_usage = any(
            value not in (None, 0)
            for value in (
                session.input_tokens,
                session.output_tokens,
                session.cache_read_tokens,
                session.cache_write_tokens,
            )
        )
        tool_has_usage[tool] = tool_has_usage.get(tool, False) or has_usage
    if not tool_has_usage:
        return ""
    covered = [tool_labels.get(tool, tool) for tool, has_usage in tool_has_usage.items() if has_usage]
    missing = [tool_labels.get(tool, tool) for tool, has_usage in tool_has_usage.items() if not has_usage]
    if covered and missing:
        return usage_i18n.get("coverage_note_partial", "").format(
            covered=" / ".join(covered),
            missing=" / ".join(missing),
        )
    if not covered and missing:
        return usage_i18n.get("coverage_note_none", "").format(
            missing=" / ".join(missing),
        )
    return ""


def _build_usage_section(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> UsageSectionView:
    usage_i18n = _view_i18n(catalogs).get("usage_overview", {})
    language = getattr(catalogs, "language", "zh")
    total_tokens = (
        (getattr(stats, "total_input_tokens", 0) or 0)
        + (getattr(stats, "total_output_tokens", 0) or 0)
        + (getattr(stats, "total_cache_read_tokens", 0) or 0)
        + (getattr(stats, "total_cache_write_tokens", 0) or 0)
    )
    token_volume_display = (
        usage_i18n.get("unknown_usage", "--")
        if total_tokens <= 0
        else _format_compact_number(total_tokens, language)
    )
    cache_hit_rate = getattr(stats, "avg_cache_hit_rate", None)
    cache_read_tokens = getattr(stats, "total_cache_read_tokens", 0) or 0
    cache_write_tokens = getattr(stats, "total_cache_write_tokens", 0) or 0
    cache_hit_display = (
        "0%"
        if cache_hit_rate is None and (cache_read_tokens + cache_write_tokens) == 0
        else usage_i18n.get("unknown_cache", "--")
        if cache_hit_rate is None
        else f"{round(cache_hit_rate * 100)}%"
    )
    cost_display = (
        usage_i18n.get("unknown_cost", "--")
        if (getattr(stats, "total_cost_usd", 0.0) or 0.0) <= 0
        else _format_currency_compact(stats.total_cost_usd)
    )
    avg_cost_display = (
        usage_i18n.get("unknown_cost", "--")
        if (getattr(stats, "avg_cost_per_session", 0.0) or 0.0) <= 0
        else _format_currency_compact(stats.avg_cost_per_session)
    )
    advanced_ratio_pct = round((getattr(stats, "advanced_feature_ratio", 0.0) or 0.0) * 100)
    mcp_rate = round((getattr(stats, "mcp_session_rate", 0.0) or 0.0) * 100)
    subagent_count = getattr(stats, "subagent_session_count", 0)
    heavy_count = getattr(stats, "heavy_session_count", 0)
    avg_chain = round(getattr(stats, "avg_autonomous_chain_length", 0.0) or 0.0, 1)
    median_minutes = int(round(getattr(stats, "median_session_duration_minutes", 0.0) or 0.0))
    total_calls = sum(count for _name, count in getattr(stats, "top_tools", []))

    summary = usage_i18n.get("summary", "").format(
        session_count=stats.session_count,
        tool_calls=total_calls,
        token_volume=token_volume_display,
        advanced_feature_ratio=advanced_ratio_pct,
    )
    hero_support_line = usage_i18n.get("hero_support_line", "").format(
        summary=summary,
        total_cost=cost_display,
        avg_cost=avg_cost_display,
        cache_hit=cache_hit_display,
    )
    stats_cards = [
        UsageStatView(
            label=usage_i18n.get("token_card_label", "Token 体量"),
            value=usage_i18n.get("token_card_value", "{token_volume}").format(token_volume=token_volume_display),
            detail=usage_i18n.get("token_card_detail", "").format(
                input_tokens=_format_compact_number(getattr(stats, "total_input_tokens", 0) or 0, language),
                output_tokens=_format_compact_number(getattr(stats, "total_output_tokens", 0) or 0, language),
                cache_tokens=_format_compact_number(cache_read_tokens + cache_write_tokens, language),
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("cache_card_label", "成本 / 缓存"),
            value=usage_i18n.get("cache_card_value", "{total_cost} · {cache_hit}").format(
                total_cost=cost_display,
                cache_hit=cache_hit_display,
            ),
            detail=usage_i18n.get("cache_card_detail", "").format(
                avg_cost=avg_cost_display,
                cache_read=_format_compact_number(cache_read_tokens, language),
                cache_write=_format_compact_number(cache_write_tokens, language),
                cache_hit=cache_hit_display,
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("leverage_card_label", "高杠杆使用"),
            value=usage_i18n.get("leverage_card_value", "{advanced_feature_ratio}%").format(
                advanced_feature_ratio=advanced_ratio_pct
            ),
            detail=usage_i18n.get("leverage_card_detail", "").format(
                subagent_count=subagent_count,
                mcp_rate=mcp_rate,
                tool_diversity=getattr(stats, "tier_diversity_count", 0),
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("intensity_card_label", "协作强度"),
            value=usage_i18n.get("intensity_card_value", "{avg_chain}").format(avg_chain=avg_chain),
            detail=usage_i18n.get("intensity_card_detail", "").format(
                median_minutes=median_minutes,
                heavy_count=heavy_count,
            ),
        ),
    ]
    return UsageSectionView(
        headline=usage_i18n.get("headline", ""),
        summary=summary,
        hero_support_line=hero_support_line,
        memory_note=usage_i18n.get("memory_note", ""),
        stats=stats_cards,
    )


def _build_work_focus(
    stats: GrowthProfile,
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    redact: bool,
    catalogs: ReportLabelCatalogs,
) -> WorkFocusSectionView:
    recent_work = [] if redact else _recent_work_items(sessions, session_reads)[:4]
    total_goal_signals = max(sum(stats.goal_category_counts.values()), 1)
    top_goals = [
        FocusAreaView(
            label=_goal_label(name, catalogs),
            count=count,
            detail=(
                f"{round(count / total_goal_signals * 100)}%"
                if total_goal_signals > 0
                else ""
            ),
        )
        for name, count in sorted(stats.goal_category_counts.items(), key=lambda item: -item[1])[:4]
    ]
    top_tools = _rollup_tool_labels(stats.top_tools[:8], catalogs)[:5]
    top_languages = [FocusAreaView(label=name, count=count) for name, count in stats.top_languages[:4]]
    work_focus_i18n = _view_i18n(catalogs).get("work_focus", {})
    primary_goal = _primary_goal_from_session_reads(session_reads, catalogs) or (
        top_goals[0].label if top_goals else ""
    )
    primary_work = recent_work[0] if recent_work else ""
    headline_template = (
        work_focus_i18n.get("headline")
        if primary_goal and primary_work
        else work_focus_i18n.get("headline_goal_only")
        if primary_goal
        else work_focus_i18n.get("headline_work_only")
        if primary_work
        else work_focus_i18n.get("insufficient_headline")
    )
    headline = (headline_template or "").format(
        primary_goal=primary_goal,
        primary_work=primary_work,
    )
    return WorkFocusSectionView(headline=headline, recent_work=recent_work, goal_mix=top_goals, tools=top_tools, languages=top_languages)


def _build_wins(
    *,
    stats: GrowthProfile,
    capability: CapabilitySectionView,
    prompt_coach: PromptCoachView,
    style_lens: StyleLensSectionView,
    exemplars: list[PersonalExemplarView],
    catalogs: ReportLabelCatalogs,
) -> WinsSectionView:
    wins_i18n = _view_i18n(catalogs).get("wins", {})
    cards = wins_i18n.get("cards", {})
    strongest_dim = max(capability.dimensions, key=lambda item: item.score)
    sd = cards.get("strongest_dim", {})
    win_cards = [
        WinCardView(
            title=sd.get("title", "{label}").format(label=strongest_dim.label),
            evidence=sd.get("evidence", "{score:.1f}").format(score=strongest_dim.score),
            why_it_matters=strongest_dim.explanation,
            next_action=strongest_dim.next_action,
        )
    ]
    if stats.verification_behavior_rate >= 0.45 or (getattr(stats, "fully_achieved_rate", 0.0) or 0.0) >= 0.25:
        dc_meta = _view_i18n(catalogs).get("capability_meta", {}).get("delivery_closure", {})
        dc = cards.get("delivery_closure", {})
        delivery_dim = next((item for item in capability.dimensions if item.key == "delivery_closure"), None)
        delivery_score = delivery_dim.score if delivery_dim else round((getattr(stats, "fully_achieved_rate", 0.0) or 0.0) * 100, 1)
        delivery_label = dc_meta.get("label", delivery_dim.label if delivery_dim else "Delivery closure")
        win_cards.append(
            WinCardView(
                title=dc.get("title", "{label}").format(label=delivery_label),
                evidence=dc.get("evidence", "{score:.1f}").format(score=delivery_score, pct=round((stats.verification_behavior_rate or 0) * 100)),
                why_it_matters=dc.get("why", dc_meta.get("explanation", "")),
                next_action=dc.get("next_action", dc_meta.get("next_action", "")),
            )
        )
    elif prompt_coach.available:
        ps = cards.get("prompt_strength", {})
        win_cards.append(
            WinCardView(
                title=ps.get("title", "{label}").format(label=prompt_coach.strongest_label),
                evidence=prompt_coach.strength_habit,
                why_it_matters=ps.get("why", ""),
                next_action=ps.get("next_action", "{weakest_label}").format(
                    weakest_label=prompt_coach.weakest_label
                ),
            )
        )
    if exemplars:
        ex = cards.get("exemplars", {})
        exemplar_labels = " / ".join(
            list(dict.fromkeys(item.category_label for item in exemplars if item.category_label))[:2]
        )
        win_cards.append(
            WinCardView(
                title=ex.get("title", ""),
                evidence=ex.get("evidence", "").format(count=len(exemplars), labels=exemplar_labels),
                why_it_matters=ex.get("why", ""),
                next_action=ex.get("next_action", ""),
            )
        )
    if len(win_cards) < 3 and style_lens.strengths:
        sl = cards.get("style_lens", {})
        win_cards.append(
            WinCardView(
                title=sl.get("title", ""),
                evidence=style_lens.strengths[0],
                why_it_matters=sl.get("why", ""),
                next_action=sl.get("next_action", ""),
            )
        )
    headline = wins_i18n.get("headline", "")
    return WinsSectionView(headline=headline, wins=win_cards[:3])


def _build_level_guide(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> LevelGuideSectionView:
    current_level = stats.growth_level or _view_i18n(catalogs).get("summary", {}).get("growth_level_unrated", "Unrated")
    current_score = stats.mirror_score
    lg = _level_guide_i18n(catalogs)
    headline = (
        lg.get("headline", "").format(current_level=current_level, current_score=current_score)
        if stats.growth_level
        else lg.get("headline_unrated", "")
    )
    levels = lg.get("levels", {})
    items = []
    for level_key in ("L1", "L2", "L3", "L4", "L5"):
        data = levels.get(level_key, {})
        items.append(
            LevelGuideItemView(
                level_key,
                format_growth_level_score_range(level_key) or data.get("score_range", ""),
                data.get("title", ""),
                data.get("description", ""),
                data.get("signals", []),
                data.get("next_step", ""),
                stats.growth_level == level_key,
            )
        )
    return LevelGuideSectionView(headline=headline, current_level=current_level, current_score=current_score, items=items)


_LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}


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


def _build_level_evidence(
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


def _compute_date_range(sessions: list[SessionRecord], since: Optional[datetime] = None, until: Optional[datetime] = None) -> str:
    times = [s.start_time for s in sessions if s.start_time]
    end_times = [s.end_time for s in sessions if s.end_time]
    if not times:
        return ""
    earliest = min(times)[:10]
    latest = max(end_times)[:10] if end_times else max(times)[:10]
    if since is not None:
        earliest = max(earliest, since.strftime("%Y-%m-%d"))
    if until is not None:
        latest = min(latest, until.strftime("%Y-%m-%d"))
    return f"{earliest} – {latest}"


def _friction_label(label: str, catalogs: ReportLabelCatalogs) -> str:
    return _view_i18n(catalogs)["friction_labels"].get(label, label)


def _friction_actions(primary: str, catalogs: ReportLabelCatalogs) -> list[str]:
    actions = _view_i18n(catalogs).get("friction", {}).get("actions", {})
    return list(actions.get(primary, actions.get("ai-capability", [])))


def _exemplar_facts(exemplar: Exemplar, catalogs: ReportLabelCatalogs) -> str:
    meta = exemplar.meta
    total_calls = sum(meta.tool_counts.values())
    fact_labels = _view_i18n(catalogs).get("exemplar_fact_labels", {})
    parts = [fact_labels.get("files", "{count} files").format(count=meta.files_modified)]
    if meta.git_commits:
        parts.append(fact_labels.get("commits", "{count} commits").format(count=meta.git_commits))
    if meta.has_verification_behavior:
        parts.append(fact_labels.get("verification", "verification loop"))
    if meta.prompt_has_constraint:
        parts.append(fact_labels.get("constraints", "constraints upfront"))
    if meta.prompt_has_code_context:
        parts.append(fact_labels.get("context", "code context"))
    parts.append(fact_labels.get("tool_calls", "{count} tool calls").format(count=total_calls))
    parts.append(
        fact_labels.get("max_chain", "max chain {count}").format(
            count=max(meta.autonomous_chain_lengths) if meta.autonomous_chain_lengths else 0
        )
    )
    return " · ".join(parts)


def _exemplar_why_keep(exemplar: Exemplar, catalogs: ReportLabelCatalogs) -> str:
    techniques = _view_i18n(catalogs)["exemplar_techniques"]
    templates = _view_i18n(catalogs).get("exemplar_why_templates", {})
    phrases = _view_i18n(catalogs).get("exemplar_signal_phrases", {})
    ranked = [
        phrases[key]
        for key, weight in sorted(exemplar.signal_weights.items(), key=lambda item: (-item[1], item[0]))
        if weight > 0 and key in phrases
    ][:2]
    if len(ranked) >= 2:
        return templates.get("double", "The method is worth keeping because you first {first}, then {second}.").format(
            first=ranked[0],
            second=ranked[1],
        )
    if ranked:
        return templates.get("single", "The method is worth keeping because you {first}.").format(first=ranked[0])
    return techniques.get(exemplar.pattern, techniques["general"])


def _exemplar_next_reuse(exemplar: Exemplar, catalogs: ReportLabelCatalogs) -> str:
    actions = _view_i18n(catalogs).get("exemplar_reuse_actions", {})
    default_action = actions.get("general", "")
    return actions.get(exemplar.pattern, default_action)


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _top_hours(hours: list[int]) -> str:
    ranked = sorted([(hour, count) for hour, count in enumerate(hours or []) if count > 0], key=lambda item: (-item[1], item[0]))[:3]
    if not ranked:
        return "--"
    return " / ".join(f"{hour:02d}:00" for hour, _ in ranked)


def _top_weekday(counts: list[int], catalogs: ReportLabelCatalogs) -> str:
    labels = _view_i18n(catalogs)["weekdays"]
    ranked = sorted([(idx, count) for idx, count in enumerate(counts or []) if count > 0], key=lambda item: (-item[1], item[0]))
    if not ranked:
        return "--"
    return labels[ranked[0][0]]


def _goal_label(name: str, catalogs: ReportLabelCatalogs) -> str:
    labels = _view_i18n(catalogs).get("goal_labels", {})
    return labels.get(name, name)


def _display_project_name(name: str) -> str:
    return clean_project_name(name)


def _display_tool_name(name: str, catalogs: ReportLabelCatalogs) -> str:
    mapping = _view_i18n(catalogs).get("tool_labels", {})
    if name.startswith("mcp__"):
        return _view_i18n(catalogs).get("tool_label_mcp", "MCP tool")
    return mapping.get(name, name.replace("_", " "))


def _rollup_projects(items: list[tuple[str, int]]) -> list[str]:
    seen: list[str] = []
    for name, _count in items:
        display = _display_project_name(name)
        if display and display not in seen:
            seen.append(display)
    return seen


def _primary_goal_from_session_reads(session_reads: list[SessionRead], catalogs: ReportLabelCatalogs) -> str:
    counts: dict[str, int] = {}
    for read in session_reads or []:
        if read.confidence == "low":
            continue
        for key, count in (read.work_intent_mix or {}).items():
            counts[key] = counts.get(key, 0) + int(count or 0)
    if not counts:
        return ""
    primary_key = max(counts.items(), key=lambda item: item[1])[0]
    return _goal_label(primary_key, catalogs)


def _recent_work_items(sessions: list[SessionRecord], session_reads: list[SessionRead]) -> list[str]:
    rows: list[str] = []
    read_by_session = {read.session_id: read for read in session_reads or []}
    sorted_sessions = sorted(
        sessions,
        key=lambda session: session.start_time or "",
        reverse=True,
    )
    for session in sorted_sessions:
        read = read_by_session.get(session.session_id)
        item = _work_item_from_session_read(read) if read else ""
        if not item:
            source = session.first_prompt or (session.top_user_messages[0] if session.top_user_messages else "")
            item = _work_item_from_prompt(source)
        if item and item not in rows:
            rows.append(item)
        if len(rows) >= 4:
            break
    return rows


def _work_item_from_session_read(read: SessionRead | None) -> str:
    if not read or read.confidence == "low":
        return ""
    source = read.work_summary or read.session_takeaway or read.key_gain
    if not source:
        return ""
    return _trim_text(_sanitize_work_item_source(source), 48)


_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s，。；;]+|/Users/[^\s，。；;]+|/home/[^\s，。；;]+|\\\\\?\\[^\s，。；;]+)"
)
_WORK_ITEM_NOISE_PATTERNS = (
    r"^根据下面的内容\s*review\s*[，,、和并]*\s*",
    r"^review\s*[，,、和并]*\s*",
    r"^使用\s*$",
    r"^解决报错\s*",
    r"^实现下面的功能\s*[，,、和并]*\s*",
    r"^并完善相关的文档\s*",
    r"^修复\s*review\s*到的问题\s*[，,、和并]*\s*",
)


def _work_item_from_prompt(value: str) -> str:
    text = " ".join((value or "").replace("\n", " ").split())
    if not text:
        return ""
    text = _sanitize_work_item_source(text)
    for pattern in (
        r"(?:目标结果|目标|本次任务|任务|当前问题|本次对象)[:：]\s*([^。；;.!?\n]+)",
        r"(?:help me|please|请|帮我)\s*([^。；;.!?\n]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ：:，,")
            if candidate:
                return _trim_text(candidate, 48)
    first_sentence = re.split(r"[。；;.!?]", text, maxsplit=1)[0].strip(" ：:，,")
    return _trim_text(first_sentence, 48)


def _sanitize_work_item_source(value: str) -> str:
    text = _PATH_RE.sub(" ", value)
    text = re.sub(r"\s+", " ", text).strip(" ：:，,、")
    changed = True
    while changed:
        changed = False
        for pattern in _WORK_ITEM_NOISE_PATTERNS:
            new_text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip(" ：:，,、")
            if new_text != text:
                text = new_text
                changed = True
    if not text:
        return ""
    theme_rules = (
        (r"报告闭环", "修复报告闭环与展示问题"),
        (r"文档", "实现功能并完善文档"),
        (r"报错|exception|traceback", "定位并修复报错"),
        (r"功能", "实现功能需求"),
        (r"review", "根据 review 修复问题"),
    )
    for pattern, label in theme_rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return text


def _rollup_tool_labels(items: list[tuple[str, int]], catalogs: ReportLabelCatalogs) -> list[FocusAreaView]:
    merged: dict[str, int] = {}
    details: dict[str, list[str]] = {}
    for name, count in items:
        label = _display_tool_name(name, catalogs)
        merged[label] = merged.get(label, 0) + count
        details.setdefault(label, []).append(name)
    ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    return [
        FocusAreaView(label=label, count=count, detail=" / ".join(sorted(set(details.get(label, [])))))
        for label, count in ranked
    ]


def _prompt_takeaways_from_real_samples(
    stats: GrowthProfile,
    catalogs: ReportLabelCatalogs,
) -> list[PromptCoachTakeawayView]:
    pc_i18n = _view_i18n(catalogs).get("prompt_coach", {})
    actions = pc_i18n.get("takeaway_actions", {})
    takeaways: list[PromptCoachTakeawayView] = []
    seen: set[str] = set()
    for item in getattr(stats, "pq_top_takeaways", []) or []:
        label = item.label or item.category.replace("_", " ").replace("-", " ")
        if label in seen:
            continue
        if item.type == "improve" and item.better_prompt:
            takeaways.append(
                PromptCoachTakeawayView(
                    label=label,
                    kind=actions.get("kind_example", "Example"),
                    evidence=_trim_text(item.original or item.message_ref, 140),
                    message=item.why or pc_i18n.get("dimension_gap_message", ""),
                    action=actions.get("improve", "Use the structure below for your next opening message."),
                    better_prompt=item.better_prompt,
                )
            )
        elif item.type == "reinforce":
            takeaways.append(
                PromptCoachTakeawayView(
                    label=label,
                    kind=actions.get("kind_reinforce", "Reinforce"),
                    evidence=_trim_text(item.what_worked or item.message_ref, 140),
                    message=item.why_effective or pc_i18n.get("strength_card", {}).get("message", ""),
                    action=actions.get("reinforce", "Carry this working pattern into a different task type."),
                    better_prompt="",
                )
            )
        seen.add(label)
        if len(takeaways) >= 2:
            break
    return takeaways


def _prompt_dimension_card(dim_key: str, catalogs: ReportLabelCatalogs) -> PromptCoachTakeawayView:
    pc_i18n = _view_i18n(catalogs).get("prompt_coach", {})
    cards = pc_i18n.get("dimension_cards", {})
    meta = cards.get(dim_key)
    if meta is None:
        meta = next(iter(cards.values()), {})
    label = meta.get("label", "")
    kind = meta.get("kind", "")
    evidence = meta.get("evidence", "")
    action = meta.get("action", "")
    better_prompt = meta.get("better_prompt", "")
    message = pc_i18n.get("dimension_gap_message", "")
    return PromptCoachTakeawayView(label=label, kind=kind, evidence=evidence, message=message, action=action, better_prompt=better_prompt)


def _prompt_deficit_card(deficit_key: str, count: int, catalogs: ReportLabelCatalogs) -> PromptCoachTakeawayView:
    pc_i18n = _view_i18n(catalogs).get("prompt_coach", {})
    meta = pc_i18n.get("deficit_cards", {}).get(deficit_key)
    if meta is None:
        meta = next(iter(pc_i18n.get("deficit_cards", {}).values()), {})
    label = meta.get("label", "")
    kind = meta.get("kind", "")
    evidence = meta.get("evidence", "").format(count=count)
    action = meta.get("action", "")
    message = pc_i18n.get("deficit_message", "")
    return PromptCoachTakeawayView(label=label, kind=kind, evidence=evidence, message=message, action=action, better_prompt="")


def _prompt_overlap_deficits(dim_key: str) -> set[str]:
    mapping = {
        "context_provision": {"missing-context"},
        "request_specificity": {"vague-request"},
        "information_timing": {"missing-context"},
        "correction_quality": {"unclear-correction"},
    }
    return mapping.get(dim_key, set())


def _prompt_strength_card(dim_key: str, catalogs: ReportLabelCatalogs) -> PromptCoachTakeawayView:
    dim_labels = _view_i18n(catalogs)["pq_dim_labels"]
    label = dim_labels.get(dim_key, dim_key)
    tl = _template_labels(catalogs)
    card = _view_i18n(catalogs).get("prompt_coach", {}).get("strength_card", {})
    return PromptCoachTakeawayView(
        label=card.get("label_prefix", "{label}").format(label=label),
        kind=tl.get("label_kind_strength", "Strength"),
        evidence=card.get("evidence", ""),
        message=card.get("message", ""),
        action=card.get("action", "").format(label=label),
        better_prompt="",
    )


def _pq_deficit_display(name: str, count: int, catalogs: ReportLabelCatalogs) -> str:
    deficit_labels = _guidance_labels(catalogs).get("pq_labels", {}).get("deficit", {})
    label = deficit_labels.get(name.replace("-", "_"), name)
    fmt = _view_i18n(catalogs).get("pq_deficit_count_format", "{label} x {count}")
    return fmt.format(label=label, count=count)


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


def _build_heuristic_exemplar_summary(
    meta: SessionRecord,
    outcome: str,
    catalogs: ReportLabelCatalogs,
) -> str:
    """Synthesize a readable summary for heuristic-mode exemplars (no LLM brief_summary)."""
    summary_i18n = _view_i18n(catalogs).get("exemplar_summary", {})
    radar_i18n = _view_i18n(catalogs).get("radar_axes", {})
    outcome_labels = summary_i18n.get("outcome_labels", {})
    project = Path(meta.project_path).name if meta.project_path else ""
    prompt_snippet = (meta.first_prompt or "")[:80].strip()
    if prompt_snippet and prompt_snippet[-1] not in ("。", ".", "?", "？", "！", "!"):
        prompt_snippet += "…"
    outcome_label = outcome_labels.get(outcome or "", summary_i18n.get("default_outcome", ""))
    tools_total = sum(meta.tool_counts.values())
    parts: list[str] = []
    if project:
        parts.append(summary_i18n.get("project", "").format(project=project))
    if prompt_snippet:
        parts.append(summary_i18n.get("task", "").format(prompt_snippet=prompt_snippet))
    parts.append(
        summary_i18n.get("outcome", "").format(
            outcome_label=outcome_label,
            files_modified=meta.files_modified,
            tools_total=tools_total,
        )
    )
    if meta.has_verification_behavior:
        delivery_note = radar_i18n.get("delivery_closure", {}).get("reason_high", "")
        if delivery_note:
            parts.append(delivery_note)
    if meta.git_commits:
        parts.append(summary_i18n.get("commits", "").format(git_commits=meta.git_commits))
    separator = summary_i18n.get("separator", "; ")
    return separator.join(parts)


def empty_prompt_coach_view() -> PromptCoachView:
    return PromptCoachView(
        available=False,
        headline="",
        strongest_label="",
        weakest_label="",
        evidence_summary="",
        strength_habit="",
    )


def build_prompt_coach_view_from_payload(payload: dict | None) -> PromptCoachView:
    if not isinstance(payload, dict) or not payload:
        return empty_prompt_coach_view()
    source_summary_payload = payload.get("source_summary") or {}
    source_summary = PromptCoachSourceSummaryView(
        llm_session_count=int(source_summary_payload.get("llm_session_count", 0) or 0),
        heuristic_session_count=int(source_summary_payload.get("heuristic_session_count", 0) or 0),
        light_session_count=int(source_summary_payload.get("light_session_count", 0) or 0),
        evaluated_user_messages=int(source_summary_payload.get("evaluated_user_messages", 0) or 0),
        run_mode=str(source_summary_payload.get("run_mode", "llm") or "llm"),
        llm_evaluated_count=int(source_summary_payload.get("llm_evaluated_count", 0) or 0),
        insufficient_count=int(source_summary_payload.get("insufficient_count", 0) or 0),
        llm_failed_count=int(source_summary_payload.get("llm_failed_count", 0) or 0),
        llm_unavailable_count=int(source_summary_payload.get("llm_unavailable_count", 0) or 0),
    )
    rewrite_cards = [
        PromptCoachRewriteCardView(
            id=str(item.get("id", "")),
            scene=str(item.get("scene", "")),
            original=str(item.get("original", "")),
            problem=str(item.get("problem", "")),
            better_prompt=str(item.get("better_prompt", "")),
            why=str(item.get("why", "")),
            category=str(item.get("category", "")),
            confidence=str(item.get("confidence", "")),
            evidence_refs=[str(ref) for ref in item.get("evidence_refs", []) if ref],
            source_note=str(item.get("source_note", "")),
        )
        for item in payload.get("rewrite_cards", [])
        if isinstance(item, dict)
    ]
    universal_payload = payload.get("universal_template") or {}
    universal_template = None
    if isinstance(universal_payload, dict) and universal_payload:
        universal_template = PromptCoachTemplateView(
            id=str(universal_payload.get("id", "")),
            title=str(universal_payload.get("title", "")),
            scene=str(universal_payload.get("scene", "")),
            common_gap=str(universal_payload.get("common_gap", "")),
            template=str(universal_payload.get("body") or universal_payload.get("template", "")),
        )
    friction_synthesis = [
        PromptCoachFrictionSynthesisView(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            explanation=str(item.get("explanation", "")),
            next_action=str(item.get("next_action", "")),
            confidence=int(item.get("confidence", 0) or 0),
            evidence_refs=[str(ref) for ref in item.get("evidence_refs", []) if ref],
            generated_by=str(item.get("generated_by", "rule") or "rule"),
        )
        for item in payload.get("friction_synthesis", [])
        if isinstance(item, dict)
    ]
    return PromptCoachView(
        available=bool(payload.get("headline") or rewrite_cards or friction_synthesis or universal_template),
        headline=str(payload.get("headline", "")),
        strongest_label=str(payload.get("strongest_label", "")),
        weakest_label=str(payload.get("weakest_label", "")),
        evidence_summary=str(payload.get("evidence_summary", "")),
        strength_habit=str(payload.get("strength_habit", "")),
        source_note=str(payload.get("source_note", "")),
        light_state_note=str(payload.get("light_state_note", "")),
        source_summary=source_summary,
        weak_dimensions=[str(item) for item in payload.get("weak_dimensions", []) if item],
        deficits=[str(item) for item in payload.get("deficits", []) if item],
        rewrite_cards=rewrite_cards,
        universal_template=universal_template,
        friction_synthesis=friction_synthesis,
    )
