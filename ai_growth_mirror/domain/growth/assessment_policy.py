"""Canonical scoring policy for the six-axis growth assessment.

This module owns semantic constants. Consumers must import these values or use
``AssessmentResult``; they must not copy the policy into another module.
"""

from __future__ import annotations

ASSESSMENT_POLICY_VERSION = "2.0"

AXIS_WEIGHTS: dict[str, float] = {
    "collaboration_framing": 0.14,
    "execution_driving": 0.25,
    "implementation_depth": 0.19,
    "delivery_closure": 0.19,
    "adaptive_recovery": 0.10,
    "agentic_system": 0.13,
}

LEVEL_MIN_SCORES: dict[str, int] = {
    "L1": 0,
    "L2": 38,
    "L3": 56,
    "L4": 75,
    "L5": 90,
}

COMPONENT_WEIGHTS: dict[str, dict[str, float]] = {
    "collaboration_framing": {
        "effective_contract": 0.40,
        "context_grounding": 0.25,
        "goal_locking": 0.20,
        "active_clarification": 0.15,
    },
    "execution_driving": {
        "autonomous_chain": 0.35,
        "structured_workflow": 0.30,
        "verified_continuation": 0.20,
        "delegation_success": 0.15,
    },
    "implementation_depth": {
        "implementation_sessions": 0.30,
        "code_verification": 0.35,
        "fully_achieved": 0.20,
        "files_per_session": 0.15,
    },
    "delivery_closure": {
        "fully_achieved": 0.40,
        "verification": 0.25,
        "tests": 0.15,
        "contract_compliance": 0.20,
    },
    "adaptive_recovery": {
        "recovery_success": 0.50,
        "correction_quality": 0.25,
        "post_friction_verification": 0.25,
    },
    "agentic_system": {
        "skill_outcome": 0.18,
        "workflow_outcome": 0.18,
        "structured_outcome": 0.14,
        "workflow_reuse": 0.15,
        "asset_authoring": 0.12,
        "assetized_outcome": 0.10,
        "advanced_feature_outcome": 0.08,
        "method_saturation": 0.05,
    },
}

MIN_AXIS_COVERAGE = 0.25
