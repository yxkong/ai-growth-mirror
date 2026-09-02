"""Pure snapshot comparison logic."""

from __future__ import annotations

from dataclasses import asdict

from ..growth.assessment_policy import AXIS_WEIGHTS

from .model import (
    AxisDelta,
    ConfidenceAssessment,
    EvidenceCard,
    FrictionDelta,
    FrictionTypeDelta,
    HumanCostTrend,
    MethodAssetDelta,
    NumericDelta,
    PromptQualityDelta,
    SnapshotComparison,
    SnapshotSource,
    TrainingPriority,
    TrendSummary,
    has_legacy_axis_schema,
    is_current_axis_schema,
)

AXIS_ORDER = tuple(AXIS_WEIGHTS)

LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

PQ_AXIS_MAP = {
    "context_provision": "collaboration_framing",
    "request_specificity": "collaboration_framing",
    "scope_management": "collaboration_framing",
    "information_timing": "execution_driving",
    "correction_quality": "adaptive_recovery",
}

FRICTION_AXIS_MAP = {
    "ambiguous-request": "collaboration_framing",
    "context-confusion": "collaboration_framing",
    "context-gap": "collaboration_framing",
    "fuzzy-intent": "collaboration_framing",
    "goal-drift": "adaptive_recovery",
    "incomplete-output": "delivery_closure",
    "missing-acceptance-criteria": "delivery_closure",
    "missing-context": "collaboration_framing",
    "off-track": "adaptive_recovery",
    "outdated-context": "adaptive_recovery",
    "recurring-pattern": "adaptive_recovery",
    "reference-gap": "implementation_depth",
    "repetition": "execution_driving",
    "scope-creep": "execution_driving",
    "tool-ceiling": "implementation_depth",
}


def _normalize_axes(scores: dict[str, float]) -> dict[str, float]:
    normalized = dict(scores)
    if "intent_clarity" in normalized and "collaboration_framing" not in normalized:
        normalized["collaboration_framing"] = normalized.pop("intent_clarity")
    return normalized


def compare_snapshot_sources(
    previous: SnapshotSource,
    current: SnapshotSource,
) -> SnapshotComparison:
    import dataclasses
    previous = dataclasses.replace(previous, axis_scores=_normalize_axes(previous.axis_scores))
    current = dataclasses.replace(current, axis_scores=_normalize_axes(current.axis_scores))
    if (
        not previous.assessment_policy_version
        or not current.assessment_policy_version
        or previous.assessment_policy_version != current.assessment_policy_version
    ):
        return SnapshotComparison(
            previous=previous,
            current=current,
            confidence=ConfidenceAssessment(
                level="low",
                score=0,
                reasons=["assessment_policy_mismatch"],
            ),
            trend_summary=TrendSummary(direction="flat", confidence="low", score_delta=0.0),
            policy_comparable=False,
            incomparable_reason="assessment_policy_mismatch",
        )
    score = _numeric_delta(previous.mirror_score, current.mirror_score, decimals=0)
    level_delta = LEVEL_ORDER.get(current.growth_level, 0) - LEVEL_ORDER.get(previous.growth_level, 0)
    axis_deltas = _build_axis_deltas(previous, current)
    prompt_quality = _build_prompt_quality_delta(previous, current)
    friction = _build_friction_delta(previous, current, axis_deltas)
    method_assets = _build_method_asset_delta(previous, current)
    confidence = _build_confidence(previous, current, prompt_quality)
    
    # Compute TrendSummary
    score_delta = current.mirror_score - previous.mirror_score
    if score_delta >= 4:
        trend_direction = "improving"
    elif score_delta <= -4:
        trend_direction = "declining"
    else:
        trend_direction = "flat"

    if previous.coverage.session_count < 8 or current.coverage.session_count < 8:
        trend_confidence = "low"
        confidence.level = "low"
    else:
        trend_confidence = confidence.level

    trend_summary = TrendSummary(
        direction=trend_direction,
        confidence=trend_confidence,
        score_delta=float(score_delta),
    )

    # Evaluate Action Contracts
    contract_outcomes = _evaluate_action_contracts(previous, current, confidence.level)

    evidence_cards = _build_evidence_cards(previous, current, axis_deltas, friction, method_assets)
    next_priorities = _build_priorities(current, axis_deltas, friction, prompt_quality, method_assets)
    human_cost_trend = _build_human_cost_trend(previous, current)
    return SnapshotComparison(
        previous=previous,
        current=current,
        score=score,
        level_delta=level_delta,
        overall_direction=_overall_direction(score.delta, level_delta),
        overall_code=_overall_code(score.delta, level_delta),
        axis_deltas=axis_deltas,
        waterfall=sorted(axis_deltas, key=lambda item: abs(item.weighted_contribution), reverse=True),
        prompt_quality=prompt_quality,
        friction=friction,
        method_assets=method_assets,
        evidence_cards=evidence_cards,
        confidence=confidence,
        next_priorities=next_priorities,
        human_cost_trend=human_cost_trend,
        trend_summary=trend_summary,
        contract_outcomes=contract_outcomes,
    )


def snapshot_comparison_to_dict(comparison: SnapshotComparison) -> dict[str, object]:
    return asdict(comparison)


def _build_human_cost_trend(
    previous: SnapshotSource,
    current: SnapshotSource,
) -> HumanCostTrend:
    """Compute the human_cost_reduction trend between two snapshots."""
    prev_rate = previous.human_intervention_session_rate
    curr_rate = current.human_intervention_session_rate

    if prev_rate is None or curr_rate is None:
        return HumanCostTrend(
            available=False,
            previous_rate=prev_rate,
            current_rate=curr_rate,
            note="historical snapshots do not yet contain human_intervention_session_rate; "
                 "trend available after next report generation",
        )

    delta = round(curr_rate - prev_rate, 4)
    if abs(delta) < 0.02:
        direction = "flat"
    elif delta < 0:
        direction = "improving"  # rate decreased = fewer human corrections
    else:
        direction = "worsening"

    pct_prev = round(prev_rate * 100, 1)
    pct_curr = round(curr_rate * 100, 1)
    pct_delta = round(abs(delta) * 100, 1)
    if direction == "improving":
        note = f"human correction rate reduced from {pct_prev}% → {pct_curr}% (−{pct_delta}pp)"
    elif direction == "worsening":
        note = f"human correction rate increased from {pct_prev}% → {pct_curr}% (+{pct_delta}pp)"
    else:
        note = f"human correction rate stable at ~{pct_curr}%"

    return HumanCostTrend(
        available=True,
        previous_rate=prev_rate,
        current_rate=curr_rate,
        delta=delta,
        direction=direction,
        note=note,
    )


def _axis_direction(delta: float) -> str:
    if delta > 0:
        return "improving"
    if delta < 0:
        return "declining"
    return "flat"


def _evaluate_action_contracts(
    previous: SnapshotSource,
    current: SnapshotSource,
    confidence_level: str,
) -> list[ContractOutcome]:
    outcomes = []
    prev_contracts = getattr(previous, "action_contracts", []) or []

    if previous.coverage.session_count < 8 or current.coverage.session_count < 8:
        contract_confidence = "low"
    else:
        contract_confidence = confidence_level

    for contract in prev_contracts:
        axis_key = contract.get("axis_key", "")
        if not axis_key:
            continue
        if axis_key == "intent_clarity":
            axis_key = "collaboration_framing"

        title = contract.get("title", "")
        has_schema = is_current_axis_schema(previous.axis_scores) and is_current_axis_schema(current.axis_scores)

        if not has_schema:
            status = "schema_mismatch"
            prev_score = None
            curr_score = None
            delta = None
        else:
            prev_score = previous.axis_scores.get(axis_key)
            curr_score = current.axis_scores.get(axis_key)

            if prev_score is None or curr_score is None:
                status = "no_data"
                delta = None
            else:
                prev_score = float(prev_score)
                curr_score = float(curr_score)
                delta = round(curr_score - prev_score, 1)

                if delta >= 5.0:
                    status = "improved"
                elif delta > 0.2:
                    status = "partial"
                else:
                    status = "unchanged"

        from .model import ContractOutcome
        outcomes.append(
            ContractOutcome(
                axis_key=axis_key,
                axis_label="",
                title=title,
                previous_score=prev_score,
                current_score=curr_score,
                delta=delta,
                status=status,
                confidence=contract_confidence,
                explanation="",
            )
        )
    return outcomes


def _build_axis_deltas(previous: SnapshotSource, current: SnapshotSource) -> list[AxisDelta]:
    rows: list[AxisDelta] = []
    # When either snapshot does not carry the current six-axis schema, the
    # missing axes would default to 0.0 and fabricate "0 -> 60" gains/regressions
    # that pollute the waterfall, evidence cards and training priorities. The
    # confidence layer already flags the mismatch; here we simply emit no axis
    # deltas so the comparison stays schema-honest.
    if not is_current_axis_schema(previous.axis_scores) or not is_current_axis_schema(current.axis_scores):
        return rows
    for key in AXIS_ORDER:
        if key not in previous.axis_scores or key not in current.axis_scores:
            continue
        prev_value = float(previous.axis_scores[key])
        curr_value = float(current.axis_scores[key])
        delta = round(curr_value - prev_value, 1)
        rows.append(
            AxisDelta(
                key=key,
                previous=prev_value,
                current=curr_value,
                delta=delta,
                direction=_axis_direction(delta),
                weight=AXIS_WEIGHTS.get(key, 0.0),
                weighted_contribution=round(delta * AXIS_WEIGHTS.get(key, 0.0), 1),
                magnitude=_magnitude(delta),
            )
        )
    rows.sort(key=lambda item: abs(item.delta), reverse=True)
    return rows


def _build_prompt_quality_delta(previous: SnapshotSource, current: SnapshotSource) -> PromptQualityDelta:
    prev_pq = previous.prompt_quality
    curr_pq = current.prompt_quality
    available = prev_pq.evaluated_sessions > 0 or curr_pq.evaluated_sessions > 0
    prev_score = float(prev_pq.efficiency_score or 0.0)
    curr_score = float(curr_pq.efficiency_score or 0.0)
    improved_deficits: list[str] = []
    worsened_deficits: list[str] = []
    keys = set(prev_pq.deficits) | set(curr_pq.deficits)
    for key in sorted(keys):
        prev_count = prev_pq.deficits.get(key, 0)
        curr_count = curr_pq.deficits.get(key, 0)
        if curr_count < prev_count:
            improved_deficits.append(key)
        elif curr_count > prev_count:
            worsened_deficits.append(key)
    confidence = "high"
    if min(prev_pq.llm_sessions, curr_pq.llm_sessions) == 0:
        confidence = "medium"
    if min(prev_pq.evaluated_sessions, curr_pq.evaluated_sessions) < 3:
        confidence = "low"
    return PromptQualityDelta(
        available=available,
        metric=_numeric_delta(prev_score, curr_score, decimals=1),
        previous_llm_sessions=prev_pq.llm_sessions,
        current_llm_sessions=curr_pq.llm_sessions,
        previous_heuristic_sessions=prev_pq.heuristic_sessions,
        current_heuristic_sessions=curr_pq.heuristic_sessions,
        previous_light_sessions=prev_pq.light_sessions,
        current_light_sessions=curr_pq.light_sessions,
        improved_deficits=improved_deficits[:3],
        worsened_deficits=worsened_deficits[:3],
        confidence=confidence,
    )


def _build_friction_delta(
    previous: SnapshotSource,
    current: SnapshotSource,
    axis_deltas: list[AxisDelta],
) -> FrictionDelta:
    prev_total = sum(previous.friction_type_counts.values())
    curr_total = sum(current.friction_type_counts.values())
    type_deltas: list[FrictionTypeDelta] = []
    keys = set(previous.friction_type_counts) | set(current.friction_type_counts)
    reduced_types: list[str] = []
    increased_types: list[str] = []
    for key in keys:
        prev_count = previous.friction_type_counts.get(key, 0)
        curr_count = current.friction_type_counts.get(key, 0)
        delta = curr_count - prev_count
        if delta < 0:
            reduced_types.append(key)
        elif delta > 0:
            increased_types.append(key)
        type_deltas.append(
            FrictionTypeDelta(
                key=key,
                previous_count=prev_count,
                current_count=curr_count,
                delta=delta,
                direction=_direction(delta),
            )
        )
    type_deltas.sort(key=lambda item: abs(item.delta), reverse=True)
    attribution_keys = set(previous.friction_by_attribution) | set(current.friction_by_attribution)
    attribution_deltas = {
        key: _numeric_delta(
            previous.friction_by_attribution.get(key, 0),
            current.friction_by_attribution.get(key, 0),
            decimals=0,
        )
        for key in attribution_keys
    }
    adaptive_delta = next(
        (item.delta for item in axis_deltas if item.key == "adaptive_recovery"),
        0.0,
    )
    recovery_signal = "flat"
    user_delta = attribution_deltas.get("user-actionable", NumericDelta()).delta
    if adaptive_delta >= 4 and user_delta <= 0:
        recovery_signal = "up"
    elif adaptive_delta <= -4 or user_delta > 0:
        recovery_signal = "down"
    return FrictionDelta(
        total=_numeric_delta(prev_total, curr_total, decimals=0),
        attribution_deltas=attribution_deltas,
        type_deltas=type_deltas[:6],
        reduced_types=sorted(reduced_types),
        increased_types=sorted(increased_types),
        adaptive_recovery_delta=adaptive_delta,
        recovery_signal=recovery_signal,
    )


def _build_method_asset_delta(previous: SnapshotSource, current: SnapshotSource) -> MethodAssetDelta:
    prev_assets = previous.method_assets
    curr_assets = current.method_assets
    total_prev = prev_assets.total_asset_files
    total_curr = curr_assets.total_asset_files
    workflow_prev = prev_assets.workflow_build_substantial_count + prev_assets.workflow_build_moderate_count
    workflow_curr = curr_assets.workflow_build_substantial_count + curr_assets.workflow_build_moderate_count
    assetization = _numeric_delta(prev_assets.assetized_session_rate * 100.0, curr_assets.assetized_session_rate * 100.0, decimals=1)
    return MethodAssetDelta(
        total_assets=_numeric_delta(total_prev, total_curr, decimals=0),
        unique_skills=_numeric_delta(prev_assets.unique_skill_count, curr_assets.unique_skill_count, decimals=0),
        workflow_assets=_numeric_delta(workflow_prev, workflow_curr, decimals=0),
        assetization_rate=assetization,
        stronger_reuse=(
            total_curr > total_prev
            or workflow_curr > workflow_prev
            or curr_assets.unique_skill_count > prev_assets.unique_skill_count
            or assetization.delta > 3.0
        ),
    )


def _build_confidence(
    previous: SnapshotSource,
    current: SnapshotSource,
    prompt_quality: PromptQualityDelta,
) -> ConfidenceAssessment:
    sample_size = min(
        previous.coverage.session_read_count or previous.coverage.session_count,
        current.coverage.session_read_count or current.coverage.session_count,
    )
    reasons: list[str] = []
    score = 100
    if sample_size < 4:
        reasons.append("small_sample")
        score -= 40
    elif sample_size < 8:
        reasons.append("limited_sample")
        score -= 20
    if previous.coverage.extraction_failed or current.coverage.extraction_failed:
        reasons.append("extraction_failed")
        score -= 20
    if not is_current_axis_schema(previous.axis_scores) or not is_current_axis_schema(current.axis_scores):
        reasons.append("axis_schema_mismatch")
        score -= 35
    if has_legacy_axis_schema(previous.axis_scores) or has_legacy_axis_schema(current.axis_scores):
        reasons.append("legacy_axis_schema")
        score -= 15
    if not previous.coverage.has_usage_data or not current.coverage.has_usage_data:
        reasons.append("missing_usage")
        score -= 10
    if prompt_quality.confidence == "low":
        reasons.append("prompt_proxy")
        score -= 20
    elif prompt_quality.confidence == "medium":
        reasons.append("prompt_mixed")
        score -= 10
    score = max(15, score)
    if score >= 80:
        level = "high"
    elif score >= 55:
        level = "medium"
    else:
        level = "low"
    return ConfidenceAssessment(
        level=level,
        score=score,
        sample_size=sample_size,
        has_usage_data=previous.coverage.has_usage_data and current.coverage.has_usage_data,
        has_prompt_quality_data=prompt_quality.available,
        reasons=reasons,
    )


def _build_evidence_cards(
    previous: SnapshotSource,
    current: SnapshotSource,
    axis_deltas: list[AxisDelta],
    friction: FrictionDelta,
    method_assets: MethodAssetDelta,
) -> list[EvidenceCard]:
    strongest_gain = next((item for item in axis_deltas if item.delta > 0), axis_deltas[0] if axis_deltas else None)
    primary_gap = next((item for item in sorted(axis_deltas, key=lambda row: row.delta) if item.delta < 0), None)
    cards: list[EvidenceCard] = [
        EvidenceCard(
            topic="overall",
            direction=_overall_direction(current.mirror_score - previous.mirror_score, LEVEL_ORDER.get(current.growth_level, 0) - LEVEL_ORDER.get(previous.growth_level, 0)),
            summaries=_fallback_evidence(
                current.evidence_by_topic.get("overall", []),
                [
                    current.headline,
                    f"mirror_score {previous.mirror_score} -> {current.mirror_score}",
                    f"focus {previous.next_focus} -> {current.next_focus}",
                ],
            ),
        )
    ]
    if strongest_gain is not None:
        cards.append(
            EvidenceCard(
                topic="strongest_gain",
                axis_key=strongest_gain.key,
                direction=strongest_gain.direction,
                summaries=_fallback_evidence(
                    current.evidence_by_topic.get(strongest_gain.key, []),
                    [
                        f"{strongest_gain.key} {strongest_gain.previous:.1f} -> {strongest_gain.current:.1f}",
                        f"weighted contribution {strongest_gain.weighted_contribution:+.1f}",
                    ],
                ),
            )
        )
    if primary_gap is not None:
        cards.append(
            EvidenceCard(
                topic="primary_gap",
                axis_key=primary_gap.key,
                direction=primary_gap.direction,
                summaries=_fallback_evidence(
                    current.evidence_by_topic.get(primary_gap.key, []),
                    [
                        f"{primary_gap.key} {primary_gap.previous:.1f} -> {primary_gap.current:.1f}",
                        current.next_focus,
                    ],
                ),
            )
        )
    cards.append(
        EvidenceCard(
            topic="friction",
            direction=friction.total.direction,
            summaries=_fallback_evidence(
                current.evidence_by_topic.get("friction", []),
                [
                    f"friction total {friction.total.previous:.0f} -> {friction.total.current:.0f}",
                    ", ".join(friction.increased_types[:2]) if friction.increased_types else "",
                    ", ".join(friction.reduced_types[:2]) if friction.reduced_types else "",
                ],
            ),
        )
    )
    cards.append(
        EvidenceCard(
            topic="method_assets",
            direction=method_assets.total_assets.direction,
            summaries=_fallback_evidence(
                current.evidence_by_topic.get("method_assets", []),
                [
                    f"asset files {method_assets.total_assets.previous:.0f} -> {method_assets.total_assets.current:.0f}",
                    f"workflow assets {method_assets.workflow_assets.previous:.0f} -> {method_assets.workflow_assets.current:.0f}",
                    f"unique skills {method_assets.unique_skills.previous:.0f} -> {method_assets.unique_skills.current:.0f}",
                ],
            ),
        )
    )
    return cards[:5]


def _build_priorities(
    current: SnapshotSource,
    axis_deltas: list[AxisDelta],
    friction: FrictionDelta,
    prompt_quality: PromptQualityDelta,
    method_assets: MethodAssetDelta,
) -> list[TrainingPriority]:
    priorities: list[TrainingPriority] = []
    weakest = min(axis_deltas, key=lambda item: item.current) if axis_deltas else None
    regressed = min(axis_deltas, key=lambda item: item.delta) if axis_deltas else None
    if weakest is not None:
        reasons = ["weakest_axis"]
        if regressed is not None and regressed.key == weakest.key and regressed.delta < 0:
            reasons.append("regressed_axis")
        if friction.recovery_signal == "down" and weakest.key == "adaptive_recovery":
            reasons.append("friction_hotspot")
        if prompt_quality.worsened_deficits and weakest.key in {PQ_AXIS_MAP.get(key, "") for key in prompt_quality.worsened_deficits}:
            reasons.append("prompt_gap")
        priorities.append(
            TrainingPriority(
                axis_key=weakest.key,
                priority="primary",
                reason_codes=reasons,
                supporting_topics=["friction", "prompt_quality"],
                evidence_summaries=_fallback_evidence(
                    current.evidence_by_topic.get(weakest.key, []),
                    [current.next_focus, current.headline],
                ),
            )
        )
    if regressed is not None and (weakest is None or regressed.key != weakest.key) and regressed.delta < 0:
        reasons = ["regressed_axis"]
        if method_assets.stronger_reuse is False and regressed.key in {"execution_driving", "adaptive_recovery"}:
            reasons.append("method_gap")
        priorities.append(
            TrainingPriority(
                axis_key=regressed.key,
                priority="secondary",
                reason_codes=reasons,
                supporting_topics=["method_assets"],
                evidence_summaries=_fallback_evidence(
                    current.evidence_by_topic.get(regressed.key, []),
                    [current.next_focus],
                ),
            )
        )
    return priorities[:2]


def _numeric_delta(previous: float, current: float, *, decimals: int) -> NumericDelta:
    delta = round(current - previous, decimals)
    return NumericDelta(
        previous=round(previous, decimals),
        current=round(current, decimals),
        delta=delta,
        direction=_direction(delta),
    )


def _direction(delta: float) -> str:
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _magnitude(delta: float) -> str:
    value = abs(delta)
    if value >= 10:
        return "strong"
    if value >= 5:
        return "medium"
    if value >= 1:
        return "light"
    return "flat"


def _overall_direction(score_delta: float, level_delta: int) -> str:
    if level_delta > 0 or score_delta >= 4:
        return "up"
    if level_delta < 0 or score_delta <= -4:
        return "down"
    return "flat"


def _overall_code(score_delta: float, level_delta: int) -> str:
    if level_delta > 0:
        return "stage_up"
    if level_delta < 0:
        return "stage_down"
    if score_delta >= 4:
        return "score_up"
    if score_delta <= -4:
        return "score_down"
    return "stable"


def _fallback_evidence(primary: list[str], fallback: list[str]) -> list[str]:
    rows: list[str] = []
    for item in [*primary, *fallback]:
        text = (item or "").strip()
        if text and text not in rows:
            rows.append(text)
        if len(rows) >= 3:
            break
    return rows
