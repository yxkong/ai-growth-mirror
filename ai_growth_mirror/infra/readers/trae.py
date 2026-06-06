"""Adapter for Trae CN local workspaceStorage chat sessions."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ...domain.session.model import SessionRef, SessionRecord
from ...domain.signals.tooling import compute_tier_counts
from .base import (
    SUBAGENT_TOOL_NAMES,
    TEST_PATTERNS,
    _common_prefix_path,
    _max_mtime,
    detect_authorship_path,
    detect_language,
    parse_ts,
)
from .workspace_storage import WorkspaceStorageChatAdapter, appdata_path


class TraeAdapter(WorkspaceStorageChatAdapter):
    tool_name = "trae"
    display_name = "Trae"
    default_data_root = Path.home() / ".trae-cn"

    def extra_storage_roots(self) -> list[Path]:
        return [
            Path.home() / ".trae-cn",
            appdata_path("Trae CN"),
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

    @staticmethod
    def _uses_default_data_root(data_roots: list[Path], default_data_root: Path) -> bool:
        return len(data_roots) == 1 and data_roots[0] == default_data_root

    def _ai_agent_db_path(self) -> Optional[Path]:
        if not self._uses_default_data_root(self.data_roots, self.default_data_root):
            return None
        db_path = appdata_path("Trae CN") / "ModularData" / "ai-agent" / "database.db"
        return db_path if db_path.exists() else None

    def is_available(self) -> bool:
        if self._ai_agent_db_path() is not None:
            return True
        if any(self._iter_session_files()):
            return True
        for workspace_dir in self._iter_workspace_dirs():
            if (workspace_dir / "state.vscdb").exists():
                return True
        return False

    def _iter_ai_agent_sessions(self, seen: set[str]) -> Iterator[SessionRef]:
        db_path = self._ai_agent_db_path()
        if db_path is None:
            return
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND (name LIKE '%session%' OR name LIKE '%conversation%')"
                )
                tables = [row[0] for row in cursor.fetchall()]
                for table in tables:
                    try:
                        rows = conn.execute(f"SELECT * FROM {table} LIMIT 100").fetchall()
                    except sqlite3.Error:
                        continue
                    for row in rows:
                        keys = row.keys()
                        session_id = str(
                            row["id"]
                            if "id" in keys
                            else row["session_id"]
                            if "session_id" in keys
                            else row["conversation_id"]
                            if "conversation_id" in keys
                            else ""
                        )
                        if not session_id or session_id in seen:
                            continue
                        timestamp = None
                        for key in ("created_at", "timestamp", "updated_at"):
                            if key in keys:
                                timestamp = row[key]
                                break
                        if timestamp:
                            try:
                                start_time = parse_ts(timestamp)
                            except Exception:
                                start_time = datetime.now(timezone.utc)
                        else:
                            start_time = datetime.now(timezone.utc)
                        seen.add(session_id)
                        yield SessionRef(
                            session_id=session_id,
                            tool_name=self.tool_name,
                            start_time=start_time,
                            source_paths=[db_path],
                            source_mtime=_max_mtime([db_path]),
                        )
        except sqlite3.Error:
            return

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        """Iterate JSONL, state.vscdb, and (on default root) ai-agent DB sessions."""
        seen: set[str] = set()
        workspaces_with_chat_files: set[str] = set()

        yield from self._iter_ai_agent_sessions(seen)

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
        source_file = raw.source_paths[0]

        if source_file.suffix.lower() in (".json", ".jsonl"):
            return self._enrich_workspace_session(super().parse_session(raw))
        if source_file.name == "state.vscdb":
            return self._parse_state_db(raw, source_file)
        if source_file.name == "database.db":
            return self._create_minimal_session(raw)
        return self._create_minimal_session(raw)

    @staticmethod
    def _enrich_workspace_session(record: SessionRecord) -> SessionRecord:
        tool_counts = record.tool_counts or {}
        subagent_count = sum(tool_counts.get(name, 0) for name in SUBAGENT_TOOL_NAMES)
        if record.uses_subagent and subagent_count == 0:
            subagent_count = 1
        if subagent_count == record.subagent_invocation_count:
            return record
        return replace(record, subagent_invocation_count=subagent_count)

    def _parse_state_db(self, raw: SessionRef, state_db: Path) -> SessionRecord:
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

        try:
            stat = state_db.stat()
            end_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            end_ts = raw.start_time
        start_ts = raw.start_time

        with sqlite3.connect(state_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            input_history = self._extract_input_history(cursor)

            for input_item in input_history:
                user_message_count += 1
                input_text = input_item.get("inputText", "")

                if not first_prompt:
                    first_prompt = input_text[:500]

                if len(top_user_messages) < 5:
                    top_user_messages.append(input_text[:300])

                if (
                    "manually_attached_skills" in input_text.lower()
                    or "<agent_skill" in input_text
                    or "<available_skills" in input_text
                ):
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

            models_used = self._extract_models_from_vscdb(cursor)
            session_metadata = self._extract_session_metadata(cursor)
            current_session_id = session_metadata.get("currentSessionId", "")
            project_path = self._extract_project_path(cursor)
            if not project_path and file_paths:
                project_path = _common_prefix_path(list(file_paths))

            for input_item in input_history:
                input_text = input_item.get("inputText", "")
                if any(tool in input_text.lower() for tool in SUBAGENT_TOOL_NAMES) or "task" in input_text.lower():
                    uses_subagent = True
                    subagent_invocation_count += 1
                if "mcp" in input_text.lower():
                    uses_mcp = True
                if "web_search" in input_text.lower() or "websearch" in input_text.lower():
                    uses_web_search = True
                if "web_fetch" in input_text.lower() or "fetch" in input_text.lower():
                    uses_web_fetch = True
                if any(pattern in input_text.lower() for pattern in TEST_PATTERNS):
                    has_test_commands = True

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
        try:
            cursor.execute(
                "SELECT value FROM ItemTable WHERE key LIKE '%ai-agent-storage%' "
                "AND key NOT LIKE '%input-history%'"
            )
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


