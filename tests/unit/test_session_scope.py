"""Tests for session scope filtering (repo / dir / keyword)."""

from __future__ import annotations

from pathlib import Path

from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.session.scope import (
    SessionScope,
    apply_session_scope,
    matches_session_scope,
)
from tests.conftest import make_session


def _session(
    *,
    project_path: str = "",
    git_origin_url: str = "",
    first_prompt: str = "",
) -> SessionRecord:
    return SessionRecord(
        session_id="s1",
        tool_name="cursor",
        start_time="2026-05-17T10:00:00+00:00",
        project_path=project_path,
        git_origin_url=git_origin_url,
        first_prompt=first_prompt,
    )


def test_scope_repo_matches_origin_or_folder_name():
    session = _session(
        project_path="D:/work/ai-growth-mirror",
        git_origin_url="https://github.com/yxkong/ai-growth-mirror.git",
    )
    scope = SessionScope(repos=("ai-growth-mirror",))
    assert matches_session_scope(session, scope)


def test_scope_repo_rejects_mismatch():
    session = _session(project_path="D:/work/other-repo")
    scope = SessionScope(repos=("ai-growth-mirror",))
    assert not matches_session_scope(session, scope)


def test_scope_dir_matches_project_under_root():
    root = Path("D:/work/ai-growth-mirror")
    session = _session(project_path=str(root / "src"))
    scope = SessionScope(dirs=(root,))
    assert matches_session_scope(session, scope)


def test_scope_keyword_matches_first_prompt():
    session = _session(first_prompt="请用 /delivery-workflow 跑一遍")
    scope = SessionScope(keywords=("delivery-workflow",))
    assert matches_session_scope(session, scope)


def test_apply_session_scope_noop_when_empty():
    sessions = [
        _session(project_path="D:/a"),
        _session(project_path="D:/b"),
    ]
    filtered = apply_session_scope(sessions, SessionScope())
    assert len(filtered) == 2


def test_apply_session_scope_filters_combined():
    sessions = [
        _session(project_path="D:/work/ai-growth-mirror", first_prompt="fix bug"),
        _session(project_path="D:/work/other", first_prompt="fix bug"),
        _session(project_path="D:/work/ai-growth-mirror", first_prompt="unrelated"),
    ]
    scope = SessionScope(
        repos=("ai-growth-mirror",),
        keywords=("fix",),
    )
    filtered = apply_session_scope(sessions, scope)
    assert len(filtered) == 1
    assert filtered[0].project_path.endswith("ai-growth-mirror")
