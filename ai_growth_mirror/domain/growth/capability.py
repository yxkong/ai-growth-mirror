"""Pure capability score derivation from growth profile aggregates."""

from __future__ import annotations

from .model import GrowthProfile


def compute_capability_scores(stats: GrowthProfile) -> dict[str, float]:
    scores = stats.agentic_sub_scores or {}
    if scores:
        return {
            "collaboration_framing": min(round(scores.get("collaboration_framing", 0.0), 1), 100.0),
            "execution_driving": min(round(scores.get("execution_driving", 0.0), 1), 100.0),
            "implementation_depth": min(round(scores.get("implementation_depth", 0.0), 1), 100.0),
            "delivery_closure": min(round(scores.get("delivery_closure", 0.0), 1), 100.0),
            "adaptive_recovery": min(round(scores.get("adaptive_recovery", 0.0), 1), 100.0),
            "agentic_system": min(round(scores.get("agentic_system", 0.0), 1), 100.0),
        }
    if stats.radar_axes:
        return {axis.key: axis.score for axis in stats.radar_axes}
    return {
        "collaboration_framing": min(
            (
                (stats.constraint_prompt_rate if hasattr(stats, "constraint_prompt_rate") else 0.0) * 50
                + (stats.code_context_rate or 0.0) * 50
            ),
            100.0,
        ),
        "execution_driving": min(
            (
                (stats.avg_autonomous_chain_length or 0.0) / 8.0 * 60
                + min((stats.heavy_session_rate or 0.0) * 100, 100.0) * 0.4
            ),
            100.0,
        ),
        "implementation_depth": min(
            (
                min((stats.total_files_modified / max(stats.session_count, 1)) * 35, 100.0) * 0.45
                + min((stats.total_token_volume / 5_000_000) * 100, 100.0) * 0.20
                + (stats.code_verification_rate or 0.0) * 100 * 0.35
            ),
            100.0,
        ),
        "delivery_closure": min(
            (
                (getattr(stats, "fully_achieved_rate", 0.0) or 0.0) * 100 * 0.50
                + (stats.verification_behavior_rate or 0.0) * 100 * 0.35
                + (stats.test_run_rate or 0.0) * 100 * 0.15
            ),
            100.0,
        ),
        "adaptive_recovery": min(
            (
                (stats.verification_behavior_rate or 0.0) * 100 * 0.35
                + (getattr(stats, "fully_achieved_rate", 0.0) or 0.0) * 100 * 0.35
                + min((stats.workflow_structured_session_count / max(stats.session_count, 1)) * 100, 100.0) * 0.30
            ),
            100.0,
        ),
        "agentic_system": 0.0,
    }
