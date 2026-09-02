"""Pure value objects and domain service for growth assessment policy 2.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .assessment_policy import (
    ASSESSMENT_POLICY_VERSION,
    AXIS_WEIGHTS,
    COMPONENT_WEIGHTS,
    LEVEL_MIN_SCORES,
    MIN_AXIS_COVERAGE,
)


@dataclass(frozen=True)
class MetricObservation:
    value: Optional[float]
    available: bool
    evidence_count: int = 0
    denominator: Optional[int] = None
    confidence: float = 0.0
    reason_codes: tuple[str, ...] = ()

    @classmethod
    def missing(cls, reason: str = "not_observed") -> "MetricObservation":
        return cls(None, False, reason_codes=(reason,))

    @classmethod
    def observed(
        cls,
        value: float,
        *,
        evidence_count: int,
        denominator: Optional[int] = None,
        reason: str = "observed",
    ) -> "MetricObservation":
        bounded = max(0.0, min(100.0, float(value)))
        if denominator is not None and denominator > 0:
            sample_confidence = min(1.0, evidence_count / max(5.0, float(denominator)))
        else:
            sample_confidence = min(1.0, evidence_count / 10.0)
        return cls(
            bounded,
            True,
            max(0, evidence_count),
            denominator,
            round(max(0.1, sample_confidence), 3),
            (reason,),
        )


@dataclass(frozen=True)
class AxisComponent:
    key: str
    weight: float
    observation: MetricObservation
    normalized_weight: float = 0.0
    contribution: float = 0.0


@dataclass(frozen=True)
class AxisAssessment:
    key: str
    score: Optional[float]
    coverage: float
    confidence: float
    components: tuple[AxisComponent, ...]
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssessmentResult:
    policy_version: str
    mirror_score: Optional[int]
    growth_level: Optional[str]
    axes: tuple[AxisAssessment, ...]


@dataclass(frozen=True)
class AssessmentInputs:
    session_count: int = 0

    effective_contract_rate: Optional[float] = None
    context_grounding_rate: Optional[float] = None
    goal_locking_score: Optional[float] = None
    goal_locking_evidence_count: int = 0
    active_clarification_rate: Optional[float] = None
    clarification_opportunity_count: int = 0
    clarification_evidence_count: int = 0

    autonomous_chain_score: Optional[float] = None
    structured_workflow_rate: Optional[float] = None
    verified_continuation_rate: Optional[float] = None
    delegation_success_rate: Optional[float] = None
    delegation_evidence_count: int = 0

    implementation_session_rate: Optional[float] = None
    code_verification_rate: Optional[float] = None
    fully_achieved_rate: Optional[float] = None
    files_per_session: Optional[float] = None

    verification_rate: Optional[float] = None
    test_run_rate: Optional[float] = None
    contract_compliance_rate: Optional[float] = None
    contract_compliance_denominator: int = 0

    recovery_success_rate: Optional[float] = None
    recovery_opportunity_count: int = 0
    recovery_success_evidence_count: int = 0
    correction_quality: Optional[float] = None
    correction_evidence_count: int = 0
    post_friction_verification_rate: Optional[float] = None

    skill_outcome_rate: Optional[float] = None
    workflow_outcome_rate: Optional[float] = None
    structured_outcome_rate: Optional[float] = None
    workflow_reuse_depth: Optional[int] = None
    asset_authoring_outcome_rate: Optional[float] = None
    assetized_outcome_rate: Optional[float] = None
    advanced_feature_outcome_rate: Optional[float] = None
    method_saturation: Optional[float] = None

    # Context-only quantities. They deliberately never enter component maps.
    total_token_volume: int = 0
    total_files_modified: int = 0
    distinct_tool_count: int = 0
    distinct_model_count: int = 0
    total_subagent_invocations: int = 0
    commit_rate: float = 0.0


def _rate(
    value: Optional[float],
    *,
    evidence_count: int,
    denominator: Optional[int] = None,
    available: bool = True,
    reason: str,
) -> MetricObservation:
    if value is None or not available:
        return MetricObservation.missing(f"{reason}_unavailable")
    return MetricObservation.observed(
        float(value) * 100.0,
        evidence_count=evidence_count,
        denominator=denominator,
        reason=reason,
    )


def _score(
    value: Optional[float],
    *,
    evidence_count: int,
    available: bool = True,
    reason: str,
) -> MetricObservation:
    if value is None or not available:
        return MetricObservation.missing(f"{reason}_unavailable")
    return MetricObservation.observed(value, evidence_count=evidence_count, reason=reason)


def _saturating(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    if high <= low:
        return 100.0
    return max(0.0, min(100.0, (float(value) - low) / (high - low) * 100.0))


def _assess_axis(key: str, observations: dict[str, MetricObservation]) -> AxisAssessment:
    weights = COMPONENT_WEIGHTS[key]
    available_weight = sum(
        weight for component, weight in weights.items() if observations[component].available
    )
    coverage = round(available_weight / sum(weights.values()), 3)
    if available_weight <= 0.0 or coverage < MIN_AXIS_COVERAGE:
        components = tuple(
            AxisComponent(component, weight, observations[component])
            for component, weight in weights.items()
        )
        return AxisAssessment(key, None, coverage, 0.0, components, ("insufficient_evidence",))

    components: list[AxisComponent] = []
    confidence_total = 0.0
    score_total = 0.0
    for component, weight in weights.items():
        observation = observations[component]
        normalized = weight / available_weight if observation.available else 0.0
        contribution = (observation.value or 0.0) * normalized
        score_total += contribution
        confidence_total += observation.confidence * normalized
        components.append(
            AxisComponent(
                component,
                weight,
                observation,
                round(normalized, 4),
                round(contribution, 2),
            )
        )
    return AxisAssessment(
        key,
        round(score_total, 1),
        coverage,
        round(confidence_total * coverage, 3),
        tuple(components),
        ("assessed",),
    )


def _growth_level(score: int) -> str:
    for level in reversed(tuple(LEVEL_MIN_SCORES)):
        if score >= LEVEL_MIN_SCORES[level]:
            return level
    return "L1"


def assess_growth(inputs: AssessmentInputs) -> AssessmentResult:
    sessions = max(0, inputs.session_count)
    session_evidence = sessions
    outcome_binding = (inputs.fully_achieved_rate or 0.0) > 0.0 or (inputs.verification_rate or 0.0) > 0.0

    observations: dict[str, dict[str, MetricObservation]] = {
        "collaboration_framing": {
            "effective_contract": _rate(inputs.effective_contract_rate, evidence_count=session_evidence, denominator=sessions or None, reason="contract_observed"),
            "context_grounding": _rate(inputs.context_grounding_rate, evidence_count=session_evidence, denominator=sessions or None, reason="context_observed"),
            "goal_locking": _score(inputs.goal_locking_score, evidence_count=inputs.goal_locking_evidence_count, available=inputs.goal_locking_evidence_count > 0, reason="goal_locking_observed"),
            "active_clarification": _rate(inputs.active_clarification_rate, evidence_count=inputs.clarification_evidence_count, denominator=inputs.clarification_opportunity_count or None, available=inputs.clarification_opportunity_count > 0 and inputs.clarification_evidence_count > 0, reason="clarification_opportunity"),
        },
        "execution_driving": {
            "autonomous_chain": _score(inputs.autonomous_chain_score, evidence_count=session_evidence, reason="autonomous_chain_observed"),
            "structured_workflow": _rate(inputs.structured_workflow_rate, evidence_count=session_evidence, denominator=sessions or None, reason="structured_workflow_observed"),
            "verified_continuation": _rate(inputs.verified_continuation_rate, evidence_count=session_evidence, denominator=sessions or None, reason="verified_continuation_observed"),
            "delegation_success": _rate(inputs.delegation_success_rate, evidence_count=inputs.delegation_evidence_count, denominator=inputs.delegation_evidence_count or None, available=inputs.delegation_evidence_count > 0, reason="delegation_result_observed"),
        },
        "implementation_depth": {
            "implementation_sessions": _rate(inputs.implementation_session_rate, evidence_count=session_evidence, denominator=sessions or None, reason="implementation_observed"),
            "code_verification": _rate(inputs.code_verification_rate, evidence_count=session_evidence, denominator=sessions or None, reason="code_verification_observed"),
            "fully_achieved": _rate(inputs.fully_achieved_rate, evidence_count=session_evidence, denominator=sessions or None, reason="outcome_observed"),
            "files_per_session": _score(_saturating(inputs.files_per_session, 0.5, 3.0), evidence_count=session_evidence, reason="bounded_change_breadth"),
        },
        "delivery_closure": {
            "fully_achieved": _rate(inputs.fully_achieved_rate, evidence_count=session_evidence, denominator=sessions or None, reason="outcome_observed"),
            "verification": _rate(inputs.verification_rate, evidence_count=session_evidence, denominator=sessions or None, reason="verification_observed"),
            "tests": _rate(inputs.test_run_rate, evidence_count=session_evidence, denominator=sessions or None, reason="tests_observed"),
            "contract_compliance": _rate(inputs.contract_compliance_rate, evidence_count=inputs.contract_compliance_denominator, denominator=inputs.contract_compliance_denominator or None, available=inputs.contract_compliance_denominator > 0, reason="contract_compliance_observed"),
        },
        "adaptive_recovery": {
            "recovery_success": _rate(inputs.recovery_success_rate, evidence_count=inputs.recovery_success_evidence_count, denominator=inputs.recovery_opportunity_count or None, available=inputs.recovery_opportunity_count > 0 and inputs.recovery_success_evidence_count > 0, reason="recovery_opportunity"),
            "correction_quality": _score(inputs.correction_quality, evidence_count=inputs.correction_evidence_count, available=inputs.recovery_opportunity_count > 0 and inputs.correction_evidence_count > 0, reason="correction_observed"),
            "post_friction_verification": _rate(inputs.post_friction_verification_rate, evidence_count=inputs.recovery_opportunity_count, denominator=inputs.recovery_opportunity_count or None, available=inputs.recovery_opportunity_count > 0, reason="post_friction_verification"),
        },
        "agentic_system": {
            "skill_outcome": _rate(inputs.skill_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="skill_bound_to_outcome"),
            "workflow_outcome": _rate(inputs.workflow_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="workflow_bound_to_outcome"),
            "structured_outcome": _rate(inputs.structured_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="structure_bound_to_outcome"),
            "workflow_reuse": _score(_saturating(float(inputs.workflow_reuse_depth) if inputs.workflow_reuse_depth is not None else None, 1.0, 5.0), evidence_count=session_evidence, available=outcome_binding, reason="reuse_bound_to_outcome"),
            "asset_authoring": _rate(inputs.asset_authoring_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="authoring_bound_to_outcome"),
            "assetized_outcome": _rate(inputs.assetized_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="asset_bound_to_outcome"),
            "advanced_feature_outcome": _rate(inputs.advanced_feature_outcome_rate, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="feature_bound_to_outcome"),
            "method_saturation": _rate(inputs.method_saturation, evidence_count=session_evidence, denominator=sessions or None, available=outcome_binding, reason="method_bound_to_outcome"),
        },
    }

    axes = tuple(_assess_axis(key, observations[key]) for key in AXIS_WEIGHTS)
    available = [axis for axis in axes if axis.score is not None]
    if not available:
        return AssessmentResult(ASSESSMENT_POLICY_VERSION, None, None, axes)
    available_axis_weight = sum(AXIS_WEIGHTS[axis.key] for axis in available)
    score = round(
        sum((axis.score or 0.0) * AXIS_WEIGHTS[axis.key] for axis in available)
        / available_axis_weight
    )
    score = max(0, min(100, score))
    if sessions < 8:
        score = min(score, 69)
    elif sessions < 15:
        score = min(score, 82)
    return AssessmentResult(ASSESSMENT_POLICY_VERSION, score, _growth_level(score), axes)
