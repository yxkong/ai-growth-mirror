from pathlib import Path

import yaml

from ai_growth_mirror.config import (
    GrowthMirrorConfig,
    default_cache_dir,
    default_config_path,
    provider_default_base_url,
    provider_default_model,
    resolve_config_path,
    resolve_provider_api_key,
)
from ai_growth_mirror.product import PRODUCT_RUNTIME_DIRNAME
from ai_growth_mirror.assets.prompts import get_prompt_template, prompt_asset_scope
from tests.conftest import run_workspace


def test_default_cache_dir_is_project_local(monkeypatch, tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "cache").resolve()
    monkeypatch.chdir(workspace_tmp)
    expected = (workspace_tmp / PRODUCT_RUNTIME_DIRNAME / "cache").resolve()
    assert default_cache_dir().resolve() == expected
    cfg = GrowthMirrorConfig()
    assert cfg.cache.dir.resolve() == expected


def test_load_config_missing_returns_default(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "missing_config")
    c = GrowthMirrorConfig.load(workspace_tmp / "nope.yaml")
    assert isinstance(c, GrowthMirrorConfig)
    assert c.llm.provider == "deepseek"
    assert c.llm.model == "deepseek-v4-pro"


def test_resolve_config_path_prefers_local_config_yaml(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "local_config")
    local = workspace_tmp / "config.yaml"
    local.write_text("llm:\n  provider: glm\n", encoding="utf-8")

    assert resolve_config_path(cwd=workspace_tmp) == local
    assert default_config_path(cwd=workspace_tmp) == local


def test_resolve_config_path_falls_back_to_home_default(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "home_fallback")

    from ai_growth_mirror.config import DEFAULT_CONFIG_PATH

    assert resolve_config_path(cwd=workspace_tmp) == DEFAULT_CONFIG_PATH


def test_load_config_without_explicit_path_uses_local_config_yaml(monkeypatch, tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "cwd_config")
    (workspace_tmp / "config.yaml").write_text(
        yaml.safe_dump({"llm": {"provider": "openai"}}),
        encoding="utf-8",
    )

    monkeypatch.chdir(workspace_tmp)
    cfg = GrowthMirrorConfig.load()
    assert cfg.llm.provider == "openai"


def test_load_config_roundtrip(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "roundtrip")
    p = workspace_tmp / "c.yaml"
    p.write_text(
        yaml.safe_dump(
            {"llm": {"provider": "openai"}, "cache": {"dir": str(workspace_tmp / "cache")}}
        ),
        encoding="utf-8",
    )
    c = GrowthMirrorConfig.load(p)
    assert c.llm.provider == "openai"
    assert c.cache.dir == workspace_tmp / "cache"
    assert c.llm.model == provider_default_model("openai")
    assert c.llm.base_url == provider_default_base_url("openai")


def test_config_loads_local_method_frameworks(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "local_methods")
    p = workspace_tmp / "c.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "report": {
                    "local_method_frameworks": [
                        "delivery-workflow",
                        "  skill-engineering  ",
                        "",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    c = GrowthMirrorConfig.load(p)

    assert c.report.local_method_frameworks == ["delivery-workflow", "skill-engineering"]


def test_provider_api_key_resolution(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-demo")
    monkeypatch.setenv("ZHIPUAI_API_KEY", "glm-demo")
    assert resolve_provider_api_key("deepseek") == "ds-demo"
    assert resolve_provider_api_key("glm") == "glm-demo"


def test_prompt_assets_exist():
    assert get_prompt_template("session_read/system.md.j2")
    assert get_prompt_template("session_read/user.md.j2")
    assert get_prompt_template("prompt_lens/system.md.j2")
    assert get_prompt_template("prompt_lens/user.md.j2")
    assert get_prompt_template("growth_coach/system.md.j2")
    assert get_prompt_template("growth_coach/user.md.j2")


def test_coach_prompt_scope_overrides_growth_coach_templates(tmp_path: Path):
    from ai_growth_mirror.infra.llm import coach

    workspace_tmp = run_workspace(tmp_path, "coach_scope")
    override_dir = workspace_tmp / "prompt_overrides" / "growth_coach"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "system.md.j2").write_text("coach-override-{{ language }}", encoding="utf-8")

    with prompt_asset_scope(override_dir.parent):
        rendered = coach._render_template("system.md.j2", {"language": "en"})

    assert rendered == "coach-override-en"


def test_extractor_prompt_scope_overrides_session_read_system_prompt(tmp_path: Path):
    from ai_growth_mirror.infra.extractors import llm as llm_extractor

    workspace_tmp = run_workspace(tmp_path, "extractor_scope")
    override_dir = workspace_tmp / "prompt_overrides" / "session_read"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "system.md.j2").write_text("extractor-override", encoding="utf-8")

    with prompt_asset_scope(override_dir.parent):
        rendered = llm_extractor._jinja_env().get_template("session_read/system.md.j2").render()

    assert rendered == "extractor-override"


def test_template_label_key_sets_match_between_languages():
    zh = yaml.safe_load(
        Path("ai_growth_mirror/assets/i18n/template_labels_zh.yaml").read_text(encoding="utf-8")
    )
    en = yaml.safe_load(
        Path("ai_growth_mirror/assets/i18n/template_labels_en.yaml").read_text(encoding="utf-8")
    )

    assert set(zh) == set(en)
