"""Product version and cache schema must stay aligned with their canonical sources."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

from ai_growth_mirror import __version__
from ai_growth_mirror.domain.cache_schema import CACHE_SCHEMA_VERSION


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_cli_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_readme_badges_reference_current_versions() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    assert f"Release-v{__version__}" in readme
    assert f"Schema-v{CACHE_SCHEMA_VERSION}" in readme


def test_readme_public_surface_mentions_current_agentic_contracts() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    assert "核心亮点 (v1.0.0)" in readme
    assert "v0.8.0-DESIGN.md" in readme
    assert "goal_locking_speed" in readme
    assert "ai-growth-mirror.summary.json" in readme


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
