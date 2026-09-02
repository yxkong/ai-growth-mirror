"""ACL for DeepSeek Harness session format v0 (raw JSONL or Zstd frames)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, TextIO

from ...domain.session.heuristics import is_validation_command
from ...domain.session.model import SessionRecord
from ...domain.signals.tooling import compute_tier_counts
from .base import BaseSessionAdapter, SessionRef, detect_language, parse_ts
from .diagnostics import ReaderDiagnostics


_PACKED_TYPES = {"reasoning-chunks", "text-chunks", "tool-call-chunks", "assistant/chunk"}
_WRITE_NAMES = {"write", "edit", "apply_patch", "patch"}
_EXEC_NAMES = {"bash", "shell", "exec", "command", "shell_command"}


class _EmptyRootTask(ValueError):
    pass


def _extract_command(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("command", "cmd"):
            if isinstance(value.get(key), str):
                return value[key]
        for nested in value.values():
            command = _extract_command(nested)
            if command:
                return command
    if isinstance(value, list):
        for nested in value:
            command = _extract_command(nested)
            if command:
                return command
    return ""


def _extract_text_content(value: Any) -> str:
    """Extract human text from Harness content blocks without reading metadata."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_extract_text_content(item) for item in value)))
    if isinstance(value, dict):
        for key in ("text", "content"):
            if key in value:
                return _extract_text_content(value[key])
    return ""


def _extract_paths(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {"path", "file", "filepath", "file_path"} and isinstance(nested, str):
                yield nested
            else:
                yield from _extract_paths(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _extract_paths(nested)


class DeepSeekHarnessAdapter(BaseSessionAdapter):
    tool_name = "deepseek_harness"
    display_name = "DeepSeek Harness"
    default_data_root = Path.home() / ".dsh" / "sessions"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = ReaderDiagnostics()
        self._headers: dict[str, dict[str, Any]] = {}
        self._paths: dict[str, Path] = {}
        self._index_signature: tuple[tuple[str, int, int], ...] = ()

    def _open_text(self, path: Path):
        if path.suffix != ".zstd":
            return path.open("r", encoding="utf-8")
        import io
        import zstandard

        compressed = path.open("rb")
        reader = zstandard.ZstdDecompressor().stream_reader(compressed, read_across_frames=True)
        text = io.TextIOWrapper(reader, encoding="utf-8")

        class _Context:
            def __enter__(self):
                return text

            def __exit__(self, exc_type, exc, tb):
                text.close()
                compressed.close()

        return _Context()

    def _read_header(self, path: Path) -> Optional[dict[str, Any]]:
        try:
            with self._open_text(path) as stream:
                for line in stream:
                    if line.strip():
                        row = json.loads(line)
                        return row if isinstance(row, dict) else None
        except Exception:
            self.diagnostics.unreadable += 1
        return None

    def _index(self) -> None:
        candidates = sorted(set(self.data_root.rglob("session.jsonl"))) + sorted(set(self.data_root.rglob("session.jsonl.zstd")))
        signature = tuple(
            (str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in candidates
        )
        if signature == self._index_signature:
            return
        self._index_signature = signature
        self._headers = {}
        self._paths = {}
        self.diagnostics = ReaderDiagnostics()
        for path in candidates:
            self.diagnostics.detected += 1
            header = self._read_header(path)
            if not header or header.get("type") != "session" or not header.get("id"):
                self.diagnostics.corrupt += 1
                continue
            if header.get("version") != 0:
                self.diagnostics.schema_mismatch += 1
                continue
            session_id = str(header["id"])
            if session_id in self._paths:
                self.diagnostics.corrupt += 1
                continue
            self._headers[session_id] = header
            self._paths[session_id] = path

    def is_available(self) -> bool:
        self._index()
        return any(not header.get("parentSession") for header in self._headers.values())

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        self._index()
        child_ids = {str(header.get("id")) for header in self._headers.values() if header.get("parentSession")}
        for child_id in child_ids:
            parent = str(self._headers[child_id].get("parentSession"))
            if parent not in self._headers:
                self.diagnostics.orphan += 1
        for session_id, header in sorted(self._headers.items()):
            if header.get("parentSession"):
                continue
            try:
                start = parse_ts(header["createdAt"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
            except Exception:
                self.diagnostics.corrupt += 1
                continue
            descendants = self._descendants(session_id)
            source_paths = [self._paths[item] for item in (session_id, *descendants)]
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start,
                source_paths=source_paths,
                source_mtime=max(path.stat().st_mtime for path in source_paths),
            )

    def _descendants(self, root_id: str) -> tuple[str, ...]:
        result: list[str] = []
        visiting = {root_id}

        def walk(parent: str, depth: int) -> None:
            if depth > 32:
                raise ValueError("delegation_depth_exceeded")
            children = sorted(
                session_id
                for session_id, header in self._headers.items()
                if str(header.get("parentSession") or "") == parent
            )
            for child in children:
                if child in visiting:
                    raise ValueError("delegation_cycle")
                visiting.add(child)
                result.append(child)
                walk(child, depth + 1)
                visiting.remove(child)

        walk(root_id, 0)
        return tuple(result)

    def _logical_rows(self, path: Path) -> Iterator[dict[str, Any]]:
        previous_seq = -1
        with self._open_text(path) as stream:
            first = True
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if first:
                    first = False
                    continue
                if not isinstance(row, dict) or row.get("type") in _PACKED_TYPES:
                    continue
                seq = row.get("seq")
                if not isinstance(seq, int) or seq <= previous_seq:
                    raise ValueError("non_monotonic_sequence")
                previous_seq = seq
                yield row

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        try:
            if raw.session_id not in self._headers:
                self._index()
            session_ids = (raw.session_id, *self._descendants(raw.session_id))
            root_header = self._headers[raw.session_id]
            tool_counts: Counter[str] = Counter()
            user_messages: list[str] = []
            user_timestamps: list[str] = []
            assistant_count = 0
            input_tokens = output_tokens = cache_read = cache_write = 0
            saw_usage = False
            saw_write = has_tests = False
            paths: set[str] = set()
            languages: Counter[str] = Counter()
            last_time: Optional[datetime] = raw.start_time
            earliest_write_time: Optional[datetime] = None
            tool_errors = 0
            models: set[str] = set()
            autonomous_chains: list[int] = []
            goal_changes = 0
            todo_writes = 0
            compactions = 0

            for session_id in session_ids:
                path = self._paths[session_id]
                is_root = session_id == raw.session_id
                chain_length = 0
                for row in self._logical_rows(path):
                    row_type = str(row.get("type") or "")
                    data = row.get("data") if isinstance(row.get("data"), dict) else {}
                    try:
                        current_time = parse_ts(row.get("time")) if row.get("time") else None
                        if current_time and current_time.tzinfo is None:
                            current_time = current_time.replace(tzinfo=timezone.utc)
                        if current_time:
                            last_time = max(last_time or current_time, current_time)
                    except Exception:
                        current_time = None
                    if row_type == "user/message" and is_root:
                        source = data.get("source")
                        source_kind = source.get("kind") if isinstance(source, dict) else None
                        if source_kind != "user":
                            continue
                        if chain_length:
                            autonomous_chains.append(chain_length)
                            chain_length = 0
                        text = _extract_text_content(data.get("content"))
                        if text:
                            user_messages.append(text[:500])
                            if current_time:
                                user_timestamps.append(current_time.isoformat())
                    elif row_type == "assistant/message":
                        assistant_count += 1
                        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                        if usage:
                            saw_usage = True
                            input_tokens += int(usage.get("inputTokens", 0) or 0)
                            output_tokens += int(usage.get("outputTokens", 0) or 0)
                            cache_read += int(usage.get("cacheReadTokens", 0) or 0)
                            cache_write += int(usage.get("cacheWriteTokens", 0) or 0)
                    elif row_type == "request/context":
                        model = data.get("model")
                        if isinstance(model, str) and model:
                            models.add(model)
                    elif row_type == "tool/call":
                        name = str(data.get("name") or "").strip().lower()
                        if not name:
                            continue
                        chain_length += 1
                        tool_counts[name] += 1
                        arguments = data.get("arguments", data.get("args", {}))
                        is_write = name in _WRITE_NAMES or any(
                            token in name for token in ("write", "edit", "patch")
                        )
                        if is_write:
                            saw_write = True
                            if current_time and (
                                earliest_write_time is None or current_time < earliest_write_time
                            ):
                                earliest_write_time = current_time
                        if name in _EXEC_NAMES or any(token in name for token in ("bash", "shell", "exec")):
                            if is_validation_command(_extract_command(arguments)):
                                has_tests = True
                        if is_write:
                            for file_path in _extract_paths(arguments):
                                paths.add(file_path)
                                language = detect_language(file_path)
                                if language:
                                    languages[language] += 1
                    elif row_type == "tool/result":
                        error = data.get("error")
                        if error not in (None, False, "", 0):
                            tool_errors += 1
                    elif row_type == "goal/change":
                        goal_changes += 1
                    elif row_type == "todo/write":
                        todo_writes += 1
                    elif row_type == "compaction/start":
                        compactions += 1
                if chain_length:
                    autonomous_chains.append(chain_length)

            if not user_messages and assistant_count == 0 and not tool_counts:
                self.diagnostics.skipped += 1
                raise _EmptyRootTask("empty_root_task")
            duration = max(0, int(((last_time or raw.start_time) - raw.start_time).total_seconds() / 60))
            first_write_turns = None
            if earliest_write_time is not None and user_timestamps:
                first_write_turns = max(
                    1,
                    sum(parse_ts(item) <= earliest_write_time for item in user_timestamps),
                )
            record = SessionRecord(
                session_id=raw.session_id,
                tool_name=self.tool_name,
                project_path=str(root_header.get("cwd") or ""),
                start_time=raw.start_time.isoformat(),
                end_time=last_time.isoformat() if last_time else None,
                duration_minutes=duration,
                first_prompt=user_messages[0] if user_messages else "",
                user_message_count=len(user_messages),
                assistant_message_count=assistant_count,
                top_user_messages=user_messages[:10],
                user_message_timestamps=user_timestamps,
                message_hours=[parse_ts(item).hour for item in user_timestamps],
                tool_counts=dict(tool_counts),
                tool_tier_counts=compute_tier_counts(dict(tool_counts)),
                tool_errors=tool_errors,
                autonomous_chain_lengths=autonomous_chains,
                input_tokens=input_tokens if saw_usage else None,
                output_tokens=output_tokens if saw_usage else None,
                cache_read_tokens=cache_read if saw_usage else None,
                cache_write_tokens=cache_write if saw_usage else None,
                files_modified=len(paths),
                languages=dict(languages),
                models_used=sorted(models),
                uses_subagent=len(session_ids) > 1,
                subagent_invocation_count=max(0, len(session_ids) - 1),
                has_verification_behavior=has_tests,
                has_test_commands=has_tests,
                slash_commands=["/goal"] if goal_changes else [],
                advanced_features=["plan_mode"] if goal_changes or todo_writes else [],
                auto_compact_count=compactions,
                turns_until_first_file_write=first_write_turns,
            )
            self._enrich_prompt_signals(record)
            self._enrich_agentic_signals(record)
            self.diagnostics.parsed += 1
            return record
        except _EmptyRootTask:
            raise
        except Exception:
            self.diagnostics.corrupt += 1
            raise
