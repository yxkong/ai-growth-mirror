"""Domain planning rules for next-step growth priorities."""

from __future__ import annotations

from typing import NamedTuple

from .model import GrowthProfile


class RankedPriority(NamedTuple):
    key: str
    urgency: float
    reason_codes: tuple[str, ...] = ()


def priority_family(key: str) -> str:
    if key in {"prompt:context_provision", "prompt:request_specificity", "prompt:scope_management"}:
        return "intent_clarity"
    if key == "prompt:information_timing":
        return "execution_driving"
    if key in {"friction", "prompt:correction_quality", "adaptive_recovery"}:
        return "course_correction"
    if key in {"delivery_closure", "verification_gap", "closure_gap"}:
        return "delivery_closure"
    if key in {"intent_clarity", "framing_gap", "scope_control_gap"}:
        return "intent_clarity"
    if key in {"implementation_depth", "code_penetration_gap"}:
        return "implementation_depth"
    if key in {"execution_driving", "workflow_composition_gap"}:
        return "execution_driving"
    return key


def rank_growth_priorities(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    *,
    trend_axis_keys: tuple[str, ...] = (),
    regression_axis_keys: tuple[str, ...] = (),
    weakest_prompt_dimension: str = "",
    top_deficit_keys: tuple[str, ...] = (),
) -> list[RankedPriority]:
    candidates: list[RankedPriority] = []

    for gap in getattr(stats, "gap_rankings", [])[:3]:
        candidates.append(
            RankedPriority(
                gap.key,
                min(max(gap.severity, 0.0), 100.0),
                ("gap_ranking",),
            )
        )

    pq_dims = stats.pq_avg_dimensions or {}
    if weakest_prompt_dimension and weakest_prompt_dimension in pq_dims:
        weakest_value = pq_dims.get(weakest_prompt_dimension, 0.0)
        candidates.append(
            RankedPriority(
                f"prompt:{weakest_prompt_dimension}",
                100.0 - weakest_value + 6.0,
                ("prompt_weakest_dimension",),
            )
        )
    elif pq_dims:
        weakest_key, weakest_value = min(pq_dims.items(), key=lambda item: item[1])
        candidates.append(
            RankedPriority(
                f"prompt:{weakest_key}",
                100.0 - weakest_value,
                ("prompt_weakest_dimension",),
            )
        )

    for capability_key, threshold, urgency_base in (
        ("delivery_closure", 62.0, 92.0),
        ("implementation_depth", 58.0, 86.0),
        ("adaptive_recovery", 56.0, 84.0),
        ("intent_clarity", 60.0, 80.0),
        ("execution_driving", 58.0, 76.0),
    ):
        score = capability_scores.get(capability_key, 0.0)
        if score < threshold:
            candidates.append(
                RankedPriority(capability_key, urgency_base - score, ("capability_threshold",))
            )

    user_actionable = stats.friction_by_attribution.get("user-actionable", 0)
    total_friction = max(sum(stats.friction_by_attribution.values()), 1)
    if user_actionable / total_friction >= 0.25:
        candidates.append(RankedPriority("friction", 72.0, ("user_actionable_friction",)))

    for key in regression_axis_keys:
        candidates.append(RankedPriority(key, 96.0, ("latest_regression",)))
    for key in trend_axis_keys:
        candidates.append(RankedPriority(key, 88.0, ("trend_stall",)))

    deficit_priority_map = {
        "missing-context": ("prompt:context_provision", 95.0, "deficit_missing_context"),
        "vague-request": ("prompt:request_specificity", 94.0, "deficit_vague_request"),
        "scope-drift": ("prompt:scope_management", 92.0, "deficit_scope_drift"),
        "missing-acceptance-criteria": ("delivery_closure", 93.0, "deficit_missing_acceptance"),
        "unclear-correction": ("prompt:correction_quality", 91.0, "deficit_unclear_correction"),
        "late-constraint": ("prompt:information_timing", 89.0, "deficit_late_constraint"),
        "assumption-not-surfaced": ("intent_clarity", 87.0, "deficit_assumption"),
    }
    for deficit_key in top_deficit_keys:
        mapped = deficit_priority_map.get(deficit_key)
        if mapped is None:
            continue
        mapped_key, urgency, reason_code = mapped
        candidates.append(RankedPriority(mapped_key, urgency, (reason_code,)))

    if not candidates:
        candidates.append(RankedPriority("consolidation", 60.0, ("fallback",)))

    candidates.sort(key=lambda item: item.urgency, reverse=True)
    return candidates


def select_growth_priority_keys(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    *,
    limit: int,
    trend_axis_keys: tuple[str, ...] = (),
    regression_axis_keys: tuple[str, ...] = (),
    weakest_prompt_dimension: str = "",
    top_deficit_keys: tuple[str, ...] = (),
) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for key, _urgency, _reason_codes in rank_growth_priorities(
        stats,
        capability_scores,
        trend_axis_keys=trend_axis_keys,
        regression_axis_keys=regression_axis_keys,
        weakest_prompt_dimension=weakest_prompt_dimension,
        top_deficit_keys=top_deficit_keys,
    ):
        family = priority_family(key)
        if family in seen:
            continue
        seen.add(family)
        deduped.append(key)
        if len(deduped) >= limit:
            break
    return deduped
