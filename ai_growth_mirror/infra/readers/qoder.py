"""Adapter for QCoder local workspaceStorage chat sessions.

QCoder stores session data in VS Code-style workspaceStorage directories,
similar to Trae. This adapter extends WorkspaceStorageChatAdapter with
QCoder-specific storage paths and enhanced feature extraction.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ...domain.session.model import SessionRef, SessionRecord
from ...domain.signals.tooling import compute_tier_counts, normalize_tool_name
from .base import (
    BaseSessionAdapter,
    EXEC_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    TEST_PATTERNS,
    WRITE_TOOL_NAMES,
    _common_prefix_path,
    _max_mtime,
    detect_authorship_path,
    detect_language,
    parse_ts,
)
from .workspace_storage import WorkspaceStorageChatAdapter, appdata_path


_PATH_INPUT_KEYS = ("path", "file_path", "target_file", "target_notebook", "notebook_path")
_USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE)


class QCoderAdapter(WorkspaceStorageChatAdapter):
    tool_name = "qcoder"
    display_name = "QCoder"
    default_data_root = Path.home() / ".qoder"

    def extra_storage_roots(self) -> list[Path]:
        return [
            Path.home() / ".qoder",
            appdata_path("Qoder"),
            appdata_path("QCoder IDE"),
        ]

    def _storage_roots(self) -> list[Path]:
        """Scan extra install paths only when using the default data root."""
        from .workspace_storage import _dedupe_paths

        candidates = list(self.data_roots)
        if len(candidates) == 1 and candidates[0] == self.default_data_root:
            candidates.extend(self.extra_storage_roots())
        resolved: list[Path] = []
        for root in _dedupe_paths(candidates):
            if root.name == "workspaceStorage":
                resolved.append(root)
            resolved.append(root / "User" / "workspaceStorage")
            resolved.append(root / "workspaceStorage")
        return _dedupe_paths(resolved)

    def is_available(self) -> bool:
        """Check if QCoder data is available."""
        # Check workspaceStorage directories
        if any(self._iter_session_files()):
            return True
        # Also check for state.vscdb files
        for workspace_dir in self._iter_workspace_dirs():
            state_db = workspace_dir / "state.vscdb"
            if state_db.exists():
                return True
        return False

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        """Iterate over raw session references from both JSONL and SQLite sources."""
        seen: set[str] = set()
        workspaces_with_chat_files: set[str] = set()

        for session_file, workspace_dir in self._iter_session_files():
            session_id = session_file.stem
            if session_id in seen:
                continue
            start_time = self._read_session_start_time(session_file)
            source_paths = [session_file]
            workspace_json = workspace_dir / "workspace.json"
            if workspace_json.exists():
                source_paths.append(workspace_json)
            seen.add(session_id)
            workspaces_with_chat_files.add(str(workspace_dir).lower())
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=source_paths,
                source_mtime=_max_mtime(source_paths),
            )

        for workspace_dir in self._iter_workspace_dirs():
            state_db = workspace_dir / "state.vscdb"
            if not state_db.exists():
                continue
            workspace_key = str(workspace_dir).lower()
            if workspace_key in workspaces_with_chat_files:
                continue
            session_id = workspace_dir.name
            if session_id in seen:
                continue
            from .base import get_vscdb_mtime
            source_mtime = get_vscdb_mtime(state_db)
            try:
                start_time = datetime.fromtimestamp(
                    source_mtime,
                    tz=timezone.utc,
                )
            except Exception:
                start_time = datetime.now(timezone.utc)
            source_paths = [state_db]
            workspace_json = workspace_dir / "workspace.json"
            if workspace_json.exists():
                source_paths.append(workspace_json)
            seen.add(session_id)
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=source_paths,
                source_mtime=source_mtime,
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        """Parse a single session from raw reference."""
        source_file = raw.source_paths[0]

        if source_file.suffix.lower() in (".json", ".jsonl"):
            return self._enrich_workspace_session(super().parse_session(raw))
        if source_file.name == "state.vscdb":
            return self._parse_state_db(raw, source_file)
        return self._create_minimal_session(raw)

    @staticmethod
    def _enrich_workspace_session(record: SessionRecord) -> SessionRecord:
        """Fill orchestration counters that WorkspaceStorageChatAdapter leaves at zero."""
        tool_counts = record.tool_counts or {}
        subagent_count = sum(tool_counts.get(name, 0) for name in SUBAGENT_TOOL_NAMES)
        if record.uses_subagent and subagent_count == 0:
            subagent_count = 1
        if subagent_count == record.subagent_invocation_count:
            return record
        return replace(record, subagent_invocation_count=subagent_count)

    def _parse_state_db(self, raw: SessionRef, state_db: Path) -> SessionRecord:
        """Parse session data from state.vscdb with full feature extraction."""
        tool_counts: Counter[str] = Counter()
        file_paths: set[str] = set()
        languages: Counter[str] = Counter()
        user_message_count = 0
        assistant_message_count = 0
        first_prompt = ""
        top_user_messages: list[str] = []
        uses_subagent = False
        uses_mcp = False
        uses_web_search = False
        uses_web_fetch = False
        subagent_invocation_count = 0
        skill_invocation_count = 0
        unique_skills: set[str] = set()
        unique_skills_from_attach: set[str] = set()
        skill_files_authored: set[str] = set()
        hook_config_modified = False
        mcp_server_authored = False
        chain_lengths: list[int] = []
        has_verification = False
        has_test_commands = False
        current_chain = 0
        pending_write = False
        shell_commands: list[str] = []

        try:
            stat = state_db.stat()
            end_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            end_ts = raw.start_time
        start_ts = raw.start_time

        with sqlite3.connect(state_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Extract input history (user messages)
            input_history = self._extract_input_history(cursor)
            
            for input_item in input_history:
                user_message_count += 1
                input_text = input_item.get("inputText", "")
                
                if not first_prompt:
                    first_prompt = input_text[:500]
                
                if len(top_user_messages) < 5:
                    top_user_messages.append(input_text[:300])

                # Check for skill attachments
                _has_skill_attach = (
                    "manually_attached_skills" in input_text.lower()
                    or "<agent_skill" in input_text
                    or "<available_skills" in input_text
                )
                if _has_skill_attach:
                    skill_invocation_count += 1
                    for _fp in re.findall(
                        r'<agent_skill[^>]+fullPath=["\']([^"\']+)["\']', input_text
                    ):
                        _folder = Path(_fp).parent.name
                        if _folder and _folder not in ("", ".", "skills", "skills-cursor"):
                            unique_skills_from_attach.add(_folder)
                    if not unique_skills_from_attach:
                        for _desc in re.findall(
                            r'<agent_skill[^>]*>([^<]{5,100})</agent_skill>', input_text
                        ):
                            _desc = _desc.strip()
                            if _desc:
                                unique_skills_from_attach.add(_desc[:60])
                    if unique_skills_from_attach:
                        skill_files_authored.add("__attached_skills__")
                
                # Extract file paths from parsedQuery
                parsed_query = input_item.get("parsedQuery", [])
                for query_item in parsed_query:
                    if isinstance(query_item, dict):
                        path = query_item.get("folderPath") or query_item.get("relatePath")
                        if path:
                            file_paths.add(path)
                            lang = detect_language(path)
                            if lang:
                                languages[lang] += 1
                            authorship = detect_authorship_path(path, self.asset_roots)
                            if authorship == "skill":
                                skill_files_authored.add(path)
                            elif authorship == "hook":
                                hook_config_modified = True
                            elif authorship == "mcp":
                                mcp_server_authored = True

            # Extract model information
            models_used = self._extract_models_from_vscdb(cursor)

            # Extract session metadata
            session_metadata = self._extract_session_metadata(cursor)
            current_session_id = session_metadata.get("currentSessionId", "")

            # Extract workspace path
            project_path = self._extract_project_path(cursor)
            if not project_path and file_paths:
                project_path = _common_prefix_path(list(file_paths))

            # Detect tool usage patterns from input text
            for input_item in input_history:
                input_text = input_item.get("inputText", "")
                # Check for subagent usage
                if any(tool in input_text.lower() for tool in SUBAGENT_TOOL_NAMES) or "task" in input_text.lower():
                    uses_subagent = True
                    subagent_invocation_count += 1
                # Check for MCP usage
                if "mcp" in input_text.lower():
                    uses_mcp = True
                # Check for web search
                if "web_search" in input_text.lower() or "websearch" in input_text.lower():
                    uses_web_search = True
                # Check for web fetch
                if "web_fetch" in input_text.lower() or "fetch" in input_text.lower():
                    uses_web_fetch = True
                # Check for test commands
                if any(pattern in input_text.lower() for pattern in TEST_PATTERNS):
                    has_test_commands = True

            # Count tool-like actions
            tool_counts["write"] = len(file_paths)
            if uses_subagent:
                tool_counts["subagent"] = subagent_invocation_count
            if uses_mcp:
                tool_counts["mcp"] = 1
            if uses_web_search:
                tool_counts["web_search"] = 1
            if uses_web_fetch:
                tool_counts["web_fetch"] = 1

        duration_minutes = max(int((end_ts - start_ts).total_seconds() // 60), 0)

        return SessionRecord(
            session_id=current_session_id or raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path,
            start_time=start_ts.isoformat(),
            end_time=end_ts.isoformat(),
            duration_minutes=duration_minutes,
            first_prompt=first_prompt,
            user_message_count=user_message_count,
            assistant_message_count=assistant_message_count,
            tool_counts=dict(tool_counts),
            tool_tier_counts=compute_tier_counts(dict(tool_counts)),
            files_modified=len(file_paths),
            languages=dict(languages),
            models_used=models_used,
            uses_subagent=uses_subagent,
            uses_mcp=uses_mcp,
            uses_web_search=uses_web_search,
            uses_web_fetch=uses_web_fetch,
            top_user_messages=top_user_messages,
            autonomous_chain_lengths=chain_lengths,
            has_verification_behavior=has_verification,
            has_test_commands=has_test_commands,
            skill_invocation_count=skill_invocation_count,
            unique_skills_used=sorted(unique_skills_from_attach | unique_skills),
            subagent_invocation_count=subagent_invocation_count,
            skill_files_authored=len(skill_files_authored),
            hook_config_modified=hook_config_modified,
            mcp_server_authored=mcp_server_authored,
            entrypoint="ide",
        )

    def _create_minimal_session(self, raw: SessionRef) -> SessionRecord:
        """Create a minimal session record when parsing fails."""
        return SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path="",
            start_time=raw.start_time.isoformat(),
            end_time=raw.start_time.isoformat(),
            duration_minutes=0,
            first_prompt="",
            user_message_count=0,
            assistant_message_count=0,
            tool_counts={},
            tool_tier_counts={},
            files_modified=0,
            languages={},
            models_used=[],
            uses_subagent=False,
            uses_mcp=False,
            uses_web_search=False,
            uses_web_fetch=False,
        )

    def _extract_project_path(self, cursor: sqlite3.Cursor) -> str:
        """Extract project path from workspace.json."""
        try:
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'workspace.json'")
            row = cursor.fetchone()
            if row:
                value = row[0]
                if isinstance(value, str):
                    data = json.loads(value)
                    folder = data.get("folder", "")
                    if folder.startswith("file:///"):
                        folder = folder[8:]
                    return folder
        except Exception:
            pass
        return ""

    def _extract_input_history(self, cursor: sqlite3.Cursor) -> list[dict]:
        """Extract input history from state.vscdb."""
        try:
            cursor.execute("SELECT value FROM ItemTable WHERE key LIKE '%input-history%'")
            row = cursor.fetchone()
            if row:
                value = row[0]
                if isinstance(value, str):
                    data = json.loads(value)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []

    def _extract_models_from_vscdb(self, cursor: sqlite3.Cursor) -> list[str]:
        """Extract model information from state.vscdb."""
        models: set[str] = set()
        try:
            cursor.execute("SELECT value FROM ItemTable WHERE key LIKE '%modelMap%'")
            row = cursor.fetchone()
            if row:
                value = row[0]
                if isinstance(value, str):
                    data = json.loads(value)
                    if isinstance(data, dict):
                        for session_data in data.values():
                            if isinstance(session_data, dict):
                                model = session_data.get("model")
                                if isinstance(model, str) and model.strip():
                                    models.add(model.strip().replace("_", "-"))
                                else:
                                    for item in session_data.values():
                                        if isinstance(item, str) and item.strip():
                                            models.add(item.strip().replace("_", "-"))
        except Exception:
            pass
        return sorted(models)

    def _extract_session_metadata(self, cursor: sqlite3.Cursor) -> dict:
        """Extract session metadata from state.vscdb."""
        try:
            cursor.execute("SELECT value FROM ItemTable WHERE key LIKE '%ai-agent-storage%' AND key NOT LIKE '%input-history%'")
            row = cursor.fetchone()
            if row:
                value = row[0]
                if isinstance(value, str):
                    data = json.loads(value)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}


