"""Stable personal run_id from analysis scope."""

from ai_growth_mirror.application.run_identity import resolve_personal_run_id
from ai_growth_mirror.domain.session.scope import SessionScope


def test_same_scope_same_run_id():
    kwargs = dict(
        tools=["cursor", "codex"],
        since_label="last-30-days",
        until_label="now",
        session_read_mode="llm",
        language="zh",
        scope_filters=SessionScope(),
    )
    assert resolve_personal_run_id(**kwargs) == resolve_personal_run_id(**kwargs)
    assert resolve_personal_run_id(**kwargs).startswith("personal-")


def test_different_since_changes_run_id():
    base = dict(
        tools=["cursor"],
        until_label="now",
        session_read_mode="llm",
        language="zh",
        scope_filters=SessionScope(),
    )
    a = resolve_personal_run_id(since_label="2025-01-01", **base)
    b = resolve_personal_run_id(since_label="2025-02-01", **base)
    assert a != b
