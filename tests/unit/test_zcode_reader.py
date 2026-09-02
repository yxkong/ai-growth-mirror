from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai_growth_mirror.infra.readers.zcode import ZCodeAdapter


def _create_db(path: Path, *, include_part: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE session (id TEXT PRIMARY KEY, parent_id TEXT, directory TEXT NOT NULL, version TEXT NOT NULL, summary_additions INTEGER, summary_deletions INTEGER, summary_files INTEGER, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL)")
        db.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
        if include_part:
            db.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT NOT NULL, session_id TEXT NOT NULL, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
        db.execute("CREATE TABLE tool_usage (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, tool_call_id TEXT NOT NULL, tool_name TEXT NOT NULL, status TEXT NOT NULL, started_at INTEGER NOT NULL, exit_code INTEGER, cancelled_by_user INTEGER NOT NULL DEFAULT 0)")
        db.execute("CREATE TABLE model_usage (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, provider_id TEXT NOT NULL, model_id TEXT NOT NULL, status TEXT NOT NULL, started_at INTEGER NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0, cache_read_input_tokens INTEGER NOT NULL DEFAULT 0, tool_call_count INTEGER NOT NULL DEFAULT 0)")
        db.execute("INSERT INTO session VALUES ('root', NULL, 'D:/repo/demo', '1', 12, 2, 2, 1756720800000, 1756720860000)")
        db.execute("INSERT INTO session VALUES ('child', 'root', 'D:/repo/demo', '1', 3, 0, 1, 1756720810000, 1756720850000)")
        user = json.dumps({"role": "user", "time": {"created": 1756720800000}})
        assistant = json.dumps({"role": "assistant", "time": {"created": 1756720801000, "completed": 1756720860000}, "modelID": "model-a", "providerID": "provider-a"})
        db.execute("INSERT INTO message VALUES ('u1', 'root', 1756720800000, 1756720800000, ?)", (user,))
        db.execute("INSERT INTO message VALUES ('a1', 'root', 1756720801000, 1756720860000, ?)", (assistant,))
        db.execute("INSERT INTO message VALUES ('a2', 'child', 1756720810000, 1756720850000, ?)", (assistant,))
        if include_part:
            db.execute("INSERT INTO part VALUES ('p1', 'u1', 'root', 1756720800000, 1756720800000, ?)", (json.dumps({"type": "text", "text": "Implement and verify cache."}),))
            db.execute("INSERT INTO part VALUES ('p2', 'a1', 'root', 1756720801000, 1756720801000, ?)", (json.dumps({"type": "tool", "callID": "c1", "tool": "Write", "state": {"status": "completed", "input": {"path": "src/cache.py"}}}),))
            db.execute("INSERT INTO part VALUES ('p3', 'a2', 'child', 1756720810000, 1756720810000, ?)", (json.dumps({"type": "tool", "callID": "c2", "tool": "Bash", "state": {"status": "completed", "input": {"command": "pytest -q"}}}),))
        db.execute("INSERT INTO tool_usage VALUES ('t1', 'root', 'c1', 'Write', 'completed', 1756720801000, 0, 0)")
        db.execute("INSERT INTO tool_usage VALUES ('t2', 'child', 'c2', 'Bash', 'completed', 1756720810000, 0, 0)")
        db.execute("INSERT INTO model_usage VALUES ('m1', 'root', 'provider-a', 'model-a', 'completed', 1756720801000, 100, 30, 5, 20, 1)")
        db.execute("INSERT INTO model_usage VALUES ('m2', 'child', 'provider-a', 'model-b', 'completed', 1756720810000, 40, 10, 0, 5, 1)")


def test_zcode_reader_uses_read_only_sqlite_and_rolls_up_children(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "db.sqlite"
    _create_db(db_path)
    adapter = ZCodeAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == "root"
    assert session.first_prompt == "Implement and verify cache."
    assert session.user_message_count == 1
    assert session.assistant_message_count == 2
    assert session.tool_counts == {"write": 1, "bash": 1}
    assert session.input_tokens == 140
    assert session.output_tokens == 40
    assert set(session.models_used) == {"model-a", "model-b"}
    assert session.uses_subagent is True
    assert session.subagent_invocation_count == 1
    assert session.has_verification_behavior is True
    assert session.has_test_commands is True
    assert session.files_modified == 3

    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA query_only").fetchone()[0] == 0


def test_zcode_reader_fails_closed_on_schema_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "db.sqlite"
    _create_db(db_path, include_part=False)
    adapter = ZCodeAdapter(data_root=tmp_path)
    assert adapter.is_available() is False
    assert list(adapter.iter_sessions()) == []
    assert adapter.diagnostics.schema_mismatch >= 1


def test_zcode_reader_never_uses_model_io_rollout_as_fallback(tmp_path: Path) -> None:
    rollout = tmp_path / "rollout" / "model-io-private.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_text('{"headers":{"authorization":"CANARY-SECRET"}}', encoding="utf-8")
    adapter = ZCodeAdapter(data_root=tmp_path)
    assert adapter.is_available() is False
    assert list(adapter.iter_sessions()) == []
    assert "CANARY" not in repr(adapter.diagnostics)
