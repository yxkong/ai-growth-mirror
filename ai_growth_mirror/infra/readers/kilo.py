"""Adapter for Kilo Code (VS Code extension) task history.

Kilo Code (Cline lineage) stores tasks under VS Code global storage::

    globalStorage/kilocode.kilo-code/tasks/<task-id>/
        api_conversation_history.json
        ui_messages.json
        task_metadata.json

Users may override storage via the ``kilo-code.customStoragePath`` setting; point
``tools.kilo.data_root`` at that directory when it differs from the default.
"""

from __future__ import annotations

from pathlib import Path

from .cline import ClineFamilyTaskAdapter

_KILO_EXTENSION_IDS = ("kilocode.kilo-code",)


class KiloAdapter(ClineFamilyTaskAdapter):
    """Session adapter for Kilo Code VS Code extension."""

    tool_name = "kilo"
    display_name = "Kilo Code"
    default_data_root = Path.home() / ".kilocode"
    extension_ids = _KILO_EXTENSION_IDS
