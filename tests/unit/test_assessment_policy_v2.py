from __future__ import annotations

from dataclasses import replace

from ai_growth_mirror.domain.growth.assessment import (
    AssessmentInputs,
    assess_growth,
)
from ai_growth_mirror.domain.growth.assessment_policy import (
    ASSESSMENT_POLICY_VERSION,
    AXIS_WEIGHTS,
)
from ai_growth_mirror.domain.snapshots.comparison import compare_snapshot_sources
from ai_growth_mirror.domain.snapshots.model import SnapshotSource


def _credible_inputs() -> AssessmentInputs:
    return AssessmentInputs(
        session_count=20,
        effective_contract_rate=0.8,
        context_grounding_rate=0.8,
        goal_locking_score=80.0,
        goal_locking_evidence_count=12,
        active_clarification_rate=0.5,
        clarification_opportunity_count=10,
        clarification_evidence_count=10,
        autonomous_chain_score=75.0,
        structured_workflow_rate=0.7,
        verified_continuation_rate=0.7,
        delegation_success_rate=0.6,
        delegation_evidence_count=5,
        implementation_session_rate=0.8,
        code_verification_rate=0.7,
        fully_achieved_rate=0.7,
        files_per_session=3.0,
        verification_rate=0.7,
        test_run_rate=0.6,
        contract_compliance_rate=0.8,
        contract_compliance_denominator=12,
        recovery_success_rate=0.7,
        recovery_opportunity_count=5,
        recovery_success_evidence_count=5,
        correction_quality=70.0,
        correction_evidence_count=5,
        post_friction_verification_rate=0.6,
        skill_outcome_rate=0.6,
        workflow_outcome_rate=0.7,
        structured_outcome_rate=0.7,
        workflow_reuse_depth=4,
        asset_authoring_outcome_rate=0.3,
        assetized_outcome_rate=0.5,
        advanced_feature_outcome_rate=0.5,
        method_saturation=0.6,
    )


def test_policy_has_one_versioned_weight_set() -> None:
    assert ASSESSMENT_POLICY_VERSION == "2.0"
    assert round(sum(AXIS_WEIGHTS.values()), 10) == 1.0


def test_missing_is_unavailable_not_zero_or_perfect() -> None:
    result = assess_growth(AssessmentInputs(session_count=20))
    by_key = {axis.key: axis for axis in result.axes}
    assert by_key["adaptive_recovery"].score is None
    assert by_key["adaptive_recovery"].coverage == 0.0
    assert result.policy_version == ASSESSMENT_POLICY_VERSION


def test_no_recovery_opportunity_cannot_earn_recovery_score() -> None:
    inputs = replace(
        _credible_inputs(),
        fully_achieved_rate=1.0,
        verification_rate=1.0,
        recovery_success_rate=None,
        recovery_opportunity_count=0,
        recovery_success_evidence_count=0,
        correction_quality=None,
        correction_evidence_count=0,
        post_friction_verification_rate=None,
    )
    axis = {item.key: item for item in assess_growth(inputs).axes}["adaptive_recovery"]
    assert axis.score is None
    assert {
        code
        for component in axis.components
        for code in component.observation.reason_codes
    } == {
        "recovery_opportunity_unavailable",
        "correction_observed_unavailable",
        "post_friction_verification_unavailable",
    }


def test_raw_volume_and_ecosystem_counts_cannot_raise_score() -> None:
    base = _credible_inputs()
    low = assess_growth(
        replace(
            base,
            total_token_volume=1,
            total_files_modified=2,
            distinct_tool_count=1,
            distinct_model_count=1,
            total_subagent_invocations=1,
            commit_rate=0.0,
        )
    )
    inflated = assess_growth(
        replace(
            base,
            total_token_volume=99_000_000,
            total_files_modified=999,
            distinct_tool_count=9,
            distinct_model_count=12,
            total_subagent_invocations=500,
            commit_rate=1.0,
        )
    )
    assert inflated.mirror_score == low.mirror_score
    assert [axis.score for axis in inflated.axes] == [axis.score for axis in low.axes]


def test_unverified_subagent_calls_do_not_raise_agentic_or_execution_scores() -> None:
    base = replace(
        _credible_inputs(),
        delegation_success_rate=None,
        delegation_evidence_count=0,
        advanced_feature_outcome_rate=None,
        total_subagent_invocations=0,
    )
    noisy = replace(base, total_subagent_invocations=200)
    base_axes = {axis.key: axis.score for axis in assess_growth(base).axes}
    noisy_axes = {axis.key: axis.score for axis in assess_growth(noisy).axes}
    assert noisy_axes["execution_driving"] == base_axes["execution_driving"]
    assert noisy_axes["agentic_system"] == base_axes["agentic_system"]


def test_files_per_session_saturates() -> None:
    base = _credible_inputs()
    saturated = assess_growth(replace(base, files_per_session=3.0))
    inflated = assess_growth(replace(base, files_per_session=300.0))
    assert inflated.mirror_score == saturated.mirror_score


def test_cross_policy_snapshots_fail_closed_without_fake_delta() -> None:
    comparison = compare_snapshot_sources(
        SnapshotSource(mirror_score=70, assessment_policy_version="1.0"),
        SnapshotSource(mirror_score=90, assessment_policy_version="2.0"),
    )
    assert comparison.policy_comparable is False
    assert comparison.incomparable_reason == "assessment_policy_mismatch"
    assert comparison.score.delta == 0.0
    assert comparison.axis_deltas == []


def test_missing_sixth_axis_is_not_treated_as_current_schema() -> None:
    five_axes = {
        "collaboration_framing": 60.0,
        "execution_driving": 60.0,
        "implementation_depth": 60.0,
        "delivery_closure": 60.0,
        "adaptive_recovery": 60.0,
    }
    comparison = compare_snapshot_sources(
        SnapshotSource(axis_scores=five_axes),
        SnapshotSource(axis_scores={**five_axes, "agentic_system": 70.0}),
    )
    assert comparison.axis_deltas == []
