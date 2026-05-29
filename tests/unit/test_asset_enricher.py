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
