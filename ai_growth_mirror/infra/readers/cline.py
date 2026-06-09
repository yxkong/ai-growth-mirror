"""Adapter for Cline (VS Code extension) task history.

Cline persists each coding task under a task directory with Anthropic-style
``api_conversation_history.json``. Newer builds use shared file storage::

    ~/.cline/data/tasks/<task-id>/api_conversation_history.json
    ~/.cline/data/state/taskHistory.json

Legacy VS Code global storage (pre file-backed migration)::

    %APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/<task-id>/
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ...domain.session.model import SessionRef, SessionRecord
from ...domain.signals.tooling import compute_tier_counts
from .base import (
    BaseSessionAdapter,
    EXEC_TOOL_NAMES,
    SKILL_READ_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    _max_mtime,
    detect_language,
    extract_skill_name_from_path,
    is_validation_command,
    parse_ts,
)
from .workspace_storage import appdata_path

_API_HISTORY = "api_conversation_history.json"
_UI_MESSAGES = "ui_messages.json"
_TASK_METADATA = "task_metadata.json"
_TASK_HISTORY = Path("state") / "taskHistory.json"

_PATH_INPUT_KEYS = (
    "path",
    "file_path",
    "filePath",
    "target_file",
    "notebook_path",
    "AbsolutePath",
)
_CLINE_EXTENSION_IDS = (
    "saoudrizwan.claude-dev",
    "saoudrizwan.cline",
)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _message_timestamp_ms(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            seconds = raw / 1000.0 if raw > 1_000_000_000_000 else float(raw)
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        return parse_ts(raw)
    except Exception:
        return None


def _path_from_tool_input(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for key in _PATH_INPUT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _command_from_tool_input(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd", "CommandLine"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_user_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text = part.get("text", "")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())
                elif isinstance(part, str) and part.strip():
                    chunks.append(part.strip())
            elif isinstance(part, str) and part.strip():
                chunks.append(part.strip())
        return "\n".join(chunks).strip()
    return ""


class ClineFamilyTaskAdapter(BaseSessionAdapter):
    """Shared adapter for Cline-lineage VS Code agents (Cline, Kilo Code, …)."""

    extension_ids: tuple[str, ...] = _CLINE_EXTENSION_IDS

    def _resolved_roots(self) -> list[Path]:
        from .workspace_storage import _dedupe_paths

        candidates = list(self.data_roots)
        if len(candidates) == 1 and candidates[0] == self.default_data_root:
            candidates.extend(self._legacy_global_storage_roots())
        return _dedupe_paths(candidates)

    @classmethod
    def _legacy_global_storage_roots(cls) -> list[Path]:
        roots: list[Path] = []
        app_roots = (
            appdata_path("Code"),
            appdata_path("Cursor"),
            appdata_path("VSCodium"),
            appdata_path("Windsurf"),
        )
        for app_root in app_roots:
            base = app_root / "User" / "globalStorage"
            if not base.exists():
                continue
            for ext_id in cls.extension_ids:
                candidate = base / ext_id
                if candidate.exists():
                    roots.append(candidate)
        if os.name != "nt":
            for ext_id in cls.extension_ids:
                for config_dir in (
                    Path.home() / ".config" / "Code",
                    Path.home() / ".config" / "Cursor",
                ):
                    candidate = config_dir / "User" / "globalStorage" / ext_id
                    if candidate.exists():
                        roots.append(candidate)
        return roots

    def _task_history_map(self, root: Path) -> dict[str, dict[str, Any]]:
        history_path = root / _TASK_HISTORY
        payload = _load_json(history_path)
        if not isinstance(payload, list):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            task_id = item.get("id")
            if isinstance(task_id, str) and task_id:
                result[task_id] = item
        return result

    def _iter_task_dirs(self, root: Path) -> Iterator[Path]:
        tasks_dir = root / "tasks"
        if not tasks_dir.exists():
            return
        for child in sorted(tasks_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if (child / _API_HISTORY).exists() or (child / _UI_MESSAGES).exists():
                yield child

    def is_available(self) -> bool:
        for root in self._resolved_roots():
            if any(True for _ in self._iter_task_dirs(root)):
                return True
        return False

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        seen: set[str] = set()
        for root in self._resolved_roots():
            history_map = self._task_history_map(root)
            for task_dir in self._iter_task_dirs(root):
                task_id = task_dir.name
                if task_id in seen:
                    continue
                source_paths = [
                    path
                    for path in (
                        task_dir / _API_HISTORY,
                        task_dir / _UI_MESSAGES,
                        task_dir / _TASK_METADATA,
                    )
                    if path.exists()
                ]
                if not source_paths:
                    continue
                history_item = history_map.get(task_id, {})
                start_time = self._task_start_time(task_dir, history_item, source_paths[0])
                seen.add(task_id)
                yield SessionRef(
                    session_id=task_id,
                    tool_name=self.tool_name,
                    start_time=start_time,
                    source_paths=source_paths,
                    source_mtime=_max_mtime(source_paths),
                )

    @staticmethod
    def _task_start_time(
        task_dir: Path,
        history_item: dict[str, Any],
        primary_source: Path,
    ) -> datetime:
        for key in ("ts", "timestamp", "createdAt", "created_at"):
            ts = _message_timestamp_ms(history_item.get(key))
            if ts is not None:
                return ts
        api_history = _load_json(task_dir / _API_HISTORY)
        if isinstance(api_history, list):
            for message in api_history:
                if isinstance(message, dict):
                    ts = _message_timestamp_ms(message.get("ts"))
                    if ts is not None:
                        return ts
        try:
            return datetime.fromtimestamp(primary_source.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return datetime.now(timezone.utc)

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        task_dir = raw.source_paths[0].parent
        root = self._locate_storage_root(task_dir)
        history_item = self._task_history_map(root).get(raw.session_id, {}) if root else {}

        api_path = next((p for p in raw.source_paths if p.name == _API_HISTORY), None)
        ui_path = next((p for p in raw.source_paths if p.name == _UI_MESSAGES), None)
        metadata_path = next((p for p in raw.source_paths if p.name == _TASK_METADATA), None)

        if api_path is not None:
            record = self._parse_api_history(raw, api_path, history_item)
        elif ui_path is not None:
            record = self._parse_ui_messages(raw, ui_path, history_item)
        else:
            record = self._minimal_session(raw, history_item)

        if metadata_path is not None:
            self._apply_task_metadata(record, metadata_path)
        self._apply_history_item(record, history_item)
        return record

    @staticmethod
    def _locate_storage_root(task_dir: Path) -> Optional[Path]:
        for parent in (task_dir.parent, task_dir.parent.parent):
            if (parent / "state").exists() or (parent / "tasks").exists():
                return parent
        return task_dir.parent if task_dir.parent.name == "tasks" else None

    def _parse_api_history(
        self,
        raw: SessionRef,
        api_path: Path,
        history_item: dict[str, Any],
    ) -> SessionRecord:
        payload = _load_json(api_path)
        messages = payload if isinstance(payload, list) else []

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
        models_used: list[str] = []
        user_message_timestamps: list[str] = []
        message_hours: list[int] = []
        chain_lengths: list[int] = []
        has_verification = False
        has_test_commands = False
        current_chain = 0
        pending_write = False
        last_timestamp: Optional[datetime] = None
        skill_invocation_count = 0
        unique_skills: set[str] = set()
        turns_until_first_file_write = None

        for message in messages:
            if not isinstance(message, dict):
                continue
            ts = _message_timestamp_ms(message.get("ts"))
            if ts is not None:
                last_timestamp = ts

            role = str(message.get("role", "")).lower()
            if role == "user":
                user_text = _extract_user_text(message.get("content"))
                if user_text:
                    user_message_count += 1
                    if not first_prompt:
                        first_prompt = user_text[:500]
                    if len(top_user_messages) < 5:
                        top_user_messages.append(user_text[:300])
                    if ts is not None:
                        user_message_timestamps.append(ts.isoformat())
                        message_hours.append(ts.astimezone().hour)
                if current_chain:
                    chain_lengths.append(current_chain)
                    current_chain = 0
                pending_write = False
                continue

            if role != "assistant":
                continue

            assistant_message_count += 1
            model_info = message.get("modelInfo")
            if isinstance(model_info, dict):
                model_id = model_info.get("modelId") or model_info.get("model")
                if isinstance(model_id, str) and model_id and model_id not in models_used:
                    models_used.append(model_id)

            content = message.get("content", [])
            if isinstance(content, str):
                continue
            if not isinstance(content, list):
                continue

            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "tool_use":
                    continue

                tool_name = str(part.get("name", "")).strip()
                if not tool_name:
                    continue
                normalized = tool_name.lower()
                tool_counts[normalized] += 1

                tool_input = part.get("input", {})
                file_path = _path_from_tool_input(tool_input)
                if file_path:
                    file_paths.add(file_path)
                    lang = detect_language(file_path)
                    if lang:
                        languages[lang] += 1

                command = _command_from_tool_input(tool_input)
                command_lower = command.lower()
                if command and is_validation_command(command_lower):
                    has_test_commands = True

                if normalized in SUBAGENT_TOOL_NAMES or "new_task" in normalized:
                    uses_subagent = True
                if "mcp" in normalized:
                    uses_mcp = True
                if "web_search" in normalized or "browser" in normalized:
                    uses_web_search = True
                if "web_fetch" in normalized or "fetch" in normalized:
                    uses_web_fetch = True
                # Skill fingerprint: agent read a SKILL.md from a skill folder
                if file_path and normalized in SKILL_READ_TOOL_NAMES:
                    skill_name = extract_skill_name_from_path(file_path)
                    if skill_name:
                        unique_skills.add(skill_name)
                        skill_invocation_count += 1

                if normalized in WRITE_TOOL_NAMES or any(
                    token in normalized for token in ("write", "replace", "edit")
                ):
                    pending_write = True
                    current_chain += 1
                    if turns_until_first_file_write is None:
                        turns_until_first_file_write = max(1, user_message_count)
                elif normalized in EXEC_TOOL_NAMES or "command" in normalized:
                    if pending_write:
                        has_verification = True
                    current_chain += 1
                    pending_write = False

        if current_chain:
            chain_lengths.append(current_chain)

        end_time = (
            last_timestamp.isoformat()
            if last_timestamp is not None
            else self._file_mtime_iso(api_path)
        )
        tool_count_dict = dict(tool_counts)
        project_path = str(history_item.get("cwd") or history_item.get("workspace") or "")

        return SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path if isinstance(project_path, str) else "",
            git_branch=None,
            start_time=raw.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=self._duration_minutes(raw.start_time, end_time),
            first_prompt=first_prompt,
            user_message_count=user_message_count,
            assistant_message_count=assistant_message_count,
            tool_counts=tool_count_dict,
            tool_tier_counts=compute_tier_counts(tool_count_dict),
            files_modified=len(file_paths),
            languages=dict(languages),
            top_user_messages=top_user_messages,
            uses_subagent=uses_subagent,
            uses_mcp=uses_mcp,
            uses_web_search=uses_web_search,
            uses_web_fetch=uses_web_fetch,
            models_used=models_used,
            user_message_timestamps=user_message_timestamps,
            message_hours=message_hours,
            has_verification_behavior=has_verification,
            has_test_commands=has_test_commands,
            autonomous_chain_lengths=chain_lengths,
            skill_invocation_count=skill_invocation_count,
            unique_skills_used=sorted(unique_skills),
            turns_until_first_file_write=turns_until_first_file_write,
        )

    def _parse_ui_messages(
        self,
        raw: SessionRef,
        ui_path: Path,
        history_item: dict[str, Any],
    ) -> SessionRecord:
        payload = _load_json(ui_path)
        messages = payload if isinstance(payload, list) else []

        user_message_count = 0
        assistant_message_count = 0
        first_prompt = ""
        top_user_messages: list[str] = []
        tool_counts: Counter[str] = Counter()
        last_timestamp: Optional[datetime] = None

        for message in messages:
            if not isinstance(message, dict):
                continue
            ts = _message_timestamp_ms(message.get("ts"))
            if ts is not None:
                last_timestamp = ts
            say = str(message.get("say", "")).lower()
            ask = str(message.get("ask", "")).lower()
            text = str(message.get("text", "")).strip()
            if ask == "tool" and isinstance(message.get("tool"), str):
                tool_counts[message["tool"].strip().lower()] += 1
            if say == "user_feedback" or ask in {"followup", "completion_result"}:
                if text:
                    user_message_count += 1
                    if not first_prompt:
                        first_prompt = text[:500]
                    if len(top_user_messages) < 5:
                        top_user_messages.append(text[:300])
            elif text and say not in {"", "error", "api_req_started"}:
                assistant_message_count += 1

        end_time = (
            last_timestamp.isoformat()
            if last_timestamp is not None
            else self._file_mtime_iso(ui_path)
        )
        tool_count_dict = dict(tool_counts)
        project_path = str(history_item.get("cwd") or "")

        return SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path if isinstance(project_path, str) else "",
            git_branch=None,
            start_time=raw.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=self._duration_minutes(raw.start_time, end_time),
            first_prompt=first_prompt,
            user_message_count=user_message_count,
            assistant_message_count=assistant_message_count,
            tool_counts=tool_count_dict,
            tool_tier_counts=compute_tier_counts(tool_count_dict),
            files_modified=0,
            languages={},
            top_user_messages=top_user_messages,
            uses_subagent=any(name in SUBAGENT_TOOL_NAMES for name in tool_count_dict),
            uses_mcp=any("mcp" in name for name in tool_count_dict),
            models_used=[],
        )

    def _minimal_session(self, raw: SessionRef, history_item: dict[str, Any]) -> SessionRecord:
        project_path = str(history_item.get("cwd") or "")
        return SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path=project_path if isinstance(project_path, str) else "",
            start_time=raw.start_time.isoformat(),
            end_time=self._file_mtime_iso(raw.source_paths[0]),
            first_prompt=str(history_item.get("task") or "")[:500],
        )

    @staticmethod
    def _apply_task_metadata(record: SessionRecord, metadata_path: Path) -> None:
        payload = _load_json(metadata_path)
        if not isinstance(payload, dict):
            return
        if record.project_path:
            return
        for entry in payload.get("environment_history") or []:
            if not isinstance(entry, dict):
                continue
            cwd = entry.get("cwd") or entry.get("workspacePath")
            if isinstance(cwd, str) and cwd.strip():
                record.project_path = cwd.strip()
                return

    @staticmethod
    def _apply_history_item(record: SessionRecord, history_item: dict[str, Any]) -> None:
        if not record.project_path:
            cwd = history_item.get("cwd") or history_item.get("workspace")
            if isinstance(cwd, str) and cwd.strip():
                record.project_path = cwd.strip()
        if not record.first_prompt:
            task = history_item.get("task")
            if isinstance(task, str) and task.strip():
                record.first_prompt = task.strip()[:500]
        tokens_in = history_item.get("tokensIn")
        tokens_out = history_item.get("tokensOut")
        if isinstance(tokens_in, (int, float)) and tokens_in > 0:
            record.input_tokens = int(tokens_in)
        if isinstance(tokens_out, (int, float)) and tokens_out > 0:
            record.output_tokens = int(tokens_out)

    @staticmethod
    def _file_mtime_iso(path: Path) -> Optional[str]:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            return None

    @staticmethod
    def _duration_minutes(start_time: datetime, end_time_iso: Optional[str]) -> Optional[int]:
        if not end_time_iso:
            return None
        try:
            from .base import parse_iso

            end_dt = parse_iso(end_time_iso)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return max(int((end_dt - start_time).total_seconds() // 60), 0)
        except Exception:
            return None


class ClineAdapter(ClineFamilyTaskAdapter):
    """Session adapter for Cline VS Code extension."""

    tool_name = "cline"
    display_name = "Cline"
    default_data_root = Path.home() / ".cline" / "data"
    extension_ids = _CLINE_EXTENSION_IDS
