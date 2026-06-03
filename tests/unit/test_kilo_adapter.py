"""Tests for the Kilo Code VS Code extension session adapter."""

from __future__ import annotations

import json
from pathlib import Path

from ai_growth_mirror.infra.readers.kilo import KiloAdapter
from tests.unit.test_cline_adapter import _build_cline_fixture


def _build_kilo_fixture(root: Path, task_id: str = "task-kilo-001") -> Path:
    """Reuse Cline fixture layout — Kilo uses the same on-disk task format."""
    return _build_cline_fixture(root, task_id=task_id)


def test_kilo_adapter_is_available(tmp_path: Path):
    root = tmp_path / "kilocode.kilo-code"
    _build_kilo_fixture(root)

    adapter = KiloAdapter(data_root=root)
    assert adapter.is_available() is True


def test_kilo_adapter_not_available(tmp_path: Path):
    root = tmp_path / "kilocode.kilo-code"
    root.mkdir(parents=True)

    adapter = KiloAdapter(data_root=root)
    assert adapter.is_available() is False


def test_kilo_adapter_iter_and_parse_session(tmp_path: Path):
    root = tmp_path / "kilocode.kilo-code"
    _build_kilo_fixture(root)

    adapter = KiloAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "kilo"
    assert session.session_id == "task-kilo-001"
    assert session.project_path == "D:/repo/demo-project"
    assert session.first_prompt == "Fix the API endpoint in app.py and run pytest."
    assert session.tool_counts["execute_command"] == 1
    assert session.input_tokens == 1200
    assert session.output_tokens == 800


def test_kilo_adapter_default_tool_identity():
    adapter = KiloAdapter()
    assert adapter.tool_name == "kilo"
    assert adapter.display_name == "Kilo Code"
