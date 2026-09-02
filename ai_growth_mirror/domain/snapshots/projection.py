"""Pure business projections shared by live and archived snapshot sources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_ACTIONABLE_FRICTION_SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "vague_request": (("pq", "vague-request"), ("friction", "fuzzy-intent"), ("friction", "ambiguous-request")),
    "missing_context": (("pq", "missing-context"), ("friction", "missing-context"), ("friction", "context-gap"), ("friction", "context-confusion")),
    "scope_drift": (("pq", "scope-drift"), ("friction", "scope-creep"), ("friction", "goal-drift")),
    "missing_acceptance_criteria": (("pq", "missing-acceptance-criteria"), ("friction", "missing-acceptance-criteria"), ("friction", "incomplete-output")),
    "unclear_correction": (("pq", "unclear-correction"), ("friction", "off-track"), ("friction", "outdated-context"), ("friction", "recurring-pattern")),
}

_FRICTION_TOPIC_BY_CATEGORY = {
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


def build_actionable_friction_counts(
    *,
    pq_deficits: Mapping[str, Any],
    friction_type_counts: Mapping[str, Any],
) -> dict[str, int]:
    """Project raw deficit categories into the five actionable friction groups."""
    sources = {"pq": pq_deficits, "friction": friction_type_counts}
    return {
        target: sum(int(sources[source].get(key, 0) or 0) for source, key in mappings)
        for target, mappings in _ACTIONABLE_FRICTION_SOURCES.items()
    }


def topic_from_friction(category: str) -> str:
    """Map a canonical friction category to the affected capability topic."""
    return _FRICTION_TOPIC_BY_CATEGORY.get(category, "")


__all__ = ["build_actionable_friction_counts", "topic_from_friction"]
