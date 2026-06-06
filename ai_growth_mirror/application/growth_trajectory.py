"""Application view assembly for growth trajectory surfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Optional

from ..domain.growth.model import GrowthProfile
from ..domain.signals.model import SessionRead
from ..domain.snapshots.comparison import compare_snapshot_sources
from ..domain.snapshots.model import SnapshotCoverage, SnapshotMethodAssets, SnapshotPromptQuality, SnapshotSource
from ..domain.snapshots.trajectory import (
    ACTIONABLE_FRICTION_ORDER,
    assess_snapshot_point_confidence,
    build_snapshot_trajectory_window,
)
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from .growth_plan import GrowthPlanView
    from .prompt_coach import PromptCoachView
    from .report_view import (
        AgentAssetFootprintView,
        CapabilitySectionView,
        PersonalExemplarView,
        PersonalSummaryView,
    )


@dataclass
class GrowthTrajectorySummaryCardView:
    label: str
    value: str
    caption: str
    tone: str = "neutral"


@dataclass
class GrowthTrajectoryAxisView:
    key: str
    label: str
    previous: float
    current: float
    delta: float
    direction: str
    explanation: str


@dataclass
class GrowthTrajectoryWaterfallStepView:
    key: str
    label: str
    delta: float
    contribution: float
    direction: str


@dataclass
class GrowthTrajectoryPromptQualityView:
    available: bool
    headline: str
    summary: str
    source_note: str
    confidence_note: str
    improved: list[str] = field(default_factory=list)
    worsened: list[str] = field(default_factory=list)


@dataclass
class GrowthTrajectoryFrictionTypeView:
    label: str
    previous: int
    current: int
    delta: int
    direction: str


@dataclass
class GrowthTrajectoryFrictionView:
    summary: str
    recovery_note: str
    reduced_types: list[str] = field(default_factory=list)
    increased_types: list[str] = field(default_factory=list)
    changes: list[GrowthTrajectoryFrictionTypeView] = field(default_factory=list)


@dataclass
class GrowthTrajectoryMethodMetricView:
    label: str
    previous: str
    current: str
    delta: str


@dataclass
class GrowthTrajectoryMethodAssetsView:
    summary: str
    detail: str
    metrics: list[GrowthTrajectoryMethodMetricView] = field(default_factory=list)


@dataclass
class GrowthTrajectoryEvidenceCardView:
    title: str
    body: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class GrowthTrajectoryPriorityView:
    title: str
    body: str
    reasons: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class GrowthTrajectoryPointView:
    snapshot_id: str
    generated_at: str
    date: str
    mirror_score: int
    growth_level: str
    sample_count: int
    confidence: str
    axis_schema: str = "current"
    comparable: bool = True


@dataclass
class GrowthTrajectorySeriesView:
    key: str
    label: str
    color: str
    polyline: str
    points: list[dict[str, object]] = field(default_factory=list)
    y_ticks: list[dict[str, object]] = field(default_factory=list)
    latest_delta: float = 0.0
    latest_value: float = 0.0
    previous_value: float = 0.0
    latest_label: str = ""
    delta_label: str = ""
    trend_label: str = ""
    start_label: str = ""
    end_label: str = ""
    source_note: str = ""
    insufficient_note: str = ""
    area_path: str = ""


@dataclass
class GrowthTrajectoryTrendView:
    available: bool
    window_days: int
    window_label: str
    summary_code: str
    summary_label: str
    summary_text: str
    confidence_note: str
    data_sufficiency: str
    empty_state: str = ""
    points: list[GrowthTrajectoryPointView] = field(default_factory=list)
    score_series: Optional[GrowthTrajectorySeriesView] = None
    axis_series: list[GrowthTrajectorySeriesView] = field(default_factory=list)
    prompt_quality_series: list[GrowthTrajectorySeriesView] = field(default_factory=list)
    friction_series: list[GrowthTrajectorySeriesView] = field(default_factory=list)


@dataclass
class HumanCostTrendView:
    """View model for human_cost_reduction trend between snapshots."""

    available: bool = False
    direction: str = "unknown"  # "improving" | "worsening" | "flat" | "unknown"
    note: str = ""
    previous_rate_pct: str = ""
    current_rate_pct: str = ""
    delta_pct: str = ""


@dataclass
class GrowthTrajectoryView:
    available: bool
    prev_label: str = ""
    overview: str = ""
    confidence_note: str = ""
    trend: Optional[GrowthTrajectoryTrendView] = None
    summary_cards: list[GrowthTrajectorySummaryCardView] = field(default_factory=list)
    axis_deltas: list[GrowthTrajectoryAxisView] = field(default_factory=list)
    waterfall_steps: list[GrowthTrajectoryWaterfallStepView] = field(default_factory=list)
    prompt_quality: Optional[GrowthTrajectoryPromptQualityView] = None
    friction: Optional[GrowthTrajectoryFrictionView] = None
    method_assets: Optional[GrowthTrajectoryMethodAssetsView] = None
    evidence_cards: list[GrowthTrajectoryEvidenceCardView] = field(default_factory=list)
    next_priorities: list[GrowthTrajectoryPriorityView] = field(default_factory=list)
    human_cost_trend: Optional[HumanCostTrendView] = None
    data: dict[str, object] = field(default_factory=dict)


@dataclass
class SnapshotCompareReportView:
    prompt_coach: "PromptCoachView"


@dataclass
class SnapshotComparisonPageView:
    title: str
    subtitle: str
    left_snapshot_id: str
    right_snapshot_id: str
    left_created_at: str
    right_created_at: str
    left_date_range: str
    right_date_range: str
    left_headline: str
    right_headline: str
    trajectory: GrowthTrajectoryView
    report: SnapshotCompareReportView
    data: dict[str, object] = field(default_factory=dict)


def build_runtime_snapshot_source(
    *,
    stats: GrowthProfile,
    session_reads: list[SessionRead],
    summary: "PersonalSummaryView",
    capability: "CapabilitySectionView",
    prompt_coach: "PromptCoachView",
    growth_plan: "GrowthPlanView",
    agent_asset: Optional["AgentAssetFootprintView"],
    exemplars: list["PersonalExemplarView"],
    tool_display_name: str,
    date_range: str,
    created_at: str,
    quality_eligible: int = 0,
    extraction_failed: int = 0,
) -> SnapshotSource:
    evidence_by_topic = _build_runtime_evidence(
        session_reads=session_reads,
        prompt_coach=prompt_coach,
        growth_plan=growth_plan,
        exemplars=exemplars,
        summary=summary,
    )
    strongest = max(capability.dimensions, key=lambda item: item.score).key if capability.dimensions else ""
    weakest = min(capability.dimensions, key=lambda item: item.score).key if capability.dimensions else ""
    prompt_quality_dimensions = {
        key: round(float(value), 1)
        for key, value in (stats.pq_avg_dimensions or {}).items()
    }
    actionable_friction_counts = _build_actionable_friction_counts(stats)
    source = SnapshotSource(
        snapshot_id="current",
        created_at=created_at,
        date_range=date_range,
        tool_display_name=tool_display_name,
        growth_level=summary.growth_level,
        mirror_score=summary.mirror_score,
        headline=summary.headline,
        next_focus=summary.next_focus,
        strongest_axis_key=strongest,
        weakest_axis_key=weakest,
        axis_scores={item.key: float(item.score) for item in capability.dimensions},
        prompt_quality_dimensions=prompt_quality_dimensions,
        actionable_friction_counts=actionable_friction_counts,
        prompt_quality=SnapshotPromptQuality(
            efficiency_score=float(stats.pq_avg_efficiency_score) if stats.pq_sessions_evaluated else None,
            evaluated_sessions=stats.pq_sessions_evaluated,
            llm_sessions=stats.pq_llm_session_count,
            heuristic_sessions=stats.pq_heuristic_session_count,
            light_sessions=stats.pq_light_session_count,
            deficits=dict(stats.pq_deficit_counts),
        ),
        friction_type_counts=dict(stats.friction_type_counts),
        friction_by_attribution=dict(stats.friction_by_attribution),
        human_intervention_session_rate=(
            float(stats.human_intervention_session_rate)
            if stats.session_count
            else None
        ),
        method_assets=SnapshotMethodAssets(
            skill_files=agent_asset.skill_count if agent_asset else 0,
            prompt_files=agent_asset.prompt_count if agent_asset else 0,
            rule_files=agent_asset.rule_count if agent_asset else 0,
            total_asset_files=(agent_asset.skill_count + agent_asset.prompt_count + agent_asset.rule_count) if agent_asset else 0,
            unique_skill_count=stats.unique_skill_count,
            workflow_build_substantial_count=stats.workflow_build_substantial_count,
            workflow_build_moderate_count=stats.workflow_build_moderate_count,
            ai_authoring_distinct_categories=stats.ai_authoring_distinct_categories,
            assetized_session_rate=stats.assetized_session_rate,
        ),
        coverage=SnapshotCoverage(
            session_count=stats.session_count,
            session_read_count=len(session_reads),
            quality_eligible=quality_eligible or 0,
            extraction_failed=extraction_failed,
            has_usage_data=_has_usage_data(stats),
        ),
        evidence_by_topic=evidence_by_topic,
        sample_count=len(session_reads) or stats.session_count,
    )
    source.point_confidence = assess_snapshot_point_confidence(source)
    return source


def build_growth_trajectory_view(
    *,
    current_source: SnapshotSource,
    previous_source: SnapshotSource | None,
    history_sources: list[SnapshotSource] | None,
    catalogs: ReportLabelCatalogs,
) -> GrowthTrajectoryView:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    all_sources = list(history_sources or [])
    all_sources.append(current_source)
    trajectory_window = build_snapshot_trajectory_window(all_sources, window_days=30)
    trend_view = _build_trend_view(trajectory_window, catalogs)
    base_data = _trajectory_window_to_dict(trajectory_window)
    if previous_source is None:
        base_data["available"] = False
        return GrowthTrajectoryView(
            available=False,
            trend=trend_view,
            data=base_data,
        )
    comparison = compare_snapshot_sources(previous_source, current_source)
    view = _build_latest_vs_previous_view_from_comparison(comparison, catalogs)
    latest_vs_previous = base_data.get("latest_vs_previous", {}) or {}
    latest_vs_previous.update(_latest_vs_previous_dict(comparison))
    base_data["available"] = True
    base_data["latest_vs_previous"] = latest_vs_previous
    view.available = True
    view.trend = trend_view
    view.data = base_data
    return view


def build_snapshot_compare_page_view(
    *,
    left_source: SnapshotSource,
    right_source: SnapshotSource,
    catalogs: ReportLabelCatalogs,
    current_prompt_coach_payload: dict | None = None,
) -> SnapshotComparisonPageView:
    from .report_view import build_prompt_coach_view_from_payload

    comparison = compare_snapshot_sources(left_source, right_source)
    trajectory = _build_latest_vs_previous_view_from_comparison(comparison, catalogs)
    trajectory.trend = None
    trajectory.data = _latest_vs_previous_dict(comparison)
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    prompt_coach = build_prompt_coach_view_from_payload(current_prompt_coach_payload)
    return SnapshotComparisonPageView(
        title=catalogs.template_labels.get("snapshot_page_title", "Growth comparison"),
        subtitle=gt_i18n.get("page_subtitle", ""),
        left_snapshot_id=left_source.snapshot_id,
        right_snapshot_id=right_source.snapshot_id,
        left_created_at=left_source.created_at,
        right_created_at=right_source.created_at,
        left_date_range=left_source.date_range,
        right_date_range=right_source.date_range,
        left_headline=left_source.headline,
        right_headline=right_source.headline,
        trajectory=trajectory,
        report=SnapshotCompareReportView(prompt_coach=prompt_coach),
        data=trajectory.data,
    )


def _build_latest_vs_previous_view_from_comparison(
    comparison,
    catalogs: ReportLabelCatalogs,
) -> GrowthTrajectoryView:
    capability_meta = catalogs.view_model.get("capability_meta", {})
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    summary_i18n = gt_i18n.get("summary_cards", {})
    confidence_note = _confidence_note(comparison, gt_i18n)

    # Localize contract outcomes
    language = getattr(catalogs, "language", "zh")
    for outcome in getattr(comparison, "contract_outcomes", []) or []:
        axis_label = capability_meta.get(outcome.axis_key, {}).get("label", outcome.axis_key)
        outcome.axis_label = axis_label
        if outcome.status == "schema_mismatch":
            if language == "zh":
                outcome.explanation = "上期与本期评估维度不一致，维度发生变更，无法进行环比对比。"
            else:
                outcome.explanation = "Evaluation schemas do not match between cycles; cannot evaluate."
        elif outcome.status == "no_data":
            if language == "zh":
                outcome.explanation = f"本期未检测到目标轴【{axis_label}】的充足样本，改善效果暂无法评估。"
            else:
                outcome.explanation = f"Insufficient data for target axis [{axis_label}] to evaluate outcome."
        else:
            delta_val = outcome.delta or 0.0
            if outcome.status == "improved":
                if language == "zh":
                    outcome.explanation = f"目标轴【{axis_label}】得分提升 {delta_val:+.1f} 分，达到了设定目标，改善效果显著。"
                else:
                    outcome.explanation = f"Target axis [{axis_label}] score improved by {delta_val:+.1f} pts. Clear improvement."
            elif outcome.status == "partial":
                if language == "zh":
                    outcome.explanation = f"目标轴【{axis_label}】得分微幅提升 {delta_val:+.1f} 分，已见初步改善，建议继续巩固练习。"
                else:
                    outcome.explanation = f"Target axis [{axis_label}] score slightly improved by {delta_val:+.1f} pts. Initial progress made."
            else:
                if language == "zh":
                    outcome.explanation = f"目标轴【{axis_label}】得分无明显提升（{delta_val:+.1f} 分），需要针对瓶颈调整练习方法。"
                else:
                    outcome.explanation = f"Target axis [{axis_label}] score showed no significant change ({delta_val:+.1f} pts)."
    # axis_deltas is empty when the two snapshots use incomparable axis schemas;
    # fall back to a schema-honest placeholder instead of indexing [0].
    strongest_gain = (
        next((item for item in comparison.axis_deltas if item.delta > 0), None)
        or (comparison.axis_deltas[0] if comparison.axis_deltas else None)
    )
    weakest_axis = (
        min(comparison.axis_deltas, key=lambda item: item.current)
        if comparison.axis_deltas
        else None
    )
    _not_comparable = summary_i18n.get("not_comparable", "schema changed")
    summary_cards = [
        GrowthTrajectorySummaryCardView(
            label=summary_i18n.get("stage", "Current stage"),
            value=comparison.current.growth_level or "--",
            caption=_overall_text(comparison, gt_i18n, capability_meta),
            tone=comparison.overall_direction,
        ),
        GrowthTrajectorySummaryCardView(
            label=summary_i18n.get("score", "Score change"),
            value=_signed(comparison.score.delta, decimals=0),
            caption=f"{comparison.score.previous:.0f} -> {comparison.score.current:.0f}",
            tone=comparison.score.direction,
        ),
        GrowthTrajectorySummaryCardView(
            label=summary_i18n.get("strongest_gain", "Largest gain"),
            value=(
                capability_meta.get(strongest_gain.key, {}).get("label", strongest_gain.key)
                if strongest_gain is not None
                else _not_comparable
            ),
            caption=_signed(strongest_gain.delta) if strongest_gain is not None else "--",
            tone=strongest_gain.direction if strongest_gain is not None else "flat",
        ),
        GrowthTrajectorySummaryCardView(
            label=summary_i18n.get("primary_gap", "Primary gap"),
            value=(
                capability_meta.get(weakest_axis.key, {}).get("label", weakest_axis.key)
                if weakest_axis is not None
                else _not_comparable
            ),
            caption=_signed(weakest_axis.delta) if weakest_axis is not None else "--",
            tone=(
                (weakest_axis.direction if weakest_axis.direction != "flat" else "down")
                if weakest_axis is not None
                else "flat"
            ),
        ),
        GrowthTrajectorySummaryCardView(
            label=summary_i18n.get("confidence", "Confidence"),
            value=gt_i18n.get("confidence_levels", {}).get(comparison.confidence.level, comparison.confidence.level),
            caption=gt_i18n.get("sample_caption", "").format(sample_size=comparison.confidence.sample_size),
            tone=comparison.confidence.level,
        ),
    ]
    axis_deltas = [
        GrowthTrajectoryAxisView(
            key=item.key,
            label=capability_meta.get(item.key, {}).get("label", item.key),
            previous=item.previous,
            current=item.current,
            delta=item.delta,
            direction=item.direction,
            explanation=_axis_explanation(item.key, item.delta, item.current, capability_meta, gt_i18n),
        )
        for item in comparison.axis_deltas
    ]
    waterfall_steps = [
        GrowthTrajectoryWaterfallStepView(
            key=item.key,
            label=capability_meta.get(item.key, {}).get("label", item.key),
            delta=item.delta,
            contribution=item.weighted_contribution,
            direction=item.direction,
        )
        for item in comparison.waterfall
    ]
    return GrowthTrajectoryView(
        available=True,
        prev_label=gt_i18n.get("prev_label", "Prev {date}").format(date=comparison.previous.created_at[:10]),
        overview=_overall_text(comparison, gt_i18n, capability_meta),
        confidence_note=confidence_note,
        summary_cards=summary_cards,
        axis_deltas=axis_deltas,
        waterfall_steps=waterfall_steps,
        prompt_quality=_build_prompt_quality_view(comparison, catalogs),
        friction=_build_friction_view(comparison, catalogs),
        method_assets=_build_method_assets_view(comparison, gt_i18n),
        evidence_cards=_build_evidence_cards(comparison, catalogs),
        next_priorities=_build_priority_views(comparison, catalogs),
        human_cost_trend=_build_human_cost_trend_view(comparison),
    )


def _build_human_cost_trend_view(comparison: object) -> HumanCostTrendView:
    """Build view model for human_cost_reduction trend."""
    trend = getattr(comparison, "human_cost_trend", None)
    if trend is None or not trend.available:
        note = (
            getattr(trend, "note", "")
            if trend is not None
            else "historical snapshots do not yet contain human cost data"
        )
        return HumanCostTrendView(available=False, direction="unknown", note=note)

    prev_pct = f"{round((trend.previous_rate or 0.0) * 100, 1)}%"
    curr_pct = f"{round((trend.current_rate or 0.0) * 100, 1)}%"
    delta_pct = f"{round(abs(trend.delta) * 100, 1)}pp"
    return HumanCostTrendView(
        available=True,
        direction=trend.direction,
        note=trend.note,
        previous_rate_pct=prev_pct,
        current_rate_pct=curr_pct,
        delta_pct=delta_pct,
    )


def _build_trend_view(trajectory_window, catalogs: ReportLabelCatalogs) -> GrowthTrajectoryTrendView:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    trend_i18n = gt_i18n.get("trend", {})
    points = [
        GrowthTrajectoryPointView(
            snapshot_id=point.snapshot_id,
            generated_at=point.generated_at,
            date=point.date,
            mirror_score=point.mirror_score,
            growth_level=point.growth_level,
            sample_count=point.sample_count,
            confidence=point.confidence,
            axis_schema=getattr(point, "axis_schema", "current"),
            comparable=bool(getattr(point, "comparable", True)),
        )
        for point in trajectory_window.daily_points
    ]
    _comparable_axis_points = [
        point
        for point in trajectory_window.daily_points
        if bool(getattr(point, "comparable", True))
    ]
    summary_label = trend_i18n.get("labels", {}).get(trajectory_window.trend_summary.label, trajectory_window.trend_summary.label)
    summary_text = trend_i18n.get("explanations", {}).get(
        trajectory_window.trend_summary.explanation,
        trend_i18n.get("explanations", {}).get("insufficient_points", ""),
    ).format(point_count=len(points))
    confidence_note = trend_i18n.get("confidence", {}).get(
        trajectory_window.trend_summary.confidence,
        "",
    )
    return GrowthTrajectoryTrendView(
        available=len(points) >= 2,
        window_days=trajectory_window.window_days,
        window_label=trend_i18n.get("window_label", "近 {days} 天").format(days=trajectory_window.window_days),
        summary_code=trajectory_window.trend_summary.label,
        summary_label=summary_label,
        summary_text=summary_text,
        confidence_note=confidence_note,
        data_sufficiency=trajectory_window.trend_summary.data_sufficiency,
        empty_state=trend_i18n.get("empty_state", ""),
        points=points,
        score_series=_series_view(
            key="mirror_score",
            label=trend_i18n.get("score_label", "Mirror Score"),
            color="var(--accent)",
            values=[point.mirror_score for point in trajectory_window.daily_points],
            points=trajectory_window.daily_points,
            value_mode="score",
        ),
        axis_series=[
            _series_view(
                key=axis_key,
                label=catalogs.view_model.get("capability_meta", {}).get(axis_key, {}).get("label", axis_key),
                color=color,
                # Only comparable (current-schema) points carry the five axes;
                # legacy points would default to 0.0 and draw a fake crash to zero.
                values=[point.axes.get(axis_key, 0.0) for point in _comparable_axis_points],
                points=_comparable_axis_points,
                value_mode="axis",
            )
            for axis_key, color in (
                ("intent_clarity", "#ec4899"),
                ("execution_driving", "#2563eb"),
                ("implementation_depth", "#0ea5e9"),
                ("delivery_closure", "#f59e0b"),
                ("adaptive_recovery", "#14b8a6"),
            )
        ],
        prompt_quality_series=[
            _series_view(
                key=dim_key,
                label=catalogs.view_model.get("pq_dim_labels", {}).get(dim_key, dim_key),
                color=color,
                values=[point.prompt_quality.get(dim_key, 0.0) for point in trajectory_window.daily_points],
                points=trajectory_window.daily_points,
                value_mode="prompt_quality",
            )
            for dim_key, color in (
                ("context_provision", "#7c3aed"),
                ("request_specificity", "#2563eb"),
                ("scope_management", "#f97316"),
                ("information_timing", "#10b981"),
                ("correction_quality", "#ef4444"),
            )
        ],
        friction_series=[
            _series_view(
                key=friction_key,
                label=trend_i18n.get("friction_labels", {}).get(friction_key, friction_key),
                color=color,
                values=[point.friction.get(friction_key, 0) for point in trajectory_window.daily_points],
                points=trajectory_window.daily_points,
                value_mode="friction",
            )
            for friction_key, color in (
                ("vague_request", "#ef4444"),
                ("missing_context", "#f97316"),
                ("scope_drift", "#f59e0b"),
                ("missing_acceptance_criteria", "#14b8a6"),
                ("unclear_correction", "#6366f1"),
            )
        ],
    )


def _series_view(
    *,
    key: str,
    label: str,
    color: str,
    values: list[float],
    points: list,
    value_mode: str,
) -> GrowthTrajectorySeriesView:
    mini = value_mode == "axis"
    svg_points, y_ticks = _chart_points(
        values,
        chart_height=64.0 if mini else 112.0,
        chart_width=300.0,
    )
    plotted_points = [
        {
            "snapshot_id": point.snapshot_id,
            "date": point.date,
            "date_label": _short_date(point.date),
            "value": round(float(value), 1),
            "x": svg_points[index]["x"] if index < len(svg_points) else 0.0,
            "y": svg_points[index]["y"] if index < len(svg_points) else 0.0,
        }
        for index, (point, value) in enumerate(zip(points, values))
    ]
    polyline = " ".join(f"{item['x']},{item['y']}" for item in svg_points)
    area_path = ""
    if len(svg_points) >= 2:
        baseline_y = max((item["y"] for item in y_ticks), default=84.0)
        area_path = (
            f"M {svg_points[0]['x']} {baseline_y} "
            + " ".join(f"L {item['x']} {item['y']}" for item in svg_points)
            + f" L {svg_points[-1]['x']} {baseline_y} Z"
        )
    previous_value = float(values[-2]) if len(values) >= 2 else 0.0
    latest_value = float(values[-1]) if values else 0.0
    return GrowthTrajectorySeriesView(
        key=key,
        label=label,
        color=color,
        polyline=polyline,
        points=plotted_points,
        y_ticks=y_ticks,
        latest_delta=round(latest_value - previous_value, 1) if len(values) >= 2 else 0.0,
        latest_value=round(latest_value, 1),
        previous_value=round(previous_value, 1),
        latest_label=_latest_label(latest_value, value_mode),
        delta_label=_delta_label(round(latest_value - previous_value, 1) if len(values) >= 2 else 0.0, value_mode),
        trend_label=_trend_badge(values, value_mode),
        start_label=_short_date(points[0].date) if points else "",
        end_label=_short_date(points[-1].date) if points else "",
        insufficient_note="数据点不足" if len(values) < 3 else "",
        area_path=area_path,
    )


def _trajectory_window_to_dict(trajectory_window) -> dict[str, object]:
    return {
        "window_days": trajectory_window.window_days,
        "window_points": [asdict(point) for point in trajectory_window.window_points],
        "daily_points": [asdict(point) for point in trajectory_window.daily_points],
        "trend_summary": asdict(trajectory_window.trend_summary),
        "latest_vs_previous": asdict(trajectory_window.latest_vs_previous) if trajectory_window.latest_vs_previous else {},
    }


def _latest_vs_previous_dict(comparison) -> dict[str, object]:
    capability_meta = {
        item.key: item.key
        for item in comparison.axis_deltas
    }
    strongest_gain = next((item for item in comparison.axis_deltas if item.delta > 0), None)
    largest_regression = next(
        (item for item in sorted(comparison.axis_deltas, key=lambda row: row.delta) if item.delta < 0),
        None,
    )
    return {
        "current": {
            "snapshot_id": comparison.current.snapshot_id,
            "mirror_score": comparison.current.mirror_score,
            "growth_level": comparison.current.growth_level,
            "next_focus": comparison.current.next_focus,
        },
        "previous": {
            "snapshot_id": comparison.previous.snapshot_id,
            "mirror_score": comparison.previous.mirror_score,
            "growth_level": comparison.previous.growth_level,
            "next_focus": comparison.previous.next_focus,
        },
        "score_delta": comparison.score.delta,
        "level_delta": comparison.level_delta,
        "strongest_improvement": {
            "key": strongest_gain.key if strongest_gain else "",
            "label": capability_meta.get(strongest_gain.key, "") if strongest_gain else "",
            "delta": strongest_gain.delta if strongest_gain else 0.0,
            "direction": strongest_gain.direction if strongest_gain else "flat",
        },
        "largest_regression": {
            "key": largest_regression.key if largest_regression else "",
            "label": capability_meta.get(largest_regression.key, "") if largest_regression else "",
            "delta": largest_regression.delta if largest_regression else 0.0,
            "direction": largest_regression.direction if largest_regression else "flat",
        },
        "prompt_quality_delta": {
            "score_delta": comparison.prompt_quality.metric.delta,
            "direction": comparison.prompt_quality.metric.direction,
            "improved": list(comparison.prompt_quality.improved_deficits),
            "worsened": list(comparison.prompt_quality.worsened_deficits),
            "confidence": comparison.prompt_quality.confidence,
        },
        "friction_delta": {
            "total_delta": int(comparison.friction.total.delta),
            "reduced_types": list(comparison.friction.reduced_types),
            "increased_types": list(comparison.friction.increased_types),
            "recovery_signal": comparison.friction.recovery_signal,
        },
        "evidence_refs": [
            summary
            for card in comparison.evidence_cards
            for summary in card.summaries[:2]
        ][:6],
        "axis_deltas": [
            {
                "key": item.key,
                "previous": item.previous,
                "current": item.current,
                "delta": item.delta,
                "direction": item.direction,
            }
            for item in comparison.axis_deltas
        ],
        "contract_outcomes": [
            {
                "axis_key": item.axis_key,
                "axis_label": item.axis_label,
                "title": item.title,
                "previous_score": item.previous_score,
                "current_score": item.current_score,
                "delta": item.delta,
                "status": item.status,
                "confidence": item.confidence,
                "explanation": item.explanation,
            }
            for item in comparison.contract_outcomes
        ] if hasattr(comparison, "contract_outcomes") else [],
    }


def _snapshot_prompt_quality_source_note(pq: SnapshotPromptQuality, catalogs: ReportLabelCatalogs) -> str:
    pc_i18n = catalogs.view_model.get("prompt_coach", {})
    breakdown = pc_i18n.get("source_breakdown", {})
    total = pq.evaluated_sessions
    if total <= 0:
        return pc_i18n.get("trainer", {}).get("source_note_light", "")
    if pq.llm_sessions and pq.heuristic_sessions:
        template = breakdown.get("mixed", "")
    elif pq.llm_sessions:
        template = breakdown.get("llm_only", "")
    else:
        template = breakdown.get("heuristic_only", "")
    if not template:
        return ""
    return template.format(
        total=total,
        llm=pq.llm_sessions,
        heuristic=pq.heuristic_sessions,
        light=pq.light_sessions,
    )


def _build_prompt_quality_view(comparison, catalogs: ReportLabelCatalogs) -> GrowthTrajectoryPromptQualityView:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    pq_i18n = gt_i18n.get("prompt_quality", {})
    if not comparison.prompt_quality.available:
        return GrowthTrajectoryPromptQualityView(
            available=False,
            headline=pq_i18n.get("headline", ""),
            summary=pq_i18n.get("insufficient", ""),
            source_note="",
            confidence_note="",
        )
    prev_note = _snapshot_prompt_quality_source_note(comparison.previous.prompt_quality, catalogs)
    curr_note = _snapshot_prompt_quality_source_note(comparison.current.prompt_quality, catalogs)
    compare_template = pq_i18n.get(
        "source_note_compare",
        "{prev_label}：{previous} {curr_label}：{current}",
    )
    source_note = compare_template.format(
        previous=prev_note,
        current=curr_note,
        prev_label=catalogs.template_labels.get("label_previous", "Previous"),
        curr_label=catalogs.template_labels.get("label_current", "Current"),
    )
    summary_key = {
        "up": "improved",
        "down": "regressed",
        "flat": "stable",
    }.get(comparison.prompt_quality.metric.direction, "stable")
    confidence_note = pq_i18n.get(f"confidence_{comparison.prompt_quality.confidence}", "")
    return GrowthTrajectoryPromptQualityView(
        available=True,
        headline=pq_i18n.get("headline", ""),
        summary=pq_i18n.get(summary_key, "").format(delta=_signed(comparison.prompt_quality.metric.delta)),
        source_note=source_note,
        confidence_note=confidence_note,
        improved=[_prompt_deficit_label(key, catalogs) for key in comparison.prompt_quality.improved_deficits],
        worsened=[_prompt_deficit_label(key, catalogs) for key in comparison.prompt_quality.worsened_deficits],
    )


def _build_friction_view(comparison, catalogs: ReportLabelCatalogs) -> GrowthTrajectoryFrictionView:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    friction_i18n = gt_i18n.get("friction", {})
    friction_labels = gt_i18n.get("trend", {}).get("friction_labels", {}) | catalogs.view_model.get("friction_labels", {})
    summary_key = {
        "up": "more",
        "down": "less",
        "flat": "flat",
    }.get(comparison.friction.total.direction, "flat")
    changes = [
        GrowthTrajectoryFrictionTypeView(
            label=friction_labels.get(item.key, item.key),
            previous=item.previous_count,
            current=item.current_count,
            delta=item.delta,
            direction=item.direction,
        )
        for item in comparison.friction.type_deltas
    ]
    return GrowthTrajectoryFrictionView(
        summary=friction_i18n.get(summary_key, "").format(delta=_signed(comparison.friction.total.delta, decimals=0)),
        recovery_note=friction_i18n.get(f"recovery_{comparison.friction.recovery_signal}", ""),
        reduced_types=[friction_labels.get(key, key) for key in comparison.friction.reduced_types[:3]],
        increased_types=[friction_labels.get(key, key) for key in comparison.friction.increased_types[:3]],
        changes=changes,
    )


def _build_method_assets_view(comparison, gt_i18n: dict) -> GrowthTrajectoryMethodAssetsView:
    asset_i18n = gt_i18n.get("method_assets", {})
    summary_key = "stronger" if comparison.method_assets.stronger_reuse else "weaker"
    return GrowthTrajectoryMethodAssetsView(
        summary=asset_i18n.get(summary_key, ""),
        detail=asset_i18n.get("detail", "").format(
            asset_delta=_signed(comparison.method_assets.total_assets.delta, decimals=0),
            workflow_delta=_signed(comparison.method_assets.workflow_assets.delta, decimals=0),
            assetization_delta=_signed(comparison.method_assets.assetization_rate.delta),
        ),
        metrics=[
            GrowthTrajectoryMethodMetricView(
                label=asset_i18n.get("metric_total_assets", "Asset files"),
                previous=f"{comparison.method_assets.total_assets.previous:.0f}",
                current=f"{comparison.method_assets.total_assets.current:.0f}",
                delta=_signed(comparison.method_assets.total_assets.delta, decimals=0),
            ),
            GrowthTrajectoryMethodMetricView(
                label=asset_i18n.get("metric_workflow_assets", "Reusable workflows"),
                previous=f"{comparison.method_assets.workflow_assets.previous:.0f}",
                current=f"{comparison.method_assets.workflow_assets.current:.0f}",
                delta=_signed(comparison.method_assets.workflow_assets.delta, decimals=0),
            ),
            GrowthTrajectoryMethodMetricView(
                label=asset_i18n.get("metric_assetization_rate", "Assetized session rate"),
                previous=f"{comparison.method_assets.assetization_rate.previous:.1f}%",
                current=f"{comparison.method_assets.assetization_rate.current:.1f}%",
                delta=_signed(comparison.method_assets.assetization_rate.delta),
            ),
        ],
    )


def _build_evidence_cards(comparison, catalogs: ReportLabelCatalogs) -> list[GrowthTrajectoryEvidenceCardView]:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    evidence_i18n = gt_i18n.get("evidence_cards", {})
    capability_meta = catalogs.view_model.get("capability_meta", {})
    cards: list[GrowthTrajectoryEvidenceCardView] = []
    for card in comparison.evidence_cards:
        axis_label = capability_meta.get(card.axis_key, {}).get("label", card.axis_key)
        body = evidence_i18n.get(card.topic, {}).get(card.direction, evidence_i18n.get(card.topic, {}).get("flat", ""))
        cards.append(
            GrowthTrajectoryEvidenceCardView(
                title=evidence_i18n.get(card.topic, {}).get("title", card.topic).format(axis_label=axis_label),
                body=body.format(axis_label=axis_label),
                evidence=card.summaries,
            )
        )
    return cards


def _build_priority_views(comparison, catalogs: ReportLabelCatalogs) -> list[GrowthTrajectoryPriorityView]:
    gt_i18n = catalogs.view_model.get("growth_trajectory", {})
    priority_i18n = gt_i18n.get("priorities", {})
    capability_meta = catalogs.view_model.get("capability_meta", {})
    views: list[GrowthTrajectoryPriorityView] = []
    for item in comparison.next_priorities:
        label = capability_meta.get(item.axis_key, {}).get("label", item.axis_key)
        title = priority_i18n.get(item.priority, "").format(label=label)
        reasons = [priority_i18n.get("reason_codes", {}).get(code, code).format(label=label) for code in item.reason_codes]
        views.append(
            GrowthTrajectoryPriorityView(
                title=title,
                body=priority_i18n.get("body", "").format(label=label),
                reasons=reasons,
                evidence=item.evidence_summaries,
            )
        )
    return views


def _build_runtime_evidence(
    *,
    session_reads: list[SessionRead],
    prompt_coach: "PromptCoachView",
    growth_plan: "GrowthPlanView",
    exemplars: list["PersonalExemplarView"],
    summary: "PersonalSummaryView",
) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {"overall": [summary.headline], "friction": [], "prompt_quality": [], "method_assets": []}
    for session_read in session_reads[:12]:
        takeaway = (session_read.session_takeaway or "").strip()
        if takeaway:
            _push(rows, "overall", takeaway)
        resistance_summary = (session_read.resistance_summary or "").strip()
        if resistance_summary:
            _push(rows, "friction", resistance_summary)
        for signal in session_read.resistance_signals[:4]:
            if signal.description:
                _push(rows, "friction", signal.description)
                topic = _topic_from_friction(signal.category)
                if topic:
                    _push(rows, topic, signal.description)
        for signal in session_read.momentum_signals[:3]:
            if signal.description:
                _push(rows, "overall", signal.description)
    if prompt_coach.evidence_summary:
        _push(rows, "prompt_quality", prompt_coach.evidence_summary)
    for deficit in prompt_coach.top_deficits[:3]:
        for evidence in deficit.evidence_refs[:2]:
            _push(rows, "prompt_quality", evidence)
    for card in prompt_coach.rewrite_cards[:2]:
        if card.why:
            _push(rows, "prompt_quality", card.why)
    if growth_plan.priorities:
        _push(rows, "overall", growth_plan.priorities[0].why)
    for exemplar in exemplars[:3]:
        if exemplar.summary:
            _push(rows, "method_assets", exemplar.summary)
        if exemplar.technique:
            _push(rows, "method_assets", exemplar.technique)
    return rows


def _build_actionable_friction_counts(stats: GrowthProfile) -> dict[str, int]:
    pq_deficits = stats.pq_deficit_counts or {}
    friction_counts = stats.friction_type_counts or {}
    return {
        "vague_request": int(pq_deficits.get("vague-request", 0) or 0) + int(friction_counts.get("fuzzy-intent", 0) or 0),
        "missing_context": int(pq_deficits.get("missing-context", 0) or 0) + int(friction_counts.get("missing-context", 0) or 0) + int(friction_counts.get("context-gap", 0) or 0),
        "scope_drift": int(pq_deficits.get("scope-drift", 0) or 0) + int(friction_counts.get("scope-creep", 0) or 0) + int(friction_counts.get("goal-drift", 0) or 0),
        "missing_acceptance_criteria": int(pq_deficits.get("missing-acceptance-criteria", 0) or 0) + int(friction_counts.get("missing-acceptance-criteria", 0) or 0) + int(friction_counts.get("incomplete-output", 0) or 0),
        "unclear_correction": int(pq_deficits.get("unclear-correction", 0) or 0) + int(friction_counts.get("off-track", 0) or 0) + int(friction_counts.get("outdated-context", 0) or 0),
    }


def _topic_from_friction(category: str) -> str:
    return {
        "ambiguous-request": "intent_clarity",
        "context-confusion": "intent_clarity",
        "context-gap": "intent_clarity",
        "fuzzy-intent": "intent_clarity",
        "goal-drift": "adaptive_recovery",
        "incomplete-output": "delivery_closure",
        "missing-acceptance-criteria": "delivery_closure",
        "missing-context": "intent_clarity",
        "off-track": "adaptive_recovery",
        "outdated-context": "adaptive_recovery",
        "recurring-pattern": "adaptive_recovery",
        "reference-gap": "implementation_depth",
        "repetition": "execution_driving",
        "scope-creep": "execution_driving",
        "tool-ceiling": "implementation_depth",
    }.get(category, "")


def _push(rows: dict[str, list[str]], key: str, value: str) -> None:
    text = (value or "").strip()
    if not text:
        return
    bucket = rows.setdefault(key, [])
    if text not in bucket:
        bucket.append(text)


def _overall_text(comparison, gt_i18n: dict, capability_meta: dict) -> str:
    overall_i18n = gt_i18n.get("overall", {})
    # axis_deltas can be empty when axis schemas are incomparable.
    strongest_gain = (
        next((item for item in comparison.axis_deltas if item.delta > 0), None)
        or (comparison.axis_deltas[0] if comparison.axis_deltas else None)
    )
    label = (
        capability_meta.get(strongest_gain.key, {}).get("label", strongest_gain.key)
        if strongest_gain is not None
        else "--"
    )
    return overall_i18n.get(comparison.overall_code, overall_i18n.get("stable", "")).format(
        previous=comparison.previous.growth_level or "--",
        current=comparison.current.growth_level or "--",
        delta=_signed(comparison.score.delta, decimals=0),
        axis_label=label,
    )


def _confidence_note(comparison, gt_i18n: dict) -> str:
    confidence_i18n = gt_i18n.get("confidence", {})
    reason_text = [
        confidence_i18n.get("reasons", {}).get(reason, reason)
        for reason in comparison.confidence.reasons
    ]
    base = confidence_i18n.get(comparison.confidence.level, "")
    if reason_text:
        return f"{base} {'; '.join(reason_text[:3])}"
    return base


def _axis_explanation(axis_key: str, delta: float, current: float, capability_meta: dict, gt_i18n: dict) -> str:
    axis_i18n = gt_i18n.get("axis", {})
    meta = capability_meta.get(axis_key, {})
    if delta > 0:
        template = axis_i18n.get("up", "")
    elif delta < 0:
        template = axis_i18n.get("down", "")
    else:
        template = axis_i18n.get("flat", "")
    return template.format(
        label=meta.get("label", axis_key),
        delta=_signed(delta),
        current=f"{current:.1f}",
        explanation=meta.get("explanation", ""),
        next_action=meta.get("next_action", ""),
    )


def _prompt_deficit_label(key: str, catalogs: ReportLabelCatalogs) -> str:
    labels = catalogs.guidance_labels.get("pq_labels", {}).get("deficit", {})
    return labels.get(key.replace("-", "_"), key)


def _chart_points(
    values: list[float],
    *,
    chart_width: float = 300.0,
    chart_height: float = 112.0,
) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    if not values:
        return [], []
    width = chart_width
    height = chart_height
    padding = 12.0
    max_value = max(values)
    min_value = min(values)
    span = max(max_value - min_value, 1.0)
    padded_min = min_value - max(span * 0.15, 2.0)
    padded_max = max_value + max(span * 0.15, 2.0)
    padded_span = max(padded_max - padded_min, 1.0)
    coords: list[dict[str, float]] = []
    for index, value in enumerate(values):
        x = padding if len(values) == 1 else padding + (width - padding * 2) * index / (len(values) - 1)
        y = height - padding - ((float(value) - padded_min) / padded_span) * (height - padding * 2)
        coords.append({"x": round(x, 1), "y": round(y, 1)})
    y_ticks = [
        {"value": round(padded_max, 1), "y": round(padding, 1)},
        {"value": round((padded_max + padded_min) / 2, 1), "y": round(height / 2, 1)},
        {"value": round(padded_min, 1), "y": round(height - padding, 1)},
    ]
    return coords, y_ticks


def _latest_label(value: float, value_mode: str) -> str:
    if value_mode == "friction":
        return _friction_band(value)
    if value_mode == "score":
        return f"{value:.0f}"
    return f"{value:.1f}"


def _delta_label(delta: float, value_mode: str) -> str:
    if value_mode == "friction":
        if delta >= 1:
            return "较上期增加"
        if delta <= -1:
            return "较上期减少"
        return "较上期持平"
    return _signed(delta)


def _trend_badge(values: list[float], value_mode: str) -> str:
    if len(values) < 3:
        return "数据不足"
    delta = values[-1] - values[0]
    recent = values[-1] - values[-2]
    if value_mode == "friction":
        if recent <= -1 and delta <= -1:
            return "下降"
        if recent >= 1 and delta >= 1:
            return "上升"
        return "波动"
    if recent <= -3 and delta > 0:
        return "回撤"
    if delta >= 4:
        return "上升"
    if delta <= -4:
        return "回撤"
    return "持平"


def _friction_band(value: float) -> str:
    if value >= 6:
        return "高频"
    if value >= 3:
        return "中频"
    if value > 0:
        return "低频"
    return "很少"


def _short_date(value: str) -> str:
    return value[5:] if len(value) >= 10 else value


def _signed(value: float, *, decimals: int = 1) -> str:
    fmt = f"{{value:+.{decimals}f}}"
    return fmt.format(value=value)


def _has_usage_data(stats: GrowthProfile) -> bool:
    return any(
        value
        for value in (
            stats.total_input_tokens,
            stats.total_output_tokens,
            stats.total_cache_read_tokens,
            stats.total_cache_write_tokens,
            stats.total_cost_usd,
        )
    )
