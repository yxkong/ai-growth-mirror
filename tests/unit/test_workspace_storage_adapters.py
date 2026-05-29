import json
from pathlib import Path

from ai_growth_mirror.infra.readers.qoder import QCoderAdapter
from ai_growth_mirror.infra.readers.trae import TraeAdapter
from tests.conftest import run_workspace


def _build_workspace_storage_fixture(root: Path) -> Path:
    workspace_dir = root / "User" / "workspaceStorage" / "workspace-a"
    chat_dir = workspace_dir / "chatSessions"
    chat_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "workspace.json").write_text(
        json.dumps({"folder": "D:/repo/demo-project"}),
        encoding="utf-8",
    )
    session_file = chat_dir / "session-1.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": 0,
                        "v": {
                            "sessionId": "session-1",
                            "creationDate": "2026-05-20T09:00:00Z",
                            "requests": [
                                {
                                    "message": {"text": "Goal: fix API error in app.py and verify with pytest."},
                                    "response": {
                                        "text": "Patched the API and verified the change.",
                                        "toolCalls": [
                                            {"toolName": "edit", "path": "app.py"},
                                            {"toolName": "bash", "path": "tests/test_api.py"},
                                        ],
                                        "model": "demo-model",
                                    },
                                },
                                {
                                    "message": {"text": "Also check the CLI entrypoint."},
                                    "response": {
                                        "text": "Checked the CLI entrypoint too.",
                                        "toolCalls": [{"toolName": "read", "path": "cli.py"}],
                                    },
                                },
                            ],
                        },
                    }
                )
            ]
        ),
        encoding="utf-8",
    )
    return root


def test_trae_adapter_parses_workspace_storage_sessions(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "trae")
    root = _build_workspace_storage_fixture(workspace_tmp / ".trae-cn")

    adapter = TraeAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert adapter.is_available() is True
    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "trae"
    assert session.project_path == "D:/repo/demo-project"
    assert session.first_prompt.startswith("Goal: fix API error")
    assert session.user_message_count == 2
    assert session.assistant_message_count == 2
    assert session.files_modified == 3
    assert session.languages["Python"] >= 1
    assert session.tool_counts["edit"] == 1
    assert session.tool_counts["bash"] == 1
    assert session.models_used == ["demo-model"]


def test_qcoder_adapter_parses_workspace_storage_sessions(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "qcoder")
    root = _build_workspace_storage_fixture(workspace_tmp / ".qoder")

    adapter = QCoderAdapter(data_root=root)
    sessions = list(adapter.iter_sessions())

    assert adapter.is_available() is True
    assert len(sessions) == 1
    session = sessions[0]
    assert session.tool_name == "qcoder"
    assert session.project_path == "D:/repo/demo-project"
    assert session.tool_counts["read"] == 1
