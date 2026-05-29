"""Test QCoder adapter with comprehensive feature extraction."""
import json
from pathlib import Path

from ai_growth_mirror.infra.readers.qoder import QCoderAdapter
from tests.conftest import run_workspace


def _build_qcoder_sqlite_fixture(root: Path) -> Path:
    """Build a test fixture with state.vscdb format."""
    import sqlite3

    workspace_dir = root / "User" / "workspaceStorage" / "workspace-b"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Create workspace.json
    (workspace_dir / "workspace.json").write_text(
        json.dumps({"folder": "D:/repo/qcoder-project"}),
        encoding="utf-8",
    )

    # Create state.vscdb
    state_db = workspace_dir / "state.vscdb"
    with sqlite3.connect(state_db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ItemTable (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Insert workspace.json
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("workspace.json", json.dumps({"folder": "D:/repo/qcoder-project"}))
        )

        # Insert input history
        input_history = [
            {
                "inputText": "Goal: implement user authentication in auth.py",
                "parsedQuery": [
                    {"folderPath": "D:/repo/qcoder-project/auth.py"},
                    {"folderPath": "D:/repo/qcoder-project/models.py"}
                ]
            },
            {
                "inputText": "Add tests for the authentication flow",
                "parsedQuery": [
                    {"folderPath": "D:/repo/qcoder-project/tests/test_auth.py"}
                ]
            }
        ]
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("chat.input-history", json.dumps(input_history))
        )

        # Insert model map
        model_map = {
            "session-1": {
                "model": "qwen-max"
            }
        }
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("chat.modelMap", json.dumps(model_map))
        )

        # Insert session metadata
        session_meta = {
            "currentSessionId": "qcoder-session-001"
        }
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            ("ai-agent-storage.sessionMetadata", json.dumps(session_meta))
        )

    return root


def test_qcoder_adapter_parses_jsonl_sessions(tmp_path: Path):
    """Test QCoder adapter with JSONL format sessions."""
    workspace_tmp = run_workspace(tmp_path, "qcoder")
    root = workspace_tmp / ".qcoder"
    workspace_dir = root / "User" / "workspaceStorage" / "workspace-a"
    chat_dir = workspace_dir / "chatSessions"
    chat_dir.mkdir(parents=True, exist_ok=True)

    (workspace_dir / "workspace.json").write_text(
        json.dumps({"folder": "D:/repo/demo-project"}),
        encoding="utf-8",
    )

    session_file = chat_dir / "session-1.jsonl"
    session_file.write_text(
        "\n".join([
            json.dumps({
                "kind": 0,
                "v": {
                    "sessionId": "session-1",
                    "creationDate": "2026-05-20T09:00:00Z",
                    "requests": [
                        {
                            "message": {"text": "Fix the API endpoint"},
                            "response": {
                                "text": "Fixed",
                                "toolCalls": [
                                    {"toolName": "edit", "path": "app.py"},
                                    {"toolName": "bash", "command": "pytest tests/"}
                                ],
                                "model": "qwen-plus"
                            }
                        }
                    ]
                }
            })
        ]),
        encoding="utf-8",
    )

    adapter = QCoderAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert adapter.is_available() is True
    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "qcoder"
    assert session.project_path == "D:/repo/demo-project"
    assert session.first_prompt == "Fix the API endpoint"
    assert session.user_message_count == 1
    assert session.assistant_message_count == 1
    assert session.files_modified >= 1
    assert session.tool_counts.get("edit") == 1
    assert session.models_used == ["qwen-plus"]


def test_qcoder_adapter_parses_sqlite_sessions(tmp_path: Path):
    """Test QCoder adapter with SQLite state.vscdb format."""
    workspace_tmp = run_workspace(tmp_path, "qcoder")
    root = _build_qcoder_sqlite_fixture(workspace_tmp / ".qcoder")

    adapter = QCoderAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert adapter.is_available() is True
    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "qcoder"
    assert session.project_path == "D:/repo/qcoder-project"
    assert "implement user authentication" in session.first_prompt.lower()
    assert session.user_message_count == 2
    assert session.files_modified >= 2
    assert "Python" in session.languages
    assert session.models_used == ["qwen-max"]


def test_qcoder_adapter_detects_subagent_and_mcp(tmp_path: Path):
    """Test QCoder adapter detects subagent and MCP usage."""
    workspace_tmp = run_workspace(tmp_path, "qcoder")
    root = workspace_tmp / ".qoder"
    workspace_dir = root / "User" / "workspaceStorage" / "workspace-c"
    chat_dir = workspace_dir / "chatSessions"
    chat_dir.mkdir(parents=True, exist_ok=True)

    (workspace_dir / "workspace.json").write_text(
        json.dumps({"folder": "D:/repo/advanced-project"}),
        encoding="utf-8",
    )

    session_file = chat_dir / "session-2.jsonl"
    session_file.write_text(
        "\n".join([
            json.dumps({
                "kind": 0,
                "v": {
                    "sessionId": "session-2",
                    "creationDate": "2026-05-20T10:00:00Z",
                    "requests": [
                        {
                            "message": {"text": "Use subagent to refactor the code and check MCP servers"},
                            "response": {
                                "text": "Done",
                                "toolCalls": [
                                    {"toolName": "task", "description": "refactor"},
                                    {"toolName": "mcp_list_servers"}
                                ]
                            }
                        }
                    ]
                }
            })
        ]),
        encoding="utf-8",
    )

    adapter = QCoderAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert len(sessions) == 1
    session = sessions[0]
    assert session.uses_subagent is True
    assert session.uses_mcp is True
    assert session.subagent_invocation_count >= 1


if __name__ == "__main__":
    import sys
    from pathlib import Path

    tmp = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / "test_output"
    tmp.mkdir(exist_ok=True)

    print("Testing JSONL format...")
    test_qcoder_adapter_parses_jsonl_sessions(tmp)
    print("✓ JSONL test passed")

    print("\nTesting SQLite format...")
    test_qcoder_adapter_parses_sqlite_sessions(tmp)
    print("✓ SQLite test passed")

    print("\nTesting subagent/MCP detection...")
    test_qcoder_adapter_detects_subagent_and_mcp(tmp)
    print("✓ Subagent/MCP test passed")

    print("\n✅ All QCoder adapter tests passed!")
