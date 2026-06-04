"""Pure 30-day snapshot trajectory rules."""

from __future__ import annotations

from datetime import datetime, timedelta

from .comparison import compare_snapshot_sources
from .model import (
    FrictionChangeSummary,
    LatestChangeHighlight,
    LatestVsPreviousSummary,
    PromptQualityChangeSummary,
    SnapshotSource,
    SnapshotTrajectoryWindow,
    TrajectoryPoint,
    TrajectorySummary,
    has_legacy_axis_schema,
    is_current_axis_schema,
)

ACTIONABLE_FRICTION_ORDER = (
    "vague_request",
    "missing_context",
    "scope_drift",
    "missing_acceptance_criteria",
    "unclear_correction",
)


def build_snapshot_trajectory_window(
    sources: list[SnapshotSource],
    *,
    window_days: int = 30,
) -> SnapshotTrajectoryWindow:
    ordered_sources = sorted(
        (source for source in sources if _parse_created_at(source.created_at) is not None),
        key=lambda item: _parse_created_at(item.created_at) or datetime.min,
    )
    if not ordered_sources:
        return SnapshotTrajectoryWindow(window_days=window_days)

    latest_dt = _parse_created_at(ordered_sources[-1].created_at) or datetime.min
    cutoff = latest_dt - timedelta(days=window_days)
    in_window = [
        source
        for source in ordered_sources
        if (_parse_created_at(source.created_at) or datetime.min) >= cutoff
    ]
    points = [_build_point(source) for source in in_window]
    daily_points = _collapse_same_day(points)
    trend_summary = _build_trend_summary(daily_points)
    latest_vs_previous = None
    if len(daily_points) >= 2:
        previous_id = daily_points[-2].snapshot_id
        current_id = daily_points[-1].snapshot_id
        source_by_id = {source.snapshot_id: source for source in in_window}
        previous_source = source_by_id.get(previous_id)
        current_source = source_by_id.get(current_id)
        if previous_source is not None and current_source is not None:
            latest_vs_previous = _build_latest_vs_previous(previous_source, current_source)

    from .comparison import _build_human_cost_trend

    human_cost_trend = None
    if len(ordered_sources) >= 2:
        human_cost_trend = _build_human_cost_trend(ordered_sources[-2], ordered_sources[-1])

    return SnapshotTrajectoryWindow(
        window_days=window_days,
        window_points=points,
        daily_points=daily_points,
        trend_summary=trend_summary,
        latest_vs_previous=latest_vs_previous,
        human_cost_trend=human_cost_trend,
    )


def assess_snapshot_point_confidence(source: SnapshotSource) -> str:
    sample = source.sample_count or source.coverage.session_read_count or source.coverage.session_count
    score = 100
    if not is_current_axis_schema(source.axis_scores):
        score -= 35
    if has_legacy_axis_schema(source.axis_scores):
        score -= 20
    if sample < 3:
        score -= 35
    elif sample < 8:
        score -= 20
    if source.coverage.extraction_failed:
        score -= 20
    if not source.coverage.has_usage_data:
        score -= 10
    if source.prompt_quality.llm_sessions <= 0 and source.prompt_quality.evaluated_sessions > 0:
        score -= 15
    if source.prompt_quality.evaluated_sessions <= 0:
        score -= 20
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _build_point(source: SnapshotSource) -> TrajectoryPoint:
    created_at = source.created_at
    date = created_at[:10] if created_at else ""
    sample_count = source.sample_count or source.coverage.session_read_count or source.coverage.session_count
    confidence = source.point_confidence or assess_snapshot_point_confidence(source)
    comparable = is_current_axis_schema(source.axis_scores)
    if comparable:
        axis_schema = "current"
    elif has_legacy_axis_schema(source.axis_scores):
        axis_schema = "legacy"
    else:
        axis_schema = "unknown"
    return TrajectoryPoint(
        snapshot_id=source.snapshot_id,
        generated_at=created_at,
        date=date,
        mirror_score=source.mirror_score,
        growth_level=source.growth_level,
        sample_count=sample_count,
        confidence=confidence,
        axes=dict(source.axis_scores),
        prompt_quality=dict(source.prompt_quality_dimensions),
        friction={key: int(source.actionable_friction_counts.get(key, 0)) for key in ACTIONABLE_FRICTION_ORDER},
        axis_schema=axis_schema,
        comparable=comparable,
    )


def _collapse_same_day(points: list[TrajectoryPoint]) -> list[TrajectoryPoint]:
    by_date: dict[str, TrajectoryPoint] = {}
    for point in points:
        by_date[point.date] = point
    return [by_date[date] for date in sorted(by_date)]


def _build_trend_summary(points: list[TrajectoryPoint]) -> TrajectorySummary:
    if len(points) < 3:
        return TrajectorySummary(
            label="data_insufficient",
            explanation="insufficient_points",
            confidence="low",
            data_sufficiency=f"points={len(points)}",
            recent_signal="insufficient",
        )
    comparable_points = [point for point in points if point.comparable]
    if len(comparable_points) < len(points):
        return TrajectorySummary(
            label="data_insufficient",
            explanation="schema_mismatch",
            confidence="low",
            data_sufficiency=f"points={len(points)} comparable={len(comparable_points)}",
            recent_signal="schema_mismatch",
        )

    scores = [point.mirror_score for point in points]
    delta = scores[-1] - scores[0]
    deltas = [curr - prev for prev, curr in zip(scores, scores[1:])]
    negatives = sum(1 for value in deltas if value < 0)
    positives = sum(1 for value in deltas if value > 0)
    score_range = max(scores) - min(scores)
    recent_delta = deltas[-1] if deltas else 0
    recent_high_gap = (max(scores[:-1]) - scores[-1]) if len(scores) >= 2 else 0
    confidence = _series_confidence(points)

    if abs(delta) <= 4 and score_range <= 6:
        label = "stable"
        explanation = "stable_band"
        recent_signal = "flat"
    elif delta >= 6 and recent_delta <= -4 and recent_high_gap >= 4:
        label = "overall_up_recent_pullback"
        explanation = "overall_up_recent_pullback"
        recent_signal = "recent_pullback"
    elif delta >= 6 and negatives == 0:
        label = "sustained_up"
        explanation = "steady_improvement"
        recent_signal = "up"
    elif delta >= 6:
        label = "volatile_up"
        explanation = "improving_with_swings"
        recent_signal = "up"
    elif recent_delta <= -4 and score_range >= 8:
        label = "phased_pullback"
        explanation = "phased_pullback"
        recent_signal = "recent_pullback"
    elif delta <= -6:
        label = "volatile_down"
        explanation = "declining_with_swings" if positives else "steady_decline"
        recent_signal = "down"
    else:
        label = "stable"
        explanation = "mixed_but_flat"
        recent_signal = "flat"
    return TrajectorySummary(
        label=label,
        explanation=explanation,
        confidence=confidence,
        data_sufficiency=f"points={len(points)}",
        recent_signal=recent_signal,
    )


def _series_confidence(points: list[TrajectoryPoint]) -> str:
    if any(not point.comparable for point in points):
        return "low"
    high = sum(1 for point in points if point.confidence == "high")
    medium = sum(1 for point in points if point.confidence == "medium")
    if high >= 3:
        return "high"
    if high + medium >= 3:
        return "medium"
    return "low"


def _build_latest_vs_previous(previous: SnapshotSource, current: SnapshotSource) -> LatestVsPreviousSummary:
    comparison = compare_snapshot_sources(previous, current)
    strongest = next((item for item in comparison.axis_deltas if item.delta > 0), None)
    regression = next(
        (item for item in sorted(comparison.axis_deltas, key=lambda row: row.delta) if item.delta < 0),
        None,
    )
    pq_dim_deltas = {
        key: round(current.prompt_quality_dimensions.get(key, 0.0) - previous.prompt_quality_dimensions.get(key, 0.0), 1)
        for key in set(previous.prompt_quality_dimensions) | set(current.prompt_quality_dimensions)
    }
    improved_dims = [key for key, value in pq_dim_deltas.items() if value > 0]
    worsened_dims = [key for key, value in pq_dim_deltas.items() if value < 0]
    friction_total_delta = sum(current.actionable_friction_counts.values()) - sum(previous.actionable_friction_counts.values())
    reduced = [
        key
        for key in ACTIONABLE_FRICTION_ORDER
        if current.actionable_friction_counts.get(key, 0) < previous.actionable_friction_counts.get(key, 0)
    ]
    increased = [
        key
        for key in ACTIONABLE_FRICTION_ORDER
        if current.actionable_friction_counts.get(key, 0) > previous.actionable_friction_counts.get(key, 0)
    ]
    evidence_refs = []
    for topic in ("overall", "prompt_quality", strongest.key if strongest else "", regression.key if regression else "", "friction"):
        for item in current.evidence_by_topic.get(topic, [])[:2]:
            if item and item not in evidence_refs:
                evidence_refs.append(item)
    return LatestVsPreviousSummary(
        score_delta=comparison.score.delta,
        level_delta=comparison.level_delta,
        strongest_improvement=LatestChangeHighlight(
            key=strongest.key if strongest else "",
            label=strongest.key if strongest else "",
            delta=strongest.delta if strongest else 0.0,
            direction=strongest.direction if strongest else "flat",
        ),
        largest_regression=LatestChangeHighlight(
            key=regression.key if regression else "",
            label=regression.key if regression else "",
            delta=regression.delta if regression else 0.0,
            direction=regression.direction if regression else "flat",
        ),
        prompt_quality_delta=PromptQualityChangeSummary(
            score_delta=comparison.prompt_quality.metric.delta,
            direction=comparison.prompt_quality.metric.direction,
            improved_dimensions=sorted(improved_dims),
            worsened_dimensions=sorted(worsened_dims),
            source_note=_prompt_source_code(current),
            confidence=comparison.prompt_quality.confidence,
        ),
        friction_delta=FrictionChangeSummary(
            total_delta=friction_total_delta,
            reduced_types=reduced,
            increased_types=increased,
            recovery_signal=comparison.friction.recovery_signal,
        ),
        evidence_refs=evidence_refs[:6],
    )


def _prompt_source_code(source: SnapshotSource) -> str:
    if source.prompt_quality.llm_sessions and source.prompt_quality.heuristic_sessions:
        return "mixed"
    if source.prompt_quality.llm_sessions:
        return "llm"
    if source.prompt_quality.evaluated_sessions:
        return "heuristic"
    return "light"


def _parse_created_at(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
