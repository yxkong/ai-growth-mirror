from ai_growth_mirror.domain.growth.coaching import parse_coaching_payload
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
    assert '"axis_diagnosis"' in rendered
    assert '"training_plan"' in rendered
    assert '"framing_evidence"' in rendered
    assert '"friction_synthesis"' in rendered
    assert "prompt_coach" not in rendered
    assert "prompt-improvement" not in rendered
    assert "prompt friction" not in rendered


def test_growth_coach_system_prompt_zh_uses_six_axis_product_language():
    ctx = {**_coach_context(), "language": "zh"}
    rendered = _render_template("system.md.j2", ctx)
    assert "Simplified Chinese" in rendered or "简体中文" in rendered
    assert "协作框定、协作驱动、实现下潜、交付收口、恢复推进、Agentic 系统化" in rendered
    assert "协作输入、任务框定、目标边界、输入材料、验收方式" in rendered


def test_growth_coach_user_prompt_uses_six_axes_and_heavy_sessions():
    rendered = _render_template("user.md.j2", _coach_context())
    assert "Six-axis scores" in rendered
    assert "- Average autonomous chain: 4.2" in rendered
    assert "- Heavy sessions: 5" in rendered
    assert "- execution_driving: 69.0" in rendered
    assert "- skill_authored_count: 2" in rendered
    assert "Delegation depth" not in rendered


def test_parse_coaching_payload_reads_llm_fields_directly():
    content = parse_coaching_payload(
        {
            "axis_diagnosis": [
                {
                    "axis_key": "collaboration_framing",
                    "label": "协作框定",
                    "explanation": "协作框定反复迟到",
                    "confidence": 72,
                    "evidence_refs": ["协作框定样本"],
                    "next_action": "固定协作框定骨架",
                }
            ],
            "training_plan": {
                "headline": "协作框定需要稳定",
                "priorities": [
                    {
                        "key": "collaboration_framing",
                        "title": "协作框定训练",
                        "why": "先补协作框定",
                        "week_1_actions": ["协作框定前置"],
                        "week_2_actions": ["复盘协作框定"],
                        "action_contract": "每次任务先写目标与边界",
                        "evidence_refs": ["pq_deficit.missing-context"],
                    }
                ],
            },
            "framing_evidence": {
                "headline": "优化协作框定",
                "evidence_summary": "协作框定反复迟到",
                "takeaways": [
                    {
                        "label": "协作框定",
                        "message": "协作框定不足",
                        "action": "补齐协作框定",
                    }
                ],
                "friction_synthesis": [
                    {
                        "label": "协作框定摩擦",
                        "explanation": "协作框定导致返工",
                        "next_action": "固定协作框定骨架",
                        "evidence_refs": ["协作框定样本"],
                    }
                ],
            },
            "share_lines": ["协作框定系统性需要提升", "协作框定训练要稳定"],
        }
    )

    assert content.growth_headline == "协作框定需要稳定"
    assert content.priorities[0].title == "协作框定训练"
    assert content.priorities[0].why == "先补协作框定"
    assert content.priorities[0].week_1_actions == ["协作框定前置"]
    assert content.priorities[0].week_2_actions == ["复盘协作框定"]
    assert content.priorities[0].action_contract == "每次任务先写目标与边界"
    assert content.priorities[0].evidence_refs == ["pq_deficit.missing-context"]
    assert content.axis_diagnosis[0].axis_key == "collaboration_framing"
    assert content.axis_diagnosis[0].label == "协作框定"
    assert content.axis_diagnosis[0].next_action == "固定协作框定骨架"
    assert content.framing_evidence_headline == "优化协作框定"
    assert content.framing_evidence_summary == "协作框定反复迟到"
    assert content.framing_evidence_takeaways[0].label == "协作框定"
    assert content.friction_synthesis[0].label == "协作框定摩擦"
    assert content.share_lines == ["协作框定系统性需要提升", "协作框定训练要稳定"]


def test_parse_coaching_payload_keeps_empty_when_schema_fields_missing():
    content = parse_coaching_payload({})

    assert content.growth_headline == ""
    assert content.priorities == []
    assert content.axis_diagnosis == []
    assert content.framing_evidence_headline == ""
    assert content.framing_evidence_summary == ""
    assert content.framing_evidence_takeaways == []
    assert content.friction_synthesis == []
    assert content.share_lines == []
