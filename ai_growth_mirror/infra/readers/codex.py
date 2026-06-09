"""Reader for Codex rollout logs and thread metadata."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ...domain.growth.costs import estimate_cost
from ...domain.session.heuristics import (
    EXEC_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    is_validation_command,
)
from ...domain.session.model import SessionRecord, SessionRef
from ...domain.signals.tooling import compute_tier_counts
from .base import (
    BaseSessionAdapter,
    SKILL_READ_TOOL_NAMES,
    _max_mtime,
    detect_authorship_path,
    detect_language,
    extract_skill_name_from_path,
    parse_iso,
    parse_ts,
)


def _thread_first_prompt(thread: sqlite3.Row | None) -> str:
    if thread is None:
        return ""
    try:
        value = thread["first_user_message"]
    except Exception:
        return ""
    return value[:500] if value else ""


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _normalize_tool_name(raw_name: str) -> str:
    return (raw_name or "").strip().lower()


def _iter_text_fragments(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_text_fragments(item)
        return
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            yield text
        for key in ("content", "items"):
            if key in value:
                yield from _iter_text_fragments(value.get(key))


def _find_paths(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in {"path", "file", "filepath", "file_path", "target_file", "new_path", "old_path"}:
                if isinstance(nested, str):
                    yield nested
            else:
                yield from _find_paths(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _find_paths(item)


def _find_command(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("command", "cmd"):
            command = value.get(key)
            if isinstance(command, str):
                return command
        for nested in value.values():
            command = _find_command(nested)
            if command:
                return command
    elif isinstance(value, list):
        for item in value:
            command = _find_command(item)
            if command:
                return command
    return ""


def _message_timestamp(obj: dict[str, Any]) -> Optional[datetime]:
    for candidate in (
        obj.get("timestamp"),
        obj.get("created_at"),
        obj.get("ts"),
        (obj.get("payload") or {}).get("timestamp") if isinstance(obj.get("payload"), dict) else None,
    ):
        if not candidate:
            continue
        try:
            parsed = parse_ts(candidate)
        except Exception:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


@dataclass
class _RolloutAccumulator:
    session_id: str
    tool_name: str
    start_time: datetime
    project_path: str = ""
    first_prompt: str = ""
    top_user_messages: list[str] = field(default_factory=list)
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    files_modified: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    models_used: list[str] = field(default_factory=list)
    message_hours: list[int] = field(default_factory=list)
    user_message_timestamps: list[str] = field(default_factory=list)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    uses_subagent: bool = False
    uses_mcp: bool = False
    uses_web_search: bool = False
    uses_web_fetch: bool = False
    has_verification_behavior: bool = False
    has_test_commands: bool = False
    skill_files_authored: int = 0
    hook_config_modified: bool = False
    mcp_server_authored: bool = False
    subagent_invocation_count: int = 0
    skill_invocation_count: int = 0
    unique_skills_used: list[str] = field(default_factory=list)
    tool_errors: int = 0
    tool_error_categories: dict[str, int] = field(default_factory=dict)
    turns_until_first_file_write: Optional[int] = None
    _written_paths: set[str] = field(default_factory=set)
    _last_timestamp: Optional[datetime] = None
    _saw_write: bool = False
    _saw_exec: bool = False

    def add_user_message(self, text: str, timestamp: Optional[datetime]) -> None:
        clean = text.strip()
        if not clean:
            return
        self.user_message_count += 1
        if not self.first_prompt:
            self.first_prompt = clean[:500]
        if len(self.top_user_messages) < 10:
            self.top_user_messages.append(clean[:500])
        if timestamp is not None:
            self.user_message_timestamps.append(timestamp.isoformat())
            self.message_hours.append(timestamp.astimezone().hour)
            self._last_timestamp = timestamp

    def add_assistant_turn(self, timestamp: Optional[datetime]) -> None:
        self.assistant_message_count += 1
        if timestamp is not None:
            self._last_timestamp = timestamp

    def add_model(self, model: str) -> None:
        if model and model not in self.models_used:
            self.models_used.append(model)

    def add_tool_use(self, raw_name: str, payload: Any, *, asset_roots: tuple[Path, ...]) -> None:
        name = _normalize_tool_name(raw_name)
        if not name:
            return
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1
        if name in SUBAGENT_TOOL_NAMES or "task" in name or "subagent" in name:
            self.uses_subagent = True
            self.subagent_invocation_count += 1
        if "mcp" in name:
            self.uses_mcp = True
        if "web_search" in name or "search" == name:
            self.uses_web_search = True
        if "web_fetch" in name or "fetch" == name:
            self.uses_web_fetch = True

        if name in WRITE_TOOL_NAMES or any(token in name for token in ("edit", "write", "patch")):
            self._saw_write = True
            if self.turns_until_first_file_write is None:
                self.turns_until_first_file_write = max(1, self.user_message_count)
        if name in EXEC_TOOL_NAMES or any(token in name for token in ("bash", "shell", "command", "exec")):
            self._saw_exec = True
            command = _find_command(payload).lower()
            if is_validation_command(command):
                self.has_test_commands = True

        is_read_tool = name in SKILL_READ_TOOL_NAMES
        for path in _find_paths(payload):
            if path not in self._written_paths:
                self._written_paths.add(path)
                self.files_modified = len(self._written_paths)
            if is_read_tool:
                skill_name = extract_skill_name_from_path(path)
                if skill_name:
                    self.skill_invocation_count += 1
                    if skill_name not in self.unique_skills_used:
                        self.unique_skills_used.append(skill_name)
            language = detect_language(path)
            if language:
                self.languages[language] = self.languages.get(language, 0) + 1
            authored_kind = detect_authorship_path(path, asset_roots)
            if authored_kind == "skill":
                self.skill_files_authored += 1
            elif authored_kind == "hook":
                self.hook_config_modified = True
            elif authored_kind == "mcp":
                self.mcp_server_authored = True

    def apply_token_totals(self, info: dict[str, Any]) -> None:
        total_usage = info.get("total_token_usage") if isinstance(info, dict) else None
        usage = total_usage if isinstance(total_usage, dict) else info
        if not isinstance(usage, dict):
            return
        self.input_tokens = usage.get("input_tokens", self.input_tokens)
        self.output_tokens = usage.get("output_tokens", self.output_tokens)
        self.cache_read_tokens = usage.get("cached_input_tokens", self.cache_read_tokens)
        self.cache_write_tokens = usage.get("cache_write_input_tokens", self.cache_write_tokens)

    def finalize(self) -> SessionRecord:
        end_time = self._last_timestamp.isoformat() if self._last_timestamp else None
        duration = None
        if self._last_timestamp is not None:
            duration = max(0, int((self._last_timestamp - self.start_time).total_seconds() / 60))
        record = SessionRecord(
            session_id=self.session_id,
            tool_name=self.tool_name,
            project_path=self.project_path,
            start_time=self.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=duration,
            first_prompt=self.first_prompt,
            user_message_count=self.user_message_count,
            assistant_message_count=self.assistant_message_count,
            tool_counts=self.tool_counts,
            tool_tier_counts=compute_tier_counts(self.tool_counts),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
            total_cost_usd=estimate_cost(
                self.input_tokens,
                self.output_tokens,
                self.cache_read_tokens,
                self.cache_write_tokens,
                self.models_used,
            ),
            files_modified=self.files_modified,
            languages=self.languages,
            message_hours=self.message_hours,
            user_message_timestamps=self.user_message_timestamps,
            uses_subagent=self.uses_subagent,
            uses_mcp=self.uses_mcp,
            uses_web_search=self.uses_web_search,
            uses_web_fetch=self.uses_web_fetch,
            models_used=self.models_used,
            top_user_messages=self.top_user_messages,
            has_verification_behavior=self._saw_write and self._saw_exec,
            has_test_commands=self.has_test_commands,
            skill_files_authored=self.skill_files_authored,
            hook_config_modified=self.hook_config_modified,
            mcp_server_authored=self.mcp_server_authored,
            subagent_invocation_count=self.subagent_invocation_count,
            skill_invocation_count=self.skill_invocation_count,
            unique_skills_used=self.unique_skills_used,
            tool_errors=self.tool_errors,
            tool_error_categories=self.tool_error_categories,
            turns_until_first_file_write=self.turns_until_first_file_write,
        )
        self._enrich(record)
        return record

    def _enrich(self, record: SessionRecord) -> None:
        BaseSessionAdapter._enrich_prompt_signals(record)
        BaseSessionAdapter._enrich_agentic_signals(record)


class CodexAdapter(BaseSessionAdapter):
    tool_name = "codex"
    display_name = "Codex CLI"
    default_data_root = Path.home() / ".codex"

    @property
    def _db_path(self) -> Path:
        return self.data_root / "state_5.sqlite"

    @property
    def _sessions_root(self) -> Path:
        return self.data_root / "sessions"

    def is_available(self) -> bool:
        return self._db_path.exists() or any(self._sessions_root.rglob("rollout-*.jsonl"))

    def _resolve_rollout_path(self, raw_path: str) -> Optional[Path]:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.data_root / candidate
        if candidate.exists():
            return candidate
        anchor = self.default_data_root.name
        parts = Path(raw_path).parts
        for index, part in enumerate(parts):
            if part == anchor:
                remapped = self.data_root / Path(*parts[index + 1 :])
                if remapped.exists():
                    return remapped
                break
        return None

    @staticmethod
    def _read_session_meta_extras(rollout_path: Path) -> tuple[str, Optional[str]]:
        for obj in _iter_jsonl(rollout_path):
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
            if obj.get("type") != "session_meta":
                continue
            cwd = payload.get("cwd") or obj.get("cwd") or ""
            model = payload.get("model") or obj.get("model")
            return cwd, model
        return "", None

    @staticmethod
    def _read_session_meta(rollout_path: Path) -> tuple[Optional[str], Optional[datetime]]:
        for obj in _iter_jsonl(rollout_path):
            if obj.get("type") != "session_meta":
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
            session_id = payload.get("id") or obj.get("id")
            raw_timestamp = (
                payload.get("timestamp")
                or obj.get("timestamp")
                or payload.get("created_at")
                or obj.get("created_at")
            )
            if not session_id or not raw_timestamp:
                return None, None
            try:
                timestamp = parse_iso(raw_timestamp)
            except Exception:
                return None, None
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return str(session_id), timestamp
        return None, None

    def _iter_filesystem_rollouts(self) -> Iterator[tuple[str, Path, datetime]]:
        for rollout in sorted(self._sessions_root.rglob("rollout-*.jsonl")):
            session_id, start_time = self._read_session_meta(rollout)
            if session_id and start_time:
                yield session_id, rollout, start_time

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        yielded: set[str] = set()
        if self._db_path.exists():
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    for row in conn.execute("SELECT * FROM threads"):
                        agent_role = str(row["agent_role"]).lower() if "agent_role" in row.keys() and row["agent_role"] is not None else ""
                        if agent_role and agent_role not in {"top_level", "primary", "main"}:
                            continue
                        rollout_path = None
                        for key in ("rollout_path", "path", "log_path"):
                            if key in row.keys() and row[key]:
                                rollout_path = self._resolve_rollout_path(str(row[key]))
                                if rollout_path is not None:
                                    break
                        if rollout_path is None:
                            continue
                        session_id = None
                        for key in ("id", "thread_id", "session_id"):
                            if key in row.keys() and row[key]:
                                session_id = str(row[key])
                                break
                        start_time = None
                        for key in ("created_at", "timestamp", "started_at"):
                            if key in row.keys() and row[key]:
                                try:
                                    start_time = parse_ts(row[key])
                                except Exception:
                                    start_time = None
                                if start_time is not None:
                                    break
                        if session_id is None or start_time is None:
                            session_id, start_time = self._read_session_meta(rollout_path)
                        if session_id is None or start_time is None or session_id in yielded:
                            continue
                        yielded.add(session_id)
                        yield SessionRef(
                            session_id=session_id,
                            tool_name=self.tool_name,
                            start_time=start_time,
                            source_paths=[rollout_path],
                            source_mtime=_max_mtime([rollout_path]),
                        )
            except sqlite3.Error:
                pass

        for session_id, rollout_path, start_time in self._iter_filesystem_rollouts():
            if session_id in yielded:
                continue
            yielded.add(session_id)
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=[rollout_path],
                source_mtime=_max_mtime([rollout_path]),
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        rollout_path = raw.source_paths[0]
        return self._parse_rollout(raw.session_id, rollout_path, raw.start_time)

    def _parse_rollout(self, session_id: str, rollout_path: Path, start_time: datetime) -> SessionRecord:
        cwd, initial_model = self._read_session_meta_extras(rollout_path)
        state = _RolloutAccumulator(
            session_id=session_id,
            tool_name=self.tool_name,
            start_time=start_time,
            project_path=cwd,
        )
        if initial_model:
            state.add_model(initial_model)

        for obj in _iter_jsonl(rollout_path):
            timestamp = _message_timestamp(obj)
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
            if obj.get("type") == "session_meta":
                if not state.project_path:
                    state.project_path = payload.get("cwd") or obj.get("cwd") or ""
                state.add_model(payload.get("model") or obj.get("model") or "")
                continue

            if obj.get("type") == "event_msg":
                info = payload.get("info") if isinstance(payload.get("info"), dict) else payload
                if payload.get("type") == "token_count" or "total_token_usage" in info:
                    state.apply_token_totals(info)
                continue

            if obj.get("type") != "response_item":
                continue

            item_type = payload.get("type")
            if item_type == "message":
                role = payload.get("role")
                if role == "user":
                    text = " ".join(_iter_text_fragments(payload.get("content")))
                    state.add_user_message(text, timestamp)
                elif role == "assistant":
                    state.add_assistant_turn(timestamp)
                    for content in payload.get("content", []):
                        if not isinstance(content, dict):
                            continue
                        if content.get("type") != "tool_use":
                            continue
                        state.add_tool_use(content.get("name", ""), content.get("input"), asset_roots=self.asset_roots)
                continue

            if item_type in {"tool_call", "function_call"}:
                state.add_assistant_turn(timestamp)
                tool_name = payload.get("name") or payload.get("tool_name") or ""
                tool_payload = payload.get("arguments") or payload.get("input") or payload
                state.add_tool_use(tool_name, tool_payload, asset_roots=self.asset_roots)

        return state.finalize()
