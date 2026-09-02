"""Release-gate contract for the repository's hosted CI workflow."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "unit-tests.yml"


def test_ci_covers_supported_os_and_python_matrix() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "ubuntu-latest" in workflow
    assert "windows-latest" in workflow
    assert '"3.12"' in workflow
    assert '"3.13"' in workflow
    assert "runs-on: ${{ matrix.os }}" in workflow


def test_ci_uses_locked_uv_environment_and_build_gate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    uses_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]
    assert uses_lines
    for line in uses_lines:
        assert re.search(r"uses:\s+[^@\s]+@[0-9a-f]{40}(?:\s+#.*)?$", line), line
    assert "uv sync --locked --extra dev" in workflow
    assert "./.venv/bin/python" in workflow
    assert '.\\.venv\\Scripts\\python.exe' in workflow
    assert "${{ matrix.python-command }} -m pytest tests/unit tests/evals" in workflow
    assert "${{ matrix.python-command }} -m compileall -q ai_growth_mirror" in workflow
    assert "uv build" in workflow
