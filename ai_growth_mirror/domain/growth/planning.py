"""Domain planning rules for next-step growth priorities."""

from __future__ import annotations

from typing import NamedTuple

from .model import GrowthProfile


class RankedPriority(NamedTuple):
    key: str
    urgency: float


def priority_family(key: str) -> str:
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
) -> list[RankedPriority]:
    candidates: list[RankedPriority] = []

    for gap in getattr(stats, "gap_rankings", [])[:3]:
        candidates.append(RankedPriority(gap.key, min(max(gap.severity, 0.0), 100.0)))

    pq_dims = stats.pq_avg_dimensions or {}
    if pq_dims:
        weakest_key, weakest_value = min(pq_dims.items(), key=lambda item: item[1])
        candidates.append(RankedPriority(f"prompt:{weakest_key}", 100.0 - weakest_value))

    for capability_key, threshold, urgency_base in (
        ("delivery_closure", 62.0, 92.0),
        ("implementation_depth", 58.0, 86.0),
        ("adaptive_recovery", 56.0, 84.0),
        ("intent_clarity", 60.0, 80.0),
        ("execution_driving", 58.0, 76.0),
    ):
        score = capability_scores.get(capability_key, 0.0)
        if score < threshold:
            candidates.append(RankedPriority(capability_key, urgency_base - score))

    user_actionable = stats.friction_by_attribution.get("user-actionable", 0)
    total_friction = max(sum(stats.friction_by_attribution.values()), 1)
    if user_actionable / total_friction >= 0.25:
        candidates.append(RankedPriority("friction", 72.0))

    if not candidates:
        candidates.append(RankedPriority("consolidation", 60.0))

    candidates.sort(key=lambda item: item.urgency, reverse=True)
    return candidates


def select_growth_priority_keys(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    *,
    limit: int,
) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for key, _urgency in rank_growth_priorities(stats, capability_scores):
        family = priority_family(key)
        if family in seen:
            continue
        seen.add(family)
        deduped.append(key)
        if len(deduped) >= limit:
            break
    return deduped
