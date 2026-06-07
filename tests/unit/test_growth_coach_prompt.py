from ai_growth_mirror.infra.llm.coach import _render_template


def _coach_context() -> dict:
    return {
        "language": "en",
        "growth_level": "L3",
        "mirror_score": 68,
        "session_count": 12,
        "active_days": 7,
        "avg_chain": 4.2,
        "heavy_session_count": 5,
        "tool_display_name": "Codex CLI",
        "period_label": "2026-05-01 -> 2026-05-31",
        "capability_scores": {
            "collaboration_framing": 74.0,
            "execution_driving": 69.0,
            "implementation_depth": 63.0,
            "delivery_closure": 55.0,
            "adaptive_recovery": 58.0,
            "agentic_system": 50.0,
        },
        "outcome_counts": {"fully_achieved": 5, "mostly_achieved": 3},
        "top_friction": [("scope_drift", 4), ("missing_context", 2)],
        "pq_sessions_evaluated": 6,
        "weakest_pq_dim": "correction_quality",
        "weakest_pq_score": 48.0,
        "pq_avg_efficiency": 61.0,
        "constraint_rate_pct": 67,
        "context_rate_pct": 58,
        "mcp_session_rate_pct": 25,
        "subagent_session_count": 3,
        "skill_authored_count": 2,
        "hook_modified_session_count": 1,
        "mcp_authored_session_count": 1,
        "priority_keys": ["delivery_closure", "prompt:correction_quality", "adaptive_recovery"],
    }


def test_growth_coach_system_prompt_uses_current_priority_contract():
    rendered = _render_template("system.md.j2", _coach_context())
    assert "copied exactly from the provided `priority_keys`" in rendered
    assert "motivational filler" in rendered
    assert "delegation|verification|breadth|authorship|outcome|workflow" not in rendered
    assert "## Output language" in rendered
    assert "natural-language content" in rendered.lower()
    assert '"friction_synthesis"' in rendered


def test_growth_coach_system_prompt_zh_output_language():
    ctx = {**_coach_context(), "language": "zh"}
    rendered = _render_template("system.md.j2", ctx)
    assert "Simplified Chinese" in rendered or "简体中文" in rendered


def test_growth_coach_user_prompt_uses_five_axes_and_heavy_sessions():
    rendered = _render_template("user.md.j2", _coach_context())
    assert "Six-axis scores" in rendered
    assert "- Average autonomous chain: 4.2" in rendered
    assert "- Heavy sessions: 5" in rendered
    assert "- execution_driving: 69.0" in rendered
    assert "- skill_authored_count: 2" in rendered
    assert "Delegation depth" not in rendered
