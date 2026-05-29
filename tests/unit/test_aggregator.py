from ai_growth_mirror.domain.growth.scorer import _compute_growth_level, aggregate
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
        constraint_prompt_rate=0.6,
        code_context_rate=0.7,
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
