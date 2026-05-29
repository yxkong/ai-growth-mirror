"""All LLM prompt bundles enforce report output locale."""

from ai_growth_mirror.assets.prompts import build_prompt_environment
from ai_growth_mirror.infra.extractors.llm import _session_read_system_prompt
from ai_growth_mirror.infra.extractors.prompt_quality import _prompt_lens_system_prompt


def test_session_read_system_prompt_locale_aware():
    env = build_prompt_environment()
    zh = _session_read_system_prompt(env, report_language="zh")
    en = _session_read_system_prompt(env, report_language="en")
    assert "简体中文" in zh
    assert "natural-language content" in zh.lower()
    assert "natural-language content" in en.lower()
    assert zh != en


def test_prompt_lens_system_prompt_includes_output_language():
    env = build_prompt_environment()
    zh = _prompt_lens_system_prompt(env, report_language="zh")
    assert "## Output language" in zh
    assert "简体中文" in zh
