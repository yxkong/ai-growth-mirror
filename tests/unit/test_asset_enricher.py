from pathlib import Path

from ai_growth_mirror.infra.enrichers.asset import scan_asset_roots


def test_scan_asset_roots_dedupes_overlapping_recent_assets(tmp_path: Path):
    root = tmp_path / "skills"
    shared = root / "share" / "demo-skill"
    shared.mkdir(parents=True)
    skill = shared / "SKILL.md"
    skill.write_text("# demo", encoding="utf-8")

    stats = scan_asset_roots([root, root / "share"])

    assert stats.skill_files_count == 1
    assert stats.total_asset_files == 1
    normalized = [item.replace("\\", "/") for item in stats.recently_modified_assets]
    assert normalized.count("share/demo-skill/SKILL.md") == 1


def test_scan_asset_roots_extracts_local_method_framework_names(tmp_path: Path):
    root = tmp_path / "agent-hub"
    (root / "skills" / "share" / "delivery-workflow").mkdir(parents=True)
    (root / "skills" / "share" / "delivery-workflow" / "SKILL.md").write_text("# skill", encoding="utf-8")
    (root / "skills" / "projects" / "demo" / "demo-dev").mkdir(parents=True)
    (root / "skills" / "projects" / "demo" / "demo-dev" / "SKILL.md").write_text("# skill", encoding="utf-8")
    (root / "prompts").mkdir()
    (root / "prompts" / "agent-task.prompt.md").write_text("# prompt", encoding="utf-8")
    (root / "rules" / "project-alpha").mkdir(parents=True)
    (root / "rules" / "project-alpha" / "PROJECT_RULES.md").write_text("# rules", encoding="utf-8")

    stats = scan_asset_roots([root], local_method_frameworks=["AI Development Governance"])

    assert "delivery-workflow" in stats.local_method_frameworks
    assert "demo-dev" in stats.local_method_frameworks
    assert "agent-task" in stats.local_method_frameworks
    assert "project-alpha" in stats.local_method_frameworks
    assert "ai-development-governance" in stats.local_method_frameworks
