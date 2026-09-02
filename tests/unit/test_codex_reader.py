from datetime import datetime, timezone
from pathlib import Path

from ai_growth_mirror.infra.readers.base import SessionRef
from ai_growth_mirror.infra.readers.codex import CodexAdapter


def test_codex_reader_parses_token_count_usage(tmp_path: Path):
    sessions_root = tmp_path / "sessions" / "2026" / "05" / "27"
    sessions_root.mkdir(parents=True)
    rollout = sessions_root / "rollout-2026-05-27T10-00-00-test.jsonl"
    rollout.write_text(
        "\n".join(
            [
                '{"type":"session_meta","payload":{"id":"sess-1","timestamp":"2026-05-27T10:00:00Z","cwd":"D:/repo/demo","model":"gpt-4.1-mini"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"请修复缓存统计。"}]}}',
                '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":100,"cached_input_tokens":30,"output_tokens":8},"last_token_usage":{"input_tokens":100,"cached_input_tokens":30,"output_tokens":8}}}}',
                '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":180,"cached_input_tokens":70,"output_tokens":20},"last_token_usage":{"input_tokens":80,"cached_input_tokens":40,"output_tokens":12}}}}',
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodexAdapter(data_root=tmp_path)
    session = adapter.parse_session(
        SessionRef(
            session_id="sess-1",
            tool_name="codex",
            start_time=datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc),
            source_paths=[rollout],
            source_mtime=rollout.stat().st_mtime,
        )
    )

    assert session.input_tokens == 180
    assert session.output_tokens == 20
    assert session.cache_read_tokens == 70
    assert session.total_cost_usd is not None


def test_codex_reader_records_turns_until_first_file_write(tmp_path: Path):
    sessions_root = tmp_path / "sessions" / "2026" / "05" / "27"
    sessions_root.mkdir(parents=True)
    rollout = sessions_root / "rollout-2026-05-27T11-00-00-write.jsonl"
    rollout.write_text(
        "\n".join(
            [
                '{"type":"session_meta","payload":{"id":"sess-2","timestamp":"2026-05-27T11:00:00Z","cwd":"D:/repo/demo","model":"gpt-4.1-mini"}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"加个缓存。"}]}}',
                '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"也限制并发到 4。"}]}}',
                '{"type":"response_item","payload":{"type":"function_call","name":"apply_patch","arguments":{"path":"src/cache.py"}}}',
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodexAdapter(data_root=tmp_path)
    session = adapter.parse_session(
        SessionRef(
            session_id="sess-2",
            tool_name="codex",
            start_time=datetime(2026, 5, 27, 11, 0, tzinfo=timezone.utc),
            source_paths=[rollout],
            source_mtime=rollout.stat().st_mtime,
        )
    )

    # First write arrives after the 2nd user message -> precise turn count,
    # not the coarse files_modified>0 fallback (which would hard-code 3).
    assert session.turns_until_first_file_write == 2
