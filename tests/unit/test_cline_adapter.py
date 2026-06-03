"""Tests for the Cline VS Code extension session adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_growth_mirror.domain.session.model import SessionRef
from ai_growth_mirror.infra.readers.cline import ClineAdapter


def _build_cline_fixture(root: Path, task_id: str = "task-001") -> Path:
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    task_dir = root / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    (state_dir / "taskHistory.json").write_text(
        json.dumps(
            [
                {
                    "id": task_id,
                    "ts": 1_715_700_000_000,
                    "task": "Fix API error in app.py",
                    "cwd": "D:/repo/demo-project",
                    "tokensIn": 1200,
                    "tokensOut": 800,
                }
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "api_conversation_history.json").write_text(
        json.dumps(
            [
                {
                    "role": "user",
                    "content": "Fix the API endpoint in app.py and run pytest.",
                    "ts": 1_715_700_000_000,
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "replace_in_file",
                            "input": {"path": "app.py", "diff": "..."},
                        },
                        {
                            "type": "tool_use",
                            "name": "execute_command",
                            "input": {"command": "python -m pytest tests/test_api.py"},
                        },
                    ],
                    "modelInfo": {"modelId": "anthropic/claude-sonnet-4"},
                    "ts": 1_715_700_060_000,
                },
                {
                    "role": "user",
                    "content": "Also check cli.py.",
                    "ts": 1_715_700_120_000,
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "read_file",
                            "input": {"path": "cli.py"},
                        }
                    ],
                    "ts": 1_715_700_180_000,
                },
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "task_metadata.json").write_text(
        json.dumps(
            {
                "environment_history": [
                    {"cwd": "D:/repo/demo-project", "timestamp": 1_715_700_000_000}
                ]
            }
        ),
        encoding="utf-8",
    )
    return task_dir


def test_cline_adapter_is_available(tmp_path: Path):
    root = tmp_path / ".cline" / "data"
    _build_cline_fixture(root)

    adapter = ClineAdapter(data_root=root)
    assert adapter.is_available() is True


def test_cline_adapter_not_available(tmp_path: Path):
    root = tmp_path / ".cline" / "data"
    root.mkdir(parents=True)

    adapter = ClineAdapter(data_root=root)
    assert adapter.is_available() is False


def test_cline_adapter_iter_and_parse_session(tmp_path: Path):
    root = tmp_path / ".cline" / "data"
    task_dir = _build_cline_fixture(root)

    adapter = ClineAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "cline"
    assert session.session_id == "task-001"
    assert session.project_path == "D:/repo/demo-project"
    assert session.first_prompt == "Fix the API endpoint in app.py and run pytest."
    assert session.user_message_count == 2
    assert session.assistant_message_count == 2
    assert session.tool_counts["replace_in_file"] == 1
    assert session.tool_counts["execute_command"] == 1
    assert session.tool_counts["read_file"] == 1
    assert session.files_modified == 2
    assert "Python" in session.languages
    assert session.models_used == ["anthropic/claude-sonnet-4"]
    assert session.has_test_commands is True
    assert session.input_tokens == 1200
    assert session.output_tokens == 800


def test_cline_adapter_parse_ui_messages_fallback(tmp_path: Path):
    root = tmp_path / ".cline" / "data"
    task_dir = root / "tasks" / "task-ui"
    task_dir.mkdir(parents=True)
    (task_dir / "ui_messages.json").write_text(
        json.dumps(
            [
                {
                    "say": "user_feedback",
                    "text": "Refactor the auth module",
                    "ts": 1_715_700_000_000,
                },
                {
                    "ask": "tool",
                    "tool": "read_file",
                    "text": "Reading auth.py",
                    "ts": 1_715_700_030_000,
                },
            ]
        ),
        encoding="utf-8",
    )

    adapter = ClineAdapter(data_root=root)
    session = adapter.parse_session(
        SessionRef(
            session_id="task-ui",
            tool_name="cline",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[task_dir / "ui_messages.json"],
            source_mtime=(task_dir / "ui_messages.json").stat().st_mtime,
        )
    )

    assert session.first_prompt == "Refactor the auth module"
    assert session.user_message_count == 1
    assert session.tool_counts.get("read_file") == 1
