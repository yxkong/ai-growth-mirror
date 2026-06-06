"""Reader for Claude Code session logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ...domain.growth.costs import estimate_cost
from ...domain.session.heuristics import CONSTRAINT_WORDS, CODE_CONTEXT_PATTERNS, TEST_PATTERNS, WRITE_TOOL_NAMES
from ...domain.session.model import SessionRecord, SessionRef
from ...domain.signals.tooling import compute_tier_counts
from .base import (
    BaseSessionAdapter,
    SKILL_READ_TOOL_NAMES,
    detect_authorship_path,
    detect_language,
    extract_skill_name_from_path,
    parse_iso,
)

_SYSTEM_PREFIXES = (
    "<local-command-",
    "<command-name>",
    "<command-message>",
    "<command-stdout>",
    "<command-stderr>",
    "<command-args>",
    "<system-reminder>",
)
_COMMAND_NAME_RE = re.compile(r"<command-name>([^<]+)</command-name>", re.IGNORECASE)
_AUTO_COMPACT_RE = re.compile(r"auto-compact|auto compact|context compact", re.IGNORECASE)


def _utc_iso_to_local_iso(ts: str) -> str:
    if not ts:
        return ts
    try:
        parsed = parse_iso(ts)
    except Exception:
        return ts
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().isoformat()


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
        for key in ("content", "parts"):
            if key in value:
                yield from _iter_text_fragments(value.get(key))


def _find_paths(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {"path", "file", "filepath", "file_path", "target_file", "new_path", "old_path"}:
                if isinstance(nested, str):
                    yield nested
            else:
                yield from _find_paths(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _find_paths(item)


def _find_numeric(mapping: dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


@dataclass
class _ClaudeAccumulator:
    session_id: str
    start_time: datetime
    project_path: str = ""
    first_prompt: str = ""
    top_user_messages: list[str] = field(default_factory=list)
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    tool_error_categories: dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    files_modified: int = 0
    models_used: list[str] = field(default_factory=list)
    user_message_timestamps: list[str] = field(default_factory=list)
    message_hours: list[int] = field(default_factory=list)
    uses_subagent: bool = False
    uses_mcp: bool = False
    uses_web_search: bool = False
    uses_web_fetch: bool = False
    has_test_commands: bool = False
    entrypoint: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    unique_skills_used: list[str] = field(default_factory=list)
    skill_invocation_count: int = 0
    slash_commands: list[str] = field(default_factory=list)
    compact_count: int = 0
    auto_compact_count: int = 0
    skill_files_authored: int = 0
    hook_config_modified: bool = False
    mcp_server_authored: bool = False
    subagent_invocation_count: int = 0
    _seen_paths: set[str] = field(default_factory=set)
    _last_timestamp: Optional[datetime] = None
    _saw_write: bool = False
    _saw_exec: bool = False

    def set_project_path(self, value: str) -> None:
        if value and not self.project_path:
            self.project_path = value

    def add_model(self, value: str) -> None:
        if value and value not in self.models_used:
            self.models_used.append(value)

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

    def add_command(self, raw_text: str) -> None:
        match = _COMMAND_NAME_RE.search(raw_text)
        if not match:
            return
        command = "/" + match.group(1).strip().lstrip("/")
        self.slash_commands.append(command)
        if command == "/compact":
            self.compact_count += 1
        if _AUTO_COMPACT_RE.search(raw_text):
            self.auto_compact_count += 1

    def add_tool_use(self, name: str, payload: Any, *, asset_roots: tuple[Path, ...]) -> None:
        normalized = (name or "").strip().lower()
        if not normalized:
            return
        self.tool_counts[normalized] = self.tool_counts.get(normalized, 0) + 1
        if normalized in WRITE_TOOL_NAMES or any(token in normalized for token in ("edit", "write", "patch")):
            self._saw_write = True
        if any(token in normalized for token in ("bash", "shell", "command", "exec")):
            self._saw_exec = True
        if "mcp" in normalized:
            self.uses_mcp = True
        if "search" in normalized:
            self.uses_web_search = True
        if "fetch" in normalized or "browser" in normalized:
            self.uses_web_fetch = True
        if "task" in normalized or "subagent" in normalized or "agent" == normalized:
            self.uses_subagent = True
            self.subagent_invocation_count += 1
        if "skill" in normalized:
            self.skill_invocation_count += 1
            if normalized not in self.unique_skills_used:
                self.unique_skills_used.append(normalized)

        command = " ".join(_iter_text_fragments(payload)).lower()
        if any(pattern in command for pattern in TEST_PATTERNS):
            self.has_test_commands = True

        is_read_tool = normalized in SKILL_READ_TOOL_NAMES
        for path in _find_paths(payload):
            if path not in self._seen_paths:
                self._seen_paths.add(path)
                self.files_modified = len(self._seen_paths)
            if is_read_tool:
                skill_name = extract_skill_name_from_path(path)
                if skill_name:
                    self.skill_invocation_count += 1
                    if skill_name not in self.unique_skills_used:
                        self.unique_skills_used.append(skill_name)
            language = detect_language(path)
            if language:
                self.languages[language] = self.languages.get(language, 0) + 1
            authored = detect_authorship_path(path, asset_roots)
            if authored == "skill":
                self.skill_files_authored += 1
            elif authored == "hook":
                self.hook_config_modified = True
            elif authored == "mcp":
                self.mcp_server_authored = True

    def apply_usage(self, usage: dict[str, Any]) -> None:
        self.input_tokens = _find_numeric(usage, "input_tokens", "inputTokens") or self.input_tokens
        self.output_tokens = _find_numeric(usage, "output_tokens", "outputTokens") or self.output_tokens
        self.cache_read_tokens = (
            _find_numeric(usage, "cache_read_input_tokens", "cached_input_tokens", "cacheReadInputTokens")
            or self.cache_read_tokens
        )
        self.cache_write_tokens = (
            _find_numeric(usage, "cache_creation_input_tokens", "cache_write_input_tokens", "cacheWriteInputTokens")
            or self.cache_write_tokens
        )

    def finalize(self) -> SessionRecord:
        end_time = self._last_timestamp.isoformat() if self._last_timestamp else None
        duration = None
        if self._last_timestamp is not None:
            duration = max(0, int((self._last_timestamp - self.start_time).total_seconds() / 60))
        record = SessionRecord(
            session_id=self.session_id,
            tool_name="claude_code",
            project_path=self.project_path,
            start_time=self.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=duration,
            first_prompt=self.first_prompt,
            user_message_count=self.user_message_count,
            assistant_message_count=self.assistant_message_count,
            entrypoint=self.entrypoint,
            tool_counts=self.tool_counts,
            tool_tier_counts=compute_tier_counts(self.tool_counts),
            tool_errors=self.tool_errors,
            tool_error_categories=self.tool_error_categories,
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
            skill_invocation_count=self.skill_invocation_count,
            unique_skills_used=self.unique_skills_used,
            slash_commands=self.slash_commands,
            compact_count=self.compact_count,
            auto_compact_count=self.auto_compact_count,
            skill_files_authored=self.skill_files_authored,
            hook_config_modified=self.hook_config_modified,
            mcp_server_authored=self.mcp_server_authored,
            subagent_invocation_count=self.subagent_invocation_count,
        )
        BaseSessionAdapter._enrich_prompt_signals(record)
        BaseSessionAdapter._enrich_agentic_signals(record)
        return record


class ClaudeCodeSessionAdapter(BaseSessionAdapter):
    tool_name = "claude_code"
    display_name = "Claude Code"
    default_data_root = Path.home() / ".claude"
    _WRITE_TOOLS = frozenset({"write", "edit", "multiedit", "notebookedit"})
    _TEST_PATTERNS = TEST_PATTERNS
    _CONSTRAINT_WORDS = CONSTRAINT_WORDS
    _CODE_CONTEXT_PATTERNS = CODE_CONTEXT_PATTERNS

    def is_available(self) -> bool:
        return any((root / "projects").exists() for root in self.data_roots)

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        projects_dir = self.data_root / "projects"
        for jsonl_path in sorted(projects_dir.rglob("*.jsonl")):
            if "subagents" in jsonl_path.parts:
                continue
            start_time = self._read_start_time(jsonl_path)
            if start_time is None:
                continue
            try:
                source_mtime = jsonl_path.stat().st_mtime
            except OSError:
                source_mtime = 0.0
            yield SessionRef(
                session_id=jsonl_path.stem,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=[jsonl_path],
                source_mtime=source_mtime,
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        jsonl_path = raw.source_paths[0]
        meta_cache = self.data_root / "usage-data" / "session-meta" / f"{raw.session_id}.json"
        if not jsonl_path.exists() and meta_cache.exists():
            return self._from_claude_meta_cache(raw.session_id, meta_cache, jsonl_path)
        return self._parse_jsonl(raw.session_id, jsonl_path)

    def _read_start_time(self, jsonl_path: Path) -> Optional[datetime]:
        for obj in _iter_jsonl(jsonl_path):
            timestamp = obj.get("timestamp")
            if not timestamp:
                continue
            try:
                parsed = parse_iso(timestamp)
            except Exception:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        return None

    @staticmethod
    def _extract_user_text(obj: dict[str, Any]) -> str:
        return " ".join(_iter_text_fragments(obj.get("message") or obj.get("content") or obj))

    @staticmethod
    def _raw_user_text(obj: dict[str, Any]) -> str:
        return ClaudeCodeSessionAdapter._extract_user_text(obj)

    @staticmethod
    def _is_human_user_msg(obj: dict[str, Any]) -> bool:
        text = ClaudeCodeSessionAdapter._raw_user_text(obj).strip()
        return bool(text) and not any(text.startswith(prefix) for prefix in _SYSTEM_PREFIXES)

    def _read_token_data_from_jsonl(self, jsonl_path: Path) -> dict[str, Optional[int]]:
        usage: dict[str, Optional[int]] = {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }
        for obj in _iter_jsonl(jsonl_path):
            raw_usage = obj.get("usage") or obj.get("token_usage")
            if not isinstance(raw_usage, dict):
                continue
            usage["input_tokens"] = _find_numeric(raw_usage, "input_tokens", "inputTokens") or usage["input_tokens"]
            usage["output_tokens"] = _find_numeric(raw_usage, "output_tokens", "outputTokens") or usage["output_tokens"]
            usage["cache_read_tokens"] = (
                _find_numeric(raw_usage, "cache_read_input_tokens", "cached_input_tokens", "cacheReadInputTokens")
                or usage["cache_read_tokens"]
            )
            usage["cache_write_tokens"] = (
                _find_numeric(raw_usage, "cache_creation_input_tokens", "cacheWriteInputTokens")
                or usage["cache_write_tokens"]
            )
        return usage

    def _extract_agentic_signals(self, record: SessionRecord) -> None:
        BaseSessionAdapter._enrich_prompt_signals(record)
        BaseSessionAdapter._enrich_agentic_signals(record)

    def _read_agentic_signals_from_jsonl(self, jsonl_path: Path) -> tuple[int, int]:
        skill_calls = 0
        subagent_calls = 0
        for obj in _iter_jsonl(jsonl_path):
            if obj.get("type") != "assistant":
                continue
            message = obj.get("message") or {}
            for content in message.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "tool_use":
                    continue
                name = str(content.get("name", "")).lower()
                if "skill" in name:
                    skill_calls += 1
                if "task" in name or "subagent" in name or name == "agent":
                    subagent_calls += 1
        return skill_calls, subagent_calls

    def _read_all_user_messages(self, jsonl_path: Path) -> list[str]:
        messages: list[str] = []
        for obj in _iter_jsonl(jsonl_path):
            if obj.get("type") != "user":
                continue
            if not self._is_human_user_msg(obj):
                continue
            text = self._extract_user_text(obj).strip()
            if text:
                messages.append(text[:500])
        return messages

    def _collect_subagent_data(self, jsonl_path: Path) -> tuple[bool, int]:
        if "subagents" in jsonl_path.parts:
            return True, 1
        return False, 0

    def _from_claude_meta_cache(self, session_id: str, meta_cache: Path, jsonl_path: Path) -> SessionRecord:
        try:
            payload = json.loads(meta_cache.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        start_raw = payload.get("start_time") or payload.get("started_at") or payload.get("timestamp")
        try:
            start_time = parse_iso(start_raw) if start_raw else datetime.now(timezone.utc)
        except Exception:
            start_time = datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        state = _ClaudeAccumulator(session_id=session_id, start_time=start_time)
        state.set_project_path(payload.get("cwd") or payload.get("project_path") or "")
        state.entrypoint = str(payload.get("entrypoint") or "")
        for model in payload.get("models_used", []) or [payload.get("model")]:
            if isinstance(model, str):
                state.add_model(model)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
        if isinstance(usage, dict):
            state.apply_usage(usage)
        if jsonl_path.exists():
            parsed = self._parse_jsonl(session_id, jsonl_path)
            if parsed.input_tokens is None:
                parsed.input_tokens = state.input_tokens
                parsed.output_tokens = state.output_tokens
                parsed.cache_read_tokens = state.cache_read_tokens
                parsed.cache_write_tokens = state.cache_write_tokens
                parsed.total_cost_usd = estimate_cost(
                    parsed.input_tokens,
                    parsed.output_tokens,
                    parsed.cache_read_tokens,
                    parsed.cache_write_tokens,
                    parsed.models_used,
                )
            return parsed
        return state.finalize()

    def _parse_jsonl(self, session_id: str, jsonl_path: Path) -> SessionRecord:
        start_time = self._read_start_time(jsonl_path) or datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        state = _ClaudeAccumulator(session_id=session_id, start_time=start_time)

        for obj in _iter_jsonl(jsonl_path):
            timestamp = None
            if obj.get("timestamp"):
                try:
                    timestamp = parse_iso(obj["timestamp"])
                except Exception:
                    timestamp = None
                if timestamp is not None and timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

            obj_type = obj.get("type")
            if obj_type == "system":
                state.entrypoint = str(obj.get("entrypoint") or state.entrypoint)
                state.set_project_path(obj.get("cwd") or obj.get("project_path") or "")
                state.add_model(str(obj.get("model") or ""))
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    state.apply_usage(usage)
                continue

            if obj_type == "user":
                raw_text = self._raw_user_text(obj)
                if raw_text:
                    state.add_command(raw_text)
                if self._is_human_user_msg(obj):
                    state.add_user_message(raw_text, timestamp)
                continue

            if obj_type != "assistant":
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    state.apply_usage(usage)
                continue

            state.add_assistant_turn(timestamp)
            state.add_model(str(obj.get("model") or ""))
            usage = obj.get("usage")
            if isinstance(usage, dict):
                state.apply_usage(usage)

            message = obj.get("message") or {}
            for content in message.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "tool_use":
                    state.add_tool_use(content.get("name", ""), content.get("input"), asset_roots=self.asset_roots)
                if content.get("type") == "tool_result" and content.get("is_error"):
                    state.tool_errors += 1
                    error_name = str(content.get("tool_name") or "tool_error")
                    state.tool_error_categories[error_name] = state.tool_error_categories.get(error_name, 0) + 1

        token_usage = self._read_token_data_from_jsonl(jsonl_path)
        if state.input_tokens is None:
            state.input_tokens = token_usage["input_tokens"]
        if state.output_tokens is None:
            state.output_tokens = token_usage["output_tokens"]
        if state.cache_read_tokens is None:
            state.cache_read_tokens = token_usage["cache_read_tokens"]
        if state.cache_write_tokens is None:
            state.cache_write_tokens = token_usage["cache_write_tokens"]

        return state.finalize()
