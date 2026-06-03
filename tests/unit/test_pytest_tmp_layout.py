"""Guardrails: pytest scratch files stay under repo .tmp/."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import PROJECT_TMP_ROOT


def test_pytest_tmp_path_stays_under_project_tmp(tmp_path: Path) -> None:
    resolved = tmp_path.resolve()
    root = PROJECT_TMP_ROOT.resolve()
    assert resolved.is_relative_to(root), f"expected under {root}, got {resolved}"


def test_project_tmp_root_is_repo_local() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert PROJECT_TMP_ROOT.resolve() == (repo_root / ".tmp").resolve()
