"""Product version and cache schema must stay aligned with their canonical sources."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib
import yaml

from ai_growth_mirror import __version__
from ai_growth_mirror.domain.cache_schema import CACHE_SCHEMA_VERSION


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing frontmatter: {path}"
    _, raw, _ = text.split("---", 2)
    payload = yaml.safe_load(raw) or {}
    assert isinstance(payload, dict), path
    return payload


def test_cli_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_readme_badges_reference_current_versions() -> None:
    for readme_path in ("README.md", "en/README.md"):
        readme = (_repo_root() / readme_path).read_text(encoding="utf-8")
        assert f"Release-v{__version__}" in readme
        assert f"Schema-v{CACHE_SCHEMA_VERSION}" in readme


def test_readme_public_surface_mentions_current_agentic_contracts() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    assert f"核心亮点 (v{__version__})" in readme
    assert "v0.8.0-DESIGN.md" in readme
    assert "goal_locking_speed" in readme
    assert "ai-growth-mirror.summary.json" in readme


def test_current_design_and_adr_are_indexed_bilingually() -> None:
    version_design = f"v{__version__}-DESIGN.md"
    adr_name = f"ADR-v{__version__}-assessment-policy-and-root-task.md"

    for index_path in ("docs/design/README.md", "docs/en/design/README.md"):
        index = (_repo_root() / index_path).read_text(encoding="utf-8")
        assert version_design in index
        assert adr_name in index

    zh_design = (_repo_root() / "docs" / "design" / version_design).read_text(
        encoding="utf-8"
    )
    en_design = (_repo_root() / "docs" / "en" / "design" / version_design).read_text(
        encoding="utf-8"
    )
    assert f"../en/design/{version_design}" in zh_design
    assert f"../../design/{version_design}" in en_design

    zh_adr = (_repo_root() / "docs" / "design" / adr_name).read_text(encoding="utf-8")
    en_adr = (_repo_root() / "docs" / "en" / "design" / adr_name).read_text(
        encoding="utf-8"
    )
    assert f"../en/design/{adr_name}" in zh_adr
    assert f"../../design/{adr_name}" in en_adr


def test_uv_lock_matches_pyproject_version() -> None:
    lock_text = (_repo_root() / "uv.lock").read_text(encoding="utf-8")
    pyproject = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    expected = pyproject["project"]["version"]
    match = re.search(
        r'name = "ai-growth-mirror"\s+version = "([^"]+)"',
        lock_text,
    )
    assert match is not None, "ai-growth-mirror entry missing in uv.lock"
    assert match.group(1) == expected


def test_english_docs_are_checked_mirrors_of_chinese_canonical_sources() -> None:
    root = _repo_root()
    pairs = [(root / "docs/en/README.md", root / "docs/README.md")]
    for area in ("config", "design"):
        for mirror in sorted((root / "docs/en" / area).glob("*.md")):
            canonical = root / "docs" / area / mirror.name
            if canonical.exists():
                pairs.append((mirror, canonical))

    assert pairs
    parity_fields = ("spec_id", "spec_version", "version", "approval", "decision_status")
    for mirror, canonical in pairs:
        mirror_meta = _frontmatter(mirror)
        canonical_meta = _frontmatter(canonical)
        assert mirror_meta.get("status") == "mirror", mirror
        assert mirror_meta.get("canonical_path") == canonical.relative_to(root).as_posix(), mirror
        assert canonical_meta.get("status") != "mirror", canonical
        for field in parity_fields:
            if field in mirror_meta or field in canonical_meta:
                assert mirror_meta.get(field) == canonical_meta.get(field), (mirror, field)


def test_public_english_readme_declares_its_canonical_source() -> None:
    english = (_repo_root() / "en/README.md").read_text(encoding="utf-8")
    assert "<!-- status: mirror; canonical_path: README.md -->" in english


def test_docs_do_not_declare_parallel_bilingual_truth_sources() -> None:
    root = _repo_root()
    for path in (root / "docs/README.md", root / "docs/en/README.md"):
        text = path.read_text(encoding="utf-8")
        assert "中英双真源" not in text
        assert "parallel truth source" not in text.lower()
