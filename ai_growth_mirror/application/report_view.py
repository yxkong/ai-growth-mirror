"""Personal AI growth report view assembly (application layer)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..domain.session.model import SessionRecord

if TYPE_CHECKING:
    from ..domain.common.contracts import LlmGateway
from ..domain.signals.model import SessionRead
from ..domain.growth.model import (
    AgentAssetStats,
    GrowthGap,
    GrowthProfile,
    GrowthStage,
    RadarAxis,
)
from ..domain.growth.capability import compute_capability_scores
from ..domain.growth.scorer import format_growth_level_score_range
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
from .prompt_coach_views import PromptCoachView
from .work_focus import WorkFocusSectionView, build_work_focus
from .level_evidence import (
    LevelEvidenceSectionView,
    build_level_evidence_section,
)
from .usage_overview import (
    UsageSectionView,
    build_usage_coverage_note,
    build_usage_section,
)


def _view_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.view_model


def _level_guide_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.level_guide


def _template_labels(catalogs: ReportLabelCatalogs) -> dict[str, str]:
    return catalogs.template_labels


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
    stats: GrowthProfile
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
    llm: Optional["LlmGateway"] = None,
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
    level_evidence = build_level_evidence_section(stats, capability_scores, session_read_mode, catalogs)
    collaboration_rhythm = _build_collaboration_rhythm(stats, catalogs)
    usage = build_usage_section(stats, catalogs)
    usage.coverage_note = build_usage_coverage_note(sessions, catalogs)
    work_focus = build_work_focus(
        stats,
        sessions,
        session_reads,
        redact,
        catalogs,
        llm=llm,
        language=catalogs.language,
    )
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
        stats=stats,
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


def _build_level_evidence(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
) -> LevelEvidenceSectionView:
    return build_level_evidence_section(stats, capability_scores, session_read_mode, catalogs)


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
    return ""


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


def _display_project_name(name: str) -> str:
    return clean_project_name(name)


def _rollup_projects(items: list[tuple[str, int]]) -> list[str]:
    seen: list[str] = []
    for name, _count in items:
        display = _display_project_name(name)
        if display and display not in seen:
            seen.append(display)
    return seen


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
