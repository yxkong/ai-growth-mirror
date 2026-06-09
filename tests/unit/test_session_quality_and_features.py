"""Targeted tests for shared advanced-feature enrichment, quality gating,
and the has_data signaling that drives the report's "no-fabrication" rule.

These cover the plan items 2.1 (indexed prompts not penalized), 2.3 (no
fabrication when data is missing), 3.1 (quality gate), and 4.1 (advanced
features extracted uniformly across readers).
"""

from __future__ import annotations

from ai_growth_mirror.domain.session.heuristics import (
    ADVANCED_FEATURE_KEYS,
    classify_session_quality,
    enrich_advanced_features,
    enrich_agentic_signals,
    enrich_task_contract_signals,
    is_validation_command,
    is_indexed_prompt_session,
    passes_quality_gate,
)
from ai_growth_mirror.domain.session.model import SessionRecord


def _bare_session(**overrides) -> SessionRecord:
    base = SessionRecord(
        session_id="t",
        tool_name="demo",
        start_time="2026-05-17T10:00:00+00:00",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


# ---------------------------------------------------------------------------
# enrich_advanced_features — derives features uniformly from existing fields
# ---------------------------------------------------------------------------


def test_enrich_advanced_features_from_subagent_count():
    session = _bare_session(subagent_invocation_count=2)
    enrich_advanced_features(session)
    assert "subagent_dispatch" in session.advanced_features


def test_enrich_advanced_features_from_uses_subagent_flag():
    session = _bare_session(uses_subagent=True)
    enrich_advanced_features(session)
    assert "subagent_dispatch" in session.advanced_features


def test_enrich_advanced_features_skill_invocation_from_count():
    session = _bare_session(skill_invocation_count=1)
    enrich_advanced_features(session)
    assert "skill_invocation" in session.advanced_features


def test_enrich_advanced_features_skill_invocation_from_unique_skills():
    session = _bare_session(unique_skills_used=["delivery-workflow"])
    enrich_advanced_features(session)
    assert "skill_invocation" in session.advanced_features


def test_enrich_advanced_features_mcp():
    session = _bare_session(uses_mcp=True)
    enrich_advanced_features(session)
    assert "mcp_usage" in session.advanced_features


def test_enrich_advanced_features_multi_model():
    session = _bare_session(models_used=["gpt-5", "claude-4-sonnet"])
    enrich_advanced_features(session)
    assert "multi_model" in session.advanced_features


def test_enrich_advanced_features_plan_mode_via_todowrite():
    session = _bare_session(tool_counts={"TodoWrite": 3})
    enrich_advanced_features(session)
    assert "plan_mode" in session.advanced_features


def test_enrich_advanced_features_plan_mode_via_text():
    session = _bare_session(first_prompt="Plan mode is active.\nWrite tests.")
    enrich_advanced_features(session)
    assert "plan_mode" in session.advanced_features


def test_enrich_advanced_features_ask_mode_via_text():
    session = _bare_session(first_prompt="Ask mode is active. Tell me.")
    enrich_advanced_features(session)
    assert "ask_mode" in session.advanced_features


def test_enrich_advanced_features_idempotent_and_additive():
    session = _bare_session(uses_mcp=True, advanced_features=["plan_mode"])
    enrich_advanced_features(session)
    enrich_advanced_features(session)
    # Both reader-detected (plan_mode) and derived (mcp_usage) survive a
    # second pass; no duplicates because we project through the canonical set.
    assert sorted(session.advanced_features) == sorted(
        {"plan_mode", "mcp_usage"}
    )


def test_enrich_advanced_features_canonical_ordering():
    session = _bare_session(
        uses_mcp=True,
        skill_invocation_count=1,
        models_used=["a", "b"],
        subagent_invocation_count=1,
    )
    enrich_advanced_features(session)
    # ADVANCED_FEATURE_KEYS is the canonical render order; ensure the
    # populated list respects it so report snapshots stay stable.
    indices = [ADVANCED_FEATURE_KEYS.index(k) for k in session.advanced_features]
    assert indices == sorted(indices)


def test_enrich_advanced_features_empty_session_stays_empty():
    session = _bare_session()
    enrich_advanced_features(session)
    assert session.advanced_features == []


# ---------------------------------------------------------------------------
# is_indexed_prompt_session — anchor for short, skill-driven sessions
# ---------------------------------------------------------------------------


def test_indexed_prompt_via_skill_invocation():
    assert is_indexed_prompt_session(_bare_session(skill_invocation_count=1))


def test_indexed_prompt_via_unique_skills():
    assert is_indexed_prompt_session(_bare_session(unique_skills_used=["delivery"]))


def test_indexed_prompt_via_slash_command():
    assert is_indexed_prompt_session(_bare_session(slash_commands=["/delivery-workflow"]))


def test_indexed_prompt_negative():
    assert not is_indexed_prompt_session(_bare_session())


# ---------------------------------------------------------------------------
# classify_session_quality — indexed prompt is never `low`
# ---------------------------------------------------------------------------


def test_quality_low_when_truly_empty():
    s = _bare_session(user_message_count=1)
    assert classify_session_quality(s) == "low"


def test_quality_indexed_single_message_is_at_least_medium():
    """User's core complaint: `/delivery-workflow` once + AI long output
    must NOT be classified as low."""
    s = _bare_session(
        user_message_count=1,
        slash_commands=["/delivery-workflow"],
    )
    assert classify_session_quality(s) == "medium"


def test_quality_skill_invocation_is_at_least_medium():
    s = _bare_session(user_message_count=1, skill_invocation_count=2)
    assert classify_session_quality(s) == "medium"


def test_quality_high_when_outcome_evidenced():
    s = _bare_session(
        user_message_count=4,
        tool_counts={"bash": 5},
        files_modified=3,
        has_test_commands=True,
    )
    assert classify_session_quality(s) == "high"


def test_build_command_counts_as_validation_command():
    s = _bare_session(
        user_message_count=1,
        tool_counts={"edit": 1, "npm run build": 1},
        files_modified=1,
    )
    enrich_agentic_signals(s)
    assert s.has_verification_behavior is True
    assert s.has_test_commands is True


def test_validation_command_uses_keyword_boundaries_not_full_allowlist():
    assert is_validation_command("pwsh -NoProfile -Command ./scripts/run_all.ps1")
    assert is_validation_command("mvn -DskipTests compile")
    assert is_validation_command("python tools/custom_verify.py")
    assert not is_validation_command("show latest report")
    assert not is_validation_command("git checkout main")
    assert not is_validation_command("cat build.log")
    assert not is_validation_command("grep 'test' file.py")
    assert not is_validation_command("rg 'test' .")
    assert not is_validation_command("git diff --stat")


def test_effective_contract_from_skill_read_not_missing_user_acceptance():
    s = _bare_session(
        first_prompt="优化报告体验",
        assistant_messages=["好的，已加载 skills。我们的验收标准是无报错。"],
        user_message_count=1,
        skill_invocation_count=1,
        unique_skills_used=["ai-growth-mirror-dev"],
        tool_counts={"read": 3},
    )
    enrich_task_contract_signals(s)
    assert "skill_read" in s.task_contract_sources
    assert s.pre_execution_contract_present is True
    assert s.acceptance_contract_source == "skill_read"


def test_late_user_correction_is_separate_from_missing_contract():
    s = _bare_session(
        first_prompt="优化这个模块",
        top_user_messages=["优化这个模块", "你为啥要改规范？按照规范执行"],
        user_message_count=2,
        files_modified=1,
    )
    enrich_task_contract_signals(s)
    assert s.late_contract_correction is True
    assert "late_user" in s.task_contract_sources


def test_quality_medium_when_signals_but_no_outcome():
    s = _bare_session(user_message_count=3, tool_counts={"read": 2})
    assert classify_session_quality(s) == "medium"


def test_passes_quality_gate_filters_low():
    low = _bare_session(user_message_count=1)
    assert classify_session_quality(low) == "low"
    # Default min_quality=medium should filter it out
    assert passes_quality_gate(low, "medium") is False
    assert low.quality_tag == "low"


def test_passes_quality_gate_admits_indexed_at_medium():
    indexed = _bare_session(user_message_count=1, slash_commands=["/skill"])
    assert passes_quality_gate(indexed, "medium") is True
    assert indexed.quality_tag == "medium"


def test_passes_quality_gate_low_tier_admits_everything():
    low = _bare_session(user_message_count=1)
    assert passes_quality_gate(low, "low") is True


# ---------------------------------------------------------------------------
# has_data on radar axes — plan 2.3 no-fabrication rule
# ---------------------------------------------------------------------------


def test_radar_axes_no_data_for_empty_profile():
    """An empty profile must not pretend axes have evidence."""
    from ai_growth_mirror.domain.growth.scorer import _build_radar_axes
    from ai_growth_mirror.domain.growth.model import GrowthProfile

    empty = GrowthProfile(tool_name="all")
    axes = _build_radar_axes(empty)
    # All six axes should report no data so the UI shows "—" not "0.0".
    assert all(not axis.has_data for axis in axes)


def test_radar_axes_has_data_when_outcome_signals_present():
    from ai_growth_mirror.domain.growth.scorer import _build_radar_axes
    from ai_growth_mirror.domain.growth.model import GrowthProfile

    profile = GrowthProfile(
        tool_name="all",
        session_count=5,
        pq_sessions_evaluated=3,
        agentic_sub_scores={
            "collaboration_framing": 62.0,
            "execution_driving": 58.0,
            "implementation_depth": 55.0,
            "delivery_closure": 60.0,
            "adaptive_recovery": 45.0,
            "agentic_system": 50.0,
        },
        avg_autonomous_chain_length=4.2,
        top_tools=[("bash", 12)],
    )
    axes = _build_radar_axes(profile)
    assert all(axis.has_data for axis in axes)


def test_radar_axes_collaboration_framing_needs_pq_evaluation():
    """`collaboration_framing` is PQ-driven, so it stays "no data" when no PQ ran,
    even if outcome signals exist."""
    from ai_growth_mirror.domain.growth.scorer import _build_radar_axes
    from ai_growth_mirror.domain.growth.model import GrowthProfile

    profile = GrowthProfile(
        tool_name="all",
        session_count=5,
        pq_sessions_evaluated=0,
        avg_autonomous_chain_length=4.0,
        top_tools=[("bash", 5)],
    )
    axes = _build_radar_axes(profile)
    by_key = {axis.key: axis for axis in axes}
    assert by_key["collaboration_framing"].has_data is False
    # Outcome-driven axes light up since chain depth + tools exist
    assert by_key["execution_driving"].has_data is True
