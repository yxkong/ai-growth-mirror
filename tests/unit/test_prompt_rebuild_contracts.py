"""Prompt rebuild contract coverage for AI Growth Mirror."""

from ai_growth_mirror.assets.prompts import build_prompt_environment
from ai_growth_mirror.infra.extractors.llm import _session_read_system_prompt
from ai_growth_mirror.infra.extractors.prompt_quality import _prompt_lens_system_prompt
from ai_growth_mirror.infra.llm.coach import _render_template


def test_session_read_prompt_uses_new_contract_language():
    env = build_prompt_environment()
    rendered = _session_read_system_prompt(env, report_language="en")
    assert '"work_summary"' in rendered
    assert '"work_intent_mix"' in rendered
    assert '"resistance_signals"' in rendered
    assert '"momentum_signals"' in rendered
    assert "underlying_goal" not in rendered
    assert "friction_points" not in rendered


def test_prompt_lens_prompt_uses_new_bundle_name_and_focus():
    env = build_prompt_environment()
    rendered = _prompt_lens_system_prompt(env, report_language="en")
    assert '"dimension_scores"' in rendered
    assert '"takeaways"' in rendered
    assert "prompt lens" in rendered.lower()
    assert "guidance lens" not in rendered.lower()


def test_growth_coach_prompt_avoids_legacy_six_dimension_frame():
    rendered = _render_template(
        "system.md.j2",
        {
            "language": "en",
            "priority_keys": ["delivery_closure"],
        },
    )
    assert "delegation" not in rendered.lower()
    assert "breadth" not in rendered.lower()
    assert "motivational filler" in rendered.lower()
