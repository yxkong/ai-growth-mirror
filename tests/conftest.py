"""Shared fixtures: FakeLLMClient and session factories (no real LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ai_growth_mirror.domain.common.contracts import LlmCallRequest
from ai_growth_mirror.domain.session.model import SessionRecord

# Repo-local scratch root for pytest basetemp, pytest cache, and ad-hoc manual runs.
PROJECT_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp"


@pytest.fixture(scope="session", autouse=True)
def _ensure_project_tmp_root() -> None:
    """Create .tmp/ early so basetemp and manual helpers never touch repo root."""
    PROJECT_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def manual_run_workspace(name: str = "manual") -> Path:
    """Scratch directory for ``python tests/unit/test_*.py`` ad-hoc runs."""
    workspace = PROJECT_TMP_ROOT / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def run_workspace(tmp_path: Path, name: str = "workspace") -> Path:
    """Per-test isolated directory under pytest tmp_path (``.tmp/pytest/`` via basetemp)."""
    workspace = tmp_path / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@dataclass
class FakeLLMClient:
    """Returns canned text from a queue (implements LLMClient.complete)."""

    queue: list[str]

    def complete(self, request: LlmCallRequest) -> str:
        return self.queue.pop(0) if self.queue else "{}"

    def complete_json(self, request: LlmCallRequest):
        return json.loads(self.complete(request))


@pytest.fixture
def prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "ai_growth_mirror" / "assets" / "prompts"


def make_session(
    *,
    tool: str = "demo",
    session_id: str = "s1",
    outcome: str | None = None,
) -> SessionRecord:
    return SessionRecord(
        session_id=session_id,
        tool_name=tool,
        start_time="2026-05-17T10:00:00+00:00",
        message_hours=[10],
    )


def make_facets_response() -> str:
    return '{"facets": {"theme": "debugging", "risk": "low"}}'


def load_report_label_catalogs(language: str = "zh"):
    """Preload all YAML catalogs required by report view assembly and rendering."""
    from ai_growth_mirror.application.label_catalogs import load_report_label_catalogs as _load

    return _load(language)


@pytest.fixture
def report_catalogs_zh():
    return load_report_label_catalogs("zh")


@pytest.fixture
def report_catalogs_en():
    return load_report_label_catalogs("en")

