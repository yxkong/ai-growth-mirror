"""Adapter for QCoder local workspaceStorage chat sessions."""

from __future__ import annotations

from pathlib import Path

from .workspace_storage import WorkspaceStorageChatAdapter, appdata_path


class QCoderAdapter(WorkspaceStorageChatAdapter):
    tool_name = "qcoder"
    display_name = "QCoder"
    default_data_root = Path.home() / ".qoder"

    def extra_storage_roots(self) -> list[Path]:
        return [
            Path.home() / ".qoder",
            appdata_path("Qoder"),
            appdata_path("Qoder IDE"),
        ]
