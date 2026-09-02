"""Pure capability score derivation from growth profile aggregates."""

from __future__ import annotations

from .model import GrowthProfile


def compute_capability_scores(stats: GrowthProfile) -> dict[str, float]:
    """Project canonical assessment axes without recomputing their semantics."""
    scores = stats.agentic_sub_scores or {}
    if scores:
        return {key: min(round(value, 1), 100.0) for key, value in scores.items()}
    if stats.radar_axes:
        return {axis.key: axis.score for axis in stats.radar_axes if axis.has_data}
    return {}
