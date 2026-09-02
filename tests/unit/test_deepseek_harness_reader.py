from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_growth_mirror.infra.readers.deepseek_harness import DeepSeekHarnessAdapter


def _rows(session_id: str, *, parent: str | None = None) -> list[dict]:
    header = {
        "type": "session",
        "version": 0,
        "id": session_id,
        "createdAt": "2026-09-01T10:00:00Z",
        "cwd": "D:/repo/demo",
        "delegationDepth": 1 if parent else 0,
        "agentPreset": "default",
    }
    if parent:
        header["parentSession"] = parent
    return [
        header,
        {"type": "user/message", "seq": 1, "time": "2026-09-01T10:00:01Z", "data": {"content": [{"type": "text", "text": "Implement and test the cache."}], "source": {"kind": "user"}}},
        {"type": "assistant/message", "seq": 2, "time": "2026-09-01T10:00:02Z", "data": {"message": {"role": "assistant"}, "usage": {"inputTokens": 100, "outputTokens": 30, "cacheReadTokens": 20}}},
        {"type": "tool/call", "seq": 3, "time": "2026-09-01T10:00:03Z", "data": {"name": "write", "arguments": {"path": "src/cache.py"}, "callId": "c1"}},
        {"type": "tool/result", "seq": 4, "time": "2026-09-01T10:00:04Z", "data": {"callId": "c1", "outcome": "completed"}},
        {"type": "tool/call", "seq": 5, "time": "2026-09-01T10:00:05Z", "data": {"name": "bash", "arguments": {"command": "pytest -q"}, "callId": "c2"}},
        {"type": "step/end", "seq": 6, "time": "2026-09-01T10:00:06Z", "data": {"step": 1, "turn": 1}},
        {"type": "user/message", "seq": 7, "time": "2026-09-01T10:00:06Z", "data": {"content": "PRIVATE SYSTEM SNAPSHOT", "source": {"kind": "plugin"}}},
        # Packed rows are transport details and must not be counted as another call/message.
        {"type": "tool-call-chunks", "seq0": 8, "time0": "2026-09-01T10:00:07Z", "data": {"name": "write", "texts": ["ignored"]}},
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_deepseek_reader_rolls_child_evidence_into_one_root_task(tmp_path: Path) -> None:
    root = tmp_path / "project" / "root" / "session.jsonl"
    child = tmp_path / "project" / "child" / "session.jsonl"
    _write_jsonl(root, _rows("root"))
    _write_jsonl(child, _rows("child", parent="root"))

    adapter = DeepSeekHarnessAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == "root"
    assert session.user_message_count == 1
    assert "PRIVATE SYSTEM SNAPSHOT" not in session.top_user_messages
    assert session.tool_counts == {"write": 2, "bash": 2}
    assert session.uses_subagent is True
    assert session.subagent_invocation_count == 1
    assert session.input_tokens == 200
    assert session.output_tokens == 60
    assert session.has_test_commands is True
    assert session.has_verification_behavior is True
    assert session.autonomous_chain_lengths == [2, 2]
    assert session.turns_until_first_file_write == 1


def test_deepseek_reader_raw_and_zstd_are_equivalent(tmp_path: Path) -> None:
    zstandard = pytest.importorskip("zstandard")
    raw_path = tmp_path / "raw" / "session.jsonl"
    zstd_path = tmp_path / "compressed" / "session.jsonl.zstd"
    rows = _rows("same")
    _write_jsonl(raw_path, rows)
    zstd_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row) for row in rows).encode()
    zstd_path.write_bytes(zstandard.ZstdCompressor().compress(payload))

    raw = DeepSeekHarnessAdapter(data_root=raw_path.parent).parse_session(
        next(DeepSeekHarnessAdapter(data_root=raw_path.parent).iter_raw_sessions())
    )
    compressed = DeepSeekHarnessAdapter(data_root=zstd_path.parent).parse_session(
        next(DeepSeekHarnessAdapter(data_root=zstd_path.parent).iter_raw_sessions())
    )
    assert raw.to_dict() == compressed.to_dict()


def test_deepseek_reader_rejects_unknown_version_without_leaking_content(tmp_path: Path) -> None:
    path = tmp_path / "bad" / "session.jsonl"
    rows = _rows("bad")
    rows[0]["version"] = 99
    rows[1]["data"]["content"] = "CANARY-PRIVATE-CONTENT"
    _write_jsonl(path, rows)
    adapter = DeepSeekHarnessAdapter(data_root=tmp_path)
    assert list(adapter.iter_sessions()) == []
    assert adapter.diagnostics.schema_mismatch == 1
    assert "CANARY" not in repr(adapter.diagnostics)


def test_deepseek_reader_rejects_non_monotonic_logical_sequence(tmp_path: Path) -> None:
    path = tmp_path / "bad-seq" / "session.jsonl"
    rows = _rows("bad-seq")
    rows[3]["seq"] = 1
    _write_jsonl(path, rows)
    adapter = DeepSeekHarnessAdapter(data_root=tmp_path)
    assert list(adapter.iter_sessions()) == []
    assert adapter.diagnostics.corrupt == 1


def test_deepseek_reader_skips_empty_seed_without_marking_it_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "seed" / "session.jsonl"
    rows = _rows("seed")[:1]
    rows.append({"type": "session/end-seed", "seq": 1, "time": "2026-09-01T10:00:01Z", "data": {}})
    _write_jsonl(path, rows)
    adapter = DeepSeekHarnessAdapter(data_root=tmp_path)

    assert list(adapter.iter_sessions()) == []
    assert adapter.diagnostics.skipped == 1
    assert adapter.diagnostics.corrupt == 0


def test_deepseek_reader_maps_goal_and_todo_events_to_structured_workflow(tmp_path: Path) -> None:
    path = tmp_path / "goal" / "session.jsonl"
    rows = _rows("goal")
    rows.insert(-1, {"type": "goal/change", "seq": 8, "time": "2026-09-01T10:00:08Z", "data": {"operation": "created"}})
    rows.insert(-1, {"type": "todo/write", "seq": 9, "time": "2026-09-01T10:00:09Z", "data": {"todos": []}})
    rows[-1]["seq0"] = 10
    _write_jsonl(path, rows)

    session = next(DeepSeekHarnessAdapter(data_root=tmp_path).iter_sessions())

    assert session.slash_commands == ["/goal"]
    assert "plan_mode" in session.advanced_features
