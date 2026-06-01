"""Tests for the CodeBuddy session adapter."""
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_growth_mirror.domain.session.model import SessionRef
from ai_growth_mirror.infra.readers.codebuddy import CodeBuddyAdapter


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_transcript_fixture(projects_dir: Path, session_id: str) -> Path:
    """Create a minimal transcript JSONL fixture under the projects directory."""
    project_hash = "abc123def456"
    project_dir = projects_dir / project_hash
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / f"{session_id}.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nFix the API endpoint in app.py\n</user_query>",
                        "timestamp": "2026-05-20T09:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "I'll fix the API endpoint for you.",
                            },
                            {
                                "type": "tool_use",
                                "name": "edit",
                                "input": {
                                    "file_path": "D:/repo/demo/app.py",
                                    "old_str": "def api(): pass",
                                    "new_str": "def api(): return {'status': 'ok'}",
                                },
                            },
                        ],
                        "timestamp": "2026-05-20T09:00:10Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nAdd tests for the API\n</user_query>",
                        "timestamp": "2026-05-20T09:05:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "I'll add tests.",
                            },
                            {
                                "type": "tool_use",
                                "name": "write",
                                "input": {
                                    "file_path": "D:/repo/demo/tests/test_app.py",
                                    "content": "def test_api(): ...",
                                },
                            },
                            {
                                "type": "tool_use",
                                "name": "bash",
                                "input": {
                                    "command": "pytest tests/test_app.py -v",
                                },
                            },
                        ],
                        "timestamp": "2026-05-20T09:05:30Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    return transcript


def _build_history_fixture(data_root: Path) -> Path:
    """Create a minimal history.jsonl fixture."""
    data_root.mkdir(parents=True, exist_ok=True)
    history = data_root / "history.jsonl"
    history.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "session_id": "history-session-001",
                        "title": "Implement user authentication",
                        "cwd": "D:/repo/auth-project",
                        "timestamp": "2026-05-15T10:00:00Z",
                        "message_count": 5,
                    }
                ),
                json.dumps(
                    {
                        "session_id": "history-session-002",
                        "title": "Fix database connection",
                        "cwd": "D:/repo/db-project",
                        "timestamp": "2026-05-16T14:00:00Z",
                        "message_count": 3,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    return history


# ── tests ─────────────────────────────────────────────────────────────────────


def test_codebuddy_adapter_is_available_with_transcripts(tmp_path: Path):
    """Adapter.is_available() returns True when transcript JSONL files exist."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    assert adapter.is_available() is True


def test_codebuddy_adapter_is_available_with_history(tmp_path: Path):
    """Adapter.is_available() returns True when only history.jsonl exists."""
    data_root = tmp_path / ".codebuddy"
    _build_history_fixture(data_root)

    adapter = CodeBuddyAdapter(data_root=data_root)
    assert adapter.is_available() is True


def test_codebuddy_adapter_not_available(tmp_path: Path):
    """Adapter.is_available() returns False when no data exists."""
    data_root = tmp_path / ".codebuddy"
    data_root.mkdir(parents=True, exist_ok=True)

    adapter = CodeBuddyAdapter(data_root=data_root)
    assert adapter.is_available() is False


def test_codebuddy_adapter_iter_raw_sessions_from_transcripts(tmp_path: Path):
    """iter_raw_sessions yields SessionRef from transcript JSONL files."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    refs = list(adapter.iter_raw_sessions())

    assert len(refs) == 1
    ref = refs[0]
    assert isinstance(ref, SessionRef)
    assert ref.session_id == "session-001"
    assert ref.tool_name == "codebuddy"
    assert ref.start_time is not None
    assert len(ref.source_paths) == 1
    assert ref.source_paths[0].name == "session-001.jsonl"


def test_codebuddy_adapter_iter_raw_sessions_from_history(tmp_path: Path):
    """iter_raw_sessions yields SessionRef from history.jsonl fallback."""
    data_root = tmp_path / ".codebuddy"
    _build_history_fixture(data_root)

    adapter = CodeBuddyAdapter(data_root=data_root)
    refs = list(adapter.iter_raw_sessions())

    assert len(refs) == 2
    ref_ids = {ref.session_id for ref in refs}
    assert "history-session-001" in ref_ids
    assert "history-session-002" in ref_ids
    for ref in refs:
        assert ref.tool_name == "codebuddy"


def test_codebuddy_adapter_deduplicates_transcripts_and_history(tmp_path: Path):
    """Transcript files take priority over history.jsonl entries."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"

    # Create a transcript for a session that also appears in history
    _build_transcript_fixture(projects_dir, "session-001")
    # Also create history.jsonl with the same session_id
    history = data_root / "history.jsonl"
    history.write_text(
        json.dumps(
            {
                "session_id": "session-001",
                "title": "Duplicate from history",
                "timestamp": "2026-05-20T09:00:00Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "session_id": "session-002",
                "title": "Only in history",
                "timestamp": "2026-05-20T10:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    refs = list(adapter.iter_raw_sessions())

    # session-001 should appear only once (from transcript, not history)
    # session-002 should appear from history
    assert len(refs) == 2
    ref_ids = {ref.session_id for ref in refs}
    assert "session-001" in ref_ids
    assert "session-002" in ref_ids


def test_codebuddy_adapter_parse_transcript_basic(tmp_path: Path):
    """parse_session extracts basic metadata from a transcript JSONL."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    transcript = _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.session_id == "session-001"
    assert session.tool_name == "codebuddy"
    assert session.user_message_count == 2
    assert session.assistant_message_count == 2
    assert session.first_prompt == "Fix the API endpoint in app.py"
    assert len(session.top_user_messages) == 2
    assert "Fix the API endpoint in app.py" in session.top_user_messages[0]
    assert "Add tests for the API" in session.top_user_messages[1]


def test_codebuddy_adapter_parse_transcript_tool_counts(tmp_path: Path):
    """parse_session correctly counts tool invocations."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    transcript = _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.tool_counts.get("edit") == 1
    assert session.tool_counts.get("write") == 1
    assert session.tool_counts.get("bash") == 1


def test_codebuddy_adapter_parse_transcript_files_and_languages(tmp_path: Path):
    """parse_session extracts file paths and detects languages."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    transcript = _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.files_modified == 2
    assert "Python" in session.languages
    assert session.project_path != ""


def test_codebuddy_adapter_parse_transcript_verification_and_test(tmp_path: Path):
    """parse_session detects write→exec verification and test commands."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    transcript = _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.has_verification_behavior is True
    assert session.has_test_commands is True
    assert len(session.autonomous_chain_lengths) > 0


def test_codebuddy_adapter_parse_transcript_with_subagent(tmp_path: Path):
    """parse_session detects subagent (task) tool usage."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "session-subagent.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nUse a subagent to explore the codebase\n</user_query>",
                        "timestamp": "2026-05-20T11:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "task",
                                "input": {
                                    "description": "Explore codebase structure",
                                    "prompt": "List all Python files",
                                },
                            },
                        ],
                        "timestamp": "2026-05-20T11:00:10Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-subagent",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 11, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.uses_subagent is True
    assert session.subagent_invocation_count == 1


def test_codebuddy_adapter_parse_transcript_with_mcp(tmp_path: Path):
    """parse_session detects MCP tool usage."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "session-mcp.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nList MCP servers\n</user_query>",
                        "timestamp": "2026-05-20T12:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "mcp_list_servers",
                                "input": {},
                            },
                        ],
                        "timestamp": "2026-05-20T12:00:05Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-mcp",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.uses_mcp is True


def test_codebuddy_adapter_parse_transcript_with_web_search(tmp_path: Path):
    """parse_session detects web_search tool usage."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "session-web.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nSearch for the latest Python features\n</user_query>",
                        "timestamp": "2026-05-20T13:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "web_search",
                                "input": {"query": "Python 3.13 new features"},
                            },
                            {
                                "type": "tool_use",
                                "name": "web_fetch",
                                "input": {"url": "https://docs.python.org/3/"},
                            },
                        ],
                        "timestamp": "2026-05-20T13:00:10Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-web",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 13, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.uses_web_search is True
    assert session.uses_web_fetch is True


def test_codebuddy_adapter_parse_transcript_with_skill_attachment(tmp_path: Path):
    """parse_session detects skill attachments in user prompts."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "session-skill.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": '<user_query>\nUse the delivery workflow\n</user_query>\n\n<agent_skill fullPath="/home/user/skills/delivery-workflow/SKILL.md">Delivery workflow skill</agent_skill>',
                        "timestamp": "2026-05-20T14:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "I'll follow the delivery workflow.",
                            },
                        ],
                        "timestamp": "2026-05-20T14:00:05Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-skill",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.skill_invocation_count == 1
    assert len(session.unique_skills_used) > 0


def test_codebuddy_adapter_parse_history_session(tmp_path: Path):
    """parse_session handles history.jsonl entries with minimal data."""
    data_root = tmp_path / ".codebuddy"
    _build_history_fixture(data_root)

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="history-session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
            source_paths=[data_root / "history.jsonl"],
            source_mtime=(data_root / "history.jsonl").stat().st_mtime,
        )
    )

    assert session.session_id == "history-session-001"
    assert session.tool_name == "codebuddy"
    assert session.first_prompt == "Implement user authentication"
    assert session.project_path == "D:/repo/auth-project"
    assert session.user_message_count == 5


def test_codebuddy_adapter_iter_sessions_full_pipeline(tmp_path: Path):
    """iter_sessions integrates iter_raw_sessions + parse_session end-to-end."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == "session-001"
    assert session.tool_name == "codebuddy"
    assert session.user_message_count == 2
    assert session.assistant_message_count == 2
    assert session.tool_counts.get("edit") == 1
    assert session.tool_counts.get("write") == 1
    assert session.tool_counts.get("bash") == 1
    assert session.has_verification_behavior is True
    assert session.has_test_commands is True
    assert session.files_modified == 2


def test_codebuddy_adapter_empty_transcript(tmp_path: Path):
    """parse_session handles an empty transcript gracefully."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="empty",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.session_id == "empty"
    assert session.user_message_count == 0
    assert session.assistant_message_count == 0
    assert session.tool_counts == {}


def test_codebuddy_adapter_multiple_projects(tmp_path: Path):
    """iter_raw_sessions discovers transcripts across multiple project hashes."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"

    # Project A
    _build_transcript_fixture(projects_dir, "session-a")
    # Project B (same session ID pattern, different project hash)
    proj_b = projects_dir / "xyz789"
    proj_b.mkdir(parents=True, exist_ok=True)
    transcript_b = proj_b / "session-b.jsonl"
    transcript_b.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "<user_query>\nRefactor the database layer\n</user_query>",
                        "timestamp": "2026-05-21T10:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "edit",
                                "input": {"file_path": "D:/repo/other/db.py"},
                            },
                        ],
                        "timestamp": "2026-05-21T10:00:15Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    refs = list(adapter.iter_raw_sessions())

    assert len(refs) == 2
    ref_ids = {ref.session_id for ref in refs}
    assert "session-a" in ref_ids
    assert "session-b" in ref_ids


def test_codebuddy_adapter_user_message_timestamps(tmp_path: Path):
    """parse_session captures user message timestamps."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    transcript = _build_transcript_fixture(projects_dir, "session-001")

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-001",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert len(session.user_message_timestamps) == 2
    assert len(session.message_hours) == 2
    # message_hours uses local timezone; 09:00 UTC may be a different hour locally
    assert 0 <= session.message_hours[0] <= 23


def test_codebuddy_adapter_parse_transcript_string_content(tmp_path: Path):
    """parse_session handles user messages where content is a plain string."""
    data_root = tmp_path / ".codebuddy"
    projects_dir = data_root / "projects"
    project_dir = projects_dir / "proj-hash"
    project_dir.mkdir(parents=True, exist_ok=True)

    transcript = project_dir / "session-string.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "Fix the bug in main.py",
                        "timestamp": "2026-05-22T08:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "read",
                                "input": {"file_path": "D:/repo/main.py"},
                            },
                        ],
                        "timestamp": "2026-05-22T08:00:10Z",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CodeBuddyAdapter(data_root=data_root)
    session = adapter.parse_session(
        SessionRef(
            session_id="session-string",
            tool_name="codebuddy",
            start_time=datetime(2026, 5, 22, 8, 0, tzinfo=timezone.utc),
            source_paths=[transcript],
            source_mtime=transcript.stat().st_mtime,
        )
    )

    assert session.first_prompt == "Fix the bug in main.py"
    assert session.user_message_count == 1


def test_codebuddy_adapter_default_data_root():
    """Default data_root is ~/.codebuddy."""
    adapter = CodeBuddyAdapter()
    assert adapter.data_root == Path.home() / ".codebuddy"
    assert adapter.tool_name == "codebuddy"
    assert adapter.display_name == "CodeBuddy"


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path

    tmp = _Path(sys.argv[1]) if len(sys.argv) > 1 else _Path.cwd() / "test_output"
    tmp.mkdir(exist_ok=True)

    tests = [
        ("test_codebuddy_adapter_is_available_with_transcripts", test_codebuddy_adapter_is_available_with_transcripts),
        ("test_codebuddy_adapter_is_available_with_history", test_codebuddy_adapter_is_available_with_history),
        ("test_codebuddy_adapter_not_available", test_codebuddy_adapter_not_available),
        ("test_codebuddy_adapter_iter_raw_sessions_from_transcripts", test_codebuddy_adapter_iter_raw_sessions_from_transcripts),
        ("test_codebuddy_adapter_iter_raw_sessions_from_history", test_codebuddy_adapter_iter_raw_sessions_from_history),
        ("test_codebuddy_adapter_deduplicates_transcripts_and_history", test_codebuddy_adapter_deduplicates_transcripts_and_history),
        ("test_codebuddy_adapter_parse_transcript_basic", test_codebuddy_adapter_parse_transcript_basic),
        ("test_codebuddy_adapter_parse_transcript_tool_counts", test_codebuddy_adapter_parse_transcript_tool_counts),
        ("test_codebuddy_adapter_parse_transcript_files_and_languages", test_codebuddy_adapter_parse_transcript_files_and_languages),
        ("test_codebuddy_adapter_parse_transcript_verification_and_test", test_codebuddy_adapter_parse_transcript_verification_and_test),
        ("test_codebuddy_adapter_parse_transcript_with_subagent", test_codebuddy_adapter_parse_transcript_with_subagent),
        ("test_codebuddy_adapter_parse_transcript_with_mcp", test_codebuddy_adapter_parse_transcript_with_mcp),
        ("test_codebuddy_adapter_parse_transcript_with_web_search", test_codebuddy_adapter_parse_transcript_with_web_search),
        ("test_codebuddy_adapter_parse_transcript_with_skill_attachment", test_codebuddy_adapter_parse_transcript_with_skill_attachment),
        ("test_codebuddy_adapter_parse_history_session", test_codebuddy_adapter_parse_history_session),
        ("test_codebuddy_adapter_iter_sessions_full_pipeline", test_codebuddy_adapter_iter_sessions_full_pipeline),
        ("test_codebuddy_adapter_empty_transcript", test_codebuddy_adapter_empty_transcript),
        ("test_codebuddy_adapter_multiple_projects", test_codebuddy_adapter_multiple_projects),
        ("test_codebuddy_adapter_user_message_timestamps", test_codebuddy_adapter_user_message_timestamps),
        ("test_codebuddy_adapter_parse_transcript_string_content", test_codebuddy_adapter_parse_transcript_string_content),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            test_fn(tmp)
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed == 0:
        print("✅ All CodeBuddy adapter tests passed!")
    else:
        print(f"❌ {failed} test(s) failed!")
        sys.exit(1)
