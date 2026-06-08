from ai_growth_mirror.domain.growth.model import AgentAssetStats
from ai_growth_mirror.domain.growth.scorer import (
    _apply_asset_floor,
    _compute_growth_level,
    aggregate,
    format_growth_level_score_range,
    growth_level_from_score,
)
from ai_growth_mirror.domain.signals.model import SessionRead
from tests.conftest import make_session


def test_aggregate_empty():
    st = aggregate([], [], tool_name="demo")
    assert st.session_count == 0


def test_aggregate_single_session():
    s = make_session(session_id="1", tool="t1")
    st = aggregate([s], [], tool_name="t1")
    assert st.session_count == 1
    assert st.total_user_messages == s.user_message_count


def test_execution_driving_rewards_reusable_asset_authoring():
    level, score, subs = _compute_growth_level(
        avg_chain=10.0,
        verification_rate=0.3,
        heavy_session_rate=0.2,
        heavy_session_count=8,
        total_token_volume=5_000_000,
        mcp_session_rate=0.0,
        subagent_session_rate=0.0,
        total_subagent_invocations=0,
        web_session_rate=0.0,
        tool_build_rate=0.4,
        unique_skill_count=4,
        tier_diversity=4,
        distinct_tool_count=1,
        distinct_model_count=1,
        workflow_build_substantial_count=0,
        workflow_build_moderate_count=0,
        ai_authoring_distinct_categories=0,
        fully_achieved_rate=0.5,
        workflow_structured_count=8,
        session_count=40,
        skill_authored_count=0,
        hook_modified_session_count=0,
        mcp_authored_session_count=0,
        assetized_session_rate=0.4,
        direction_clarity_rate=0.6,
        context_grounding_rate=0.7,
        goal_locking_speed=80.0,
        active_clarification_rate=0.5,
        skill_usage_session_rate=0.5,
        workflow_fingerprint_session_rate=0.5,
        workflow_reuse_depth=4,
        advanced_feature_ratio=0.5,
        prompt_dimensions={
            "request_specificity": 68.0,
            "context_provision": 70.0,
            "scope_management": 65.0,
            "correction_quality": 60.0,
        },
        test_run_rate=0.3,
        code_verification_rate=0.28,
        total_files_modified=24,
    )
    assert level in {"L2", "L3", "L4", "L5"}
    assert score > 0
    assert subs["execution_driving"] > 0


def test_apply_asset_floor_rewards_smaller_skill_libraries():
    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats(skill_files_count=15, prompt_files_count=8, rule_files_count=5, total_asset_files=28, roots_scanned=1)
    _apply_asset_floor(stats)
    assert stats.workflow_build_moderate_count >= 2
    assert stats.workflow_build_substantial_count >= 1


def test_apply_asset_floor_skips_when_no_asset_data():
    """No-asset profile: floor must not synthesize evidence."""
    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats()  # has_data == False
    _apply_asset_floor(stats)
    assert stats.workflow_build_moderate_count == 0
    assert stats.workflow_build_substantial_count == 0


def test_apply_asset_floor_substantial_kicks_in_at_30_skills():
    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats(
        skill_files_count=35,
        rule_files_count=8,
        total_asset_files=43,
        roots_scanned=1,
    )
    _apply_asset_floor(stats)
    assert stats.workflow_build_substantial_count >= 3


def test_asset_maturity_bonus_caps_at_three():
    """Bonus saturates so a huge asset library can't single-handedly push to L5."""
    from ai_growth_mirror.domain.growth.scorer import _asset_maturity_bonus

    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats(
        skill_files_count=120,
        prompt_files_count=80,
        rule_files_count=50,
        total_asset_files=250,
        roots_scanned=2,
    )
    assert _asset_maturity_bonus(stats) == 3.0


def test_asset_maturity_bonus_zero_when_no_assets():
    from ai_growth_mirror.domain.growth.scorer import _asset_maturity_bonus

    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats()
    assert _asset_maturity_bonus(stats) == 0.0


def test_asset_maturity_bonus_partial_credits_for_skills_and_rules():
    from ai_growth_mirror.domain.growth.scorer import _asset_maturity_bonus

    stats = aggregate([], [], tool_name="demo")
    stats.agent_asset = AgentAssetStats(
        skill_files_count=12,
        rule_files_count=6,
        total_asset_files=18,
        roots_scanned=1,
    )
    # 1.5 from skill+rule combo, no prompt bonus, no >=30 skill bonus
    assert _asset_maturity_bonus(stats) == 1.5


def test_agentic_system_inventory_alone_is_weak_evidence():
    sessions = [make_session(session_id=f"s{i}") for i in range(20)]
    stats = aggregate(
        sessions,
        [],
        tool_name="demo",
        agent_asset=AgentAssetStats(
            skill_files_count=120,
            prompt_files_count=80,
            rule_files_count=50,
            total_asset_files=250,
            roots_scanned=1,
            local_method_frameworks=["delivery-workflow", "ai-development-governance"],
        ),
    )

    assert stats.skill_usage_session_rate == 0.0
    assert stats.workflow_fingerprint_session_rate == 0.0
    assert stats.local_method_framework_session_rate == 0.0
    assert stats.agentic_system_score < 20
    assert stats.growth_level != "L5"


def test_agentic_system_rewards_real_repeated_skill_and_workflow_use():
    sessions = []
    for i in range(24):
        s = make_session(session_id=f"s{i}")
        s.unique_skills_used = ["implementation-workflow", "quality-gate", "git-workflow", "test-framework"]
        s.slash_commands = ["/spec-create"]
        s.advanced_features = ["skill_invocation", "subagent_dispatch"]
        s.skill_invocation_count = 2
        s.uses_subagent = True
        s.subagent_invocation_count = 2
        s.uses_mcp = i % 3 == 0
        s.tool_counts = {"read": 8, "edit": 4, "shell_command": 4}
        s.tool_tier_counts = {"read": 8, "write": 4, "execute": 4}
        s.autonomous_chain_lengths = [18]
        s.files_modified = 4
        s.languages = {"Python": 2}
        s.has_verification_behavior = True
        s.has_test_commands = i % 2 == 0
        s.skill_files_authored = 1 if i % 6 == 0 else 0
        sessions.append(s)

    reads = [
        SessionRead(
            session_id=session.session_id,
            work_style="plan_driven",
            delivery_outcome="mostly_achieved",
            capability_focus="workflow_builder",
            capability_depth="substantial",
        )
        for session in sessions
    ]
    stats = aggregate(sessions, reads, tool_name="demo")

    assert stats.skill_usage_session_rate == 1.0
    assert stats.workflow_fingerprint_session_rate == 1.0
    assert stats.workflow_reuse_depth >= 3
    assert stats.asset_authoring_session_rate > 0
    assert stats.agentic_system_score >= 75


def test_agentic_system_counts_configured_local_methods_when_used():
    sessions = []
    for i in range(10):
        s = make_session(session_id=f"s{i}")
        s.unique_skills_used = ["delivery-workflow", "skill-engineering"]
        s.slash_commands = ["/delivery-workflow"]
        s.skill_invocation_count = 2
        s.advanced_features = ["skill_invocation"]
        sessions.append(s)

    stats = aggregate(
        sessions,
        [],
        tool_name="demo",
        agent_asset=AgentAssetStats(
            local_method_frameworks=[
                "delivery-workflow",
                "skill-engineering",
                "unused-private-method",
            ]
        ),
    )

    assert stats.public_framework_session_rate == 0.0
    assert stats.local_method_framework_session_rate == 1.0
    assert stats.workflow_fingerprint_session_rate == 1.0
    assert stats.top_local_method_frameworks[:2] == [
        ("delivery-workflow", 10),
        ("skill-engineering", 10),
    ]
    assert stats.workflow_reuse_depth >= 2


def test_growth_level_boundaries_match_canonical_ranges():
    assert growth_level_from_score(0) == "L1"
    assert growth_level_from_score(37) == "L1"
    assert growth_level_from_score(38) == "L2"
    assert growth_level_from_score(55) == "L2"
    assert growth_level_from_score(56) == "L3"
    assert growth_level_from_score(74) == "L3"
    assert growth_level_from_score(75) == "L4"
    assert growth_level_from_score(89) == "L4"
    assert growth_level_from_score(90) == "L5"
    assert format_growth_level_score_range("L3") == "56-74"
    assert format_growth_level_score_range("L4") == "75-89"


def test_goal_locking_speed_excludes_readonly_sessions():
    from ai_growth_mirror.domain.session.model import SessionRecord
    from ai_growth_mirror.domain.signals.model import SessionRead

    s1 = make_session(session_id="s1")
    s1.turns_until_first_file_write = 3
    s1.files_modified = 1

    # s2 is a read-only session
    s2 = make_session(session_id="s2")
    s2.turns_until_first_file_write = None
    s2.files_modified = 0

    st = aggregate([s1, s2], [], tool_name="demo")
    # Only s1 participates in locking speed, so it should be exactly 100.0 (turns_until_first_file_write = 3)
    assert st.goal_locking_speed == 100.0


def test_goal_locking_speed_rewards_active_clarification():
    from ai_growth_mirror.domain.session.model import SessionRecord
    from ai_growth_mirror.domain.signals.model import SessionRead

    s1 = make_session(session_id="s1")
    s1.turns_until_first_file_write = 4
    s1.files_modified = 1

    s2 = make_session(session_id="s2")
    s2.turns_until_first_file_write = None
    s2.files_modified = 0

    r1 = SessionRead(
        session_id="s1",
        tool_name="claude_code",
        delivery_outcome="fully_achieved",
        work_intent_mix={"feature": 1.0},
        confidence="high",
        active_clarification=True,
    )

    st = aggregate([s1, s2], [r1], tool_name="demo")
    # Since r1 active_clarification is True, s1 turns (4) is treated as max(1, 4-1) = 3
    # A turn count of 3 yields 100.0 points. s2 is read-only and excluded.
    assert st.goal_locking_speed == 100.0

