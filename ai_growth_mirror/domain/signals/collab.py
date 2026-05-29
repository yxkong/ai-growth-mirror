"""Custom collaboration style system for the personal growth report.

This intentionally does not reuse the older "personality" dimension names.
It focuses on the user's collaboration operating model instead of broad
personality labels, so every dimension maps directly to trainable behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from ..growth.model import GrowthProfile

if TYPE_CHECKING:
    from ..growth.model import AgentAssetStats


@dataclass
class CollaborationStyleDimension:
    key: str
    label: str
    left_pole: str
    right_pole: str
    pct: float
    interpretation: str


@dataclass
class CollaborationStyleResult:
    archetype_name: str
    archetype_tag: str
    slogan: str
    description: str
    strengths: list[str] = field(default_factory=list)
    growth_areas: list[str] = field(default_factory=list)
    dimensions: list[CollaborationStyleDimension] = field(default_factory=list)


@dataclass(frozen=True)
class CollaborationCapabilityProfile:
    planning_score: float
    orchestration_score: float
    evidence_score: float
    reuse_score: float
    depth_score: float

    @classmethod
    def from_capability_scores(cls, capability_scores: dict[str, float]) -> "CollaborationCapabilityProfile":
        return cls(
            planning_score=capability_scores.get("intent_clarity", 0.0),
            orchestration_score=capability_scores.get("execution_driving", 0.0),
            evidence_score=capability_scores.get("delivery_closure", 0.0),
            reuse_score=capability_scores.get("adaptive_recovery", 0.0),
            depth_score=capability_scores.get("implementation_depth", 0.0),
        )


def compute_collaboration_style(
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    *,
    style_labels: dict[str, Any],
    agent_asset: "Optional[AgentAssetStats]" = None,
) -> CollaborationStyleResult:
    profile = CollaborationCapabilityProfile.from_capability_scores(capability_scores)
    plan_pct = _clamp(
        (
            profile.planning_score * 0.40
            + (stats.pq_avg_dimensions or {}).get("context_provision", 50.0) * 0.30
            + (stats.pq_avg_dimensions or {}).get("scope_management", 50.0) * 0.25
            + profile.depth_score * 0.05
        )
    )
    orchestration_pct = _clamp(
        (
            profile.orchestration_score * 0.45
            + profile.depth_score * 0.25
            + min((stats.subagent_session_rate or 0.0) * 100 * 1.4, 100.0) * 0.20
            + min((stats.tier_diversity_count / 5.0) * 100, 100.0) * 0.10
        )
    )
    evidence_pct = _clamp(
        (
            profile.evidence_score * 0.65
            + min((getattr(stats, "test_run_rate", 0.0) or 0.0) * 100, 100.0) * 0.30
            + profile.planning_score * 0.05
        )
    )
    reuse_pct = _clamp(
        (
            profile.reuse_score * 0.35
            + profile.orchestration_score * 0.20
            + min((stats.tool_build_rate or 0.0) * 100, 100.0) * 0.25
            + min((stats.advanced_feature_ratio or 0.0) * 100, 100.0) * 0.20
        )
    )

    # Boost reuse_pct when user has a significant hub asset library.
    # This compensates for heuristic mode's blind spot: session-level path
    # matching misses skill files that live in the hub root.
    if agent_asset is not None and agent_asset.has_data:
        hub_skill_boost = min(agent_asset.skill_files_count / 40.0, 1.0) * 35.0
        hub_total_boost = min(agent_asset.total_asset_files / 80.0, 1.0) * 20.0
        reuse_pct = _clamp(reuse_pct + (hub_skill_boost + hub_total_boost) * 0.5)

    dim_labels = style_labels.get("dimensions", {})
    pct_by_key = {
        "planning": plan_pct,
        "orchestration": orchestration_pct,
        "evidence": evidence_pct,
        "reuse": reuse_pct,
    }
    dims: list[CollaborationStyleDimension] = []
    for key, pct in pct_by_key.items():
        meta = dim_labels.get(key, {})
        high = pct >= 55
        interpretation_key = "interpretation_high" if high else "interpretation_low"
        dims.append(
            CollaborationStyleDimension(
                key=key,
                label=meta.get("label", key),
                left_pole=meta.get("left_pole", ""),
                right_pole=meta.get("right_pole", ""),
                pct=pct,
                interpretation=meta.get(interpretation_key, ""),
            )
        )

    pole_meta = style_labels.get("poles", {})
    poles = {
        key: pole_meta.get(key, {}).get("high" if pct_by_key[key] >= 55 else "low", "")
        for key in pct_by_key
    }

    archetype_cfg = style_labels.get("archetype", {})
    archetype_name = archetype_cfg.get("name_pattern", "{planning}{orchestration}").format(**poles)
    archetype_tag = archetype_cfg.get("tag_pattern", "{evidence}×{reuse}").format(**poles)

    strengths = _strengths(
        plan_pct=plan_pct,
        orchestration_pct=orchestration_pct,
        evidence_pct=evidence_pct,
        reuse_pct=reuse_pct,
        style_labels=style_labels,
    )
    growth_areas = _growth_areas(
        plan_pct=plan_pct,
        orchestration_pct=orchestration_pct,
        evidence_pct=evidence_pct,
        reuse_pct=reuse_pct,
        style_labels=style_labels,
    )
    slogan, description = _narrative(
        plan_pct=plan_pct,
        orchestration_pct=orchestration_pct,
        evidence_pct=evidence_pct,
        reuse_pct=reuse_pct,
        archetype_name=archetype_name,
        style_labels=style_labels,
    )
    return CollaborationStyleResult(
        archetype_name=archetype_name,
        archetype_tag=archetype_tag,
        slogan=slogan,
        description=description,
        strengths=strengths,
        growth_areas=growth_areas,
        dimensions=dims,
    )


def _strengths(
    *,
    plan_pct: float,
    orchestration_pct: float,
    evidence_pct: float,
    reuse_pct: float,
    style_labels: dict[str, Any],
) -> list[str]:
    strength_labels = style_labels.get("strengths", {})
    strengths: list[str] = []
    if plan_pct >= 55:
        strengths.append(strength_labels.get("planning", ""))
    if orchestration_pct >= 55:
        strengths.append(strength_labels.get("orchestration", ""))
    if evidence_pct >= 55:
        strengths.append(strength_labels.get("evidence", ""))
    if reuse_pct >= 55:
        strengths.append(strength_labels.get("reuse", ""))
    if not strengths:
        strengths.append(strength_labels.get("fallback", ""))
    return [item for item in strengths if item][:4]


def _growth_areas(
    *,
    plan_pct: float,
    orchestration_pct: float,
    evidence_pct: float,
    reuse_pct: float,
    style_labels: dict[str, Any],
) -> list[str]:
    growth_labels = style_labels.get("growth", {})
    growth: list[str] = []
    scores = {
        "planning": plan_pct,
        "orchestration": orchestration_pct,
        "evidence": evidence_pct,
        "reuse": reuse_pct,
    }
    for key, _score in sorted(scores.items(), key=lambda item: item[1])[:2]:
        text = growth_labels.get(key, "")
        if text:
            growth.append(text)
    return growth


def _narrative(
    *,
    plan_pct: float,
    orchestration_pct: float,
    evidence_pct: float,
    reuse_pct: float,
    archetype_name: str,
    style_labels: dict[str, Any],
) -> tuple[str, str]:
    narrative = style_labels.get("narrative", {})
    slogan = narrative.get("slogan", "")
    description = narrative.get("description", "").format(archetype_name=archetype_name)
    if evidence_pct < 55:
        description += narrative.get("description_evidence_low", "")
    elif reuse_pct < 55:
        description += narrative.get("description_reuse_low", "")
    return slogan, description


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 1)))
