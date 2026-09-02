"""Read-only ACL for ZCode Agent's local SQLite session database."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ...domain.session.heuristics import is_validation_command
from ...domain.session.model import SessionRecord
from ...domain.signals.tooling import compute_tier_counts
from .base import BaseSessionAdapter, SessionRef, parse_ts
from .diagnostics import ReaderDiagnostics


_REQUIRED_COLUMNS = {
    "session": {"id", "parent_id", "directory", "time_created", "time_updated"},
    "message": {"id", "session_id", "time_created", "data"},
    "part": {"id", "message_id", "session_id", "time_created", "data"},
    "tool_usage": {"id", "session_id", "tool_call_id", "tool_name", "status", "started_at"},
    "model_usage": {
        "id",
        "session_id",
        "model_id",
        "started_at",
        "input_tokens",
        "output_tokens",
    },
}


class ZCodeAdapter(BaseSessionAdapter):
    tool_name = "zcode"
    display_name = "ZCode Agent"
    default_data_root = Path.home() / ".zcode" / "cli"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = ReaderDiagnostics()
        self._session_rows: Optional[list[sqlite3.Row]] = None

    @property
    def _db_path(self) -> Path:
        return self.data_root / "db" / "db.sqlite"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self._db_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _schema_ok(self) -> bool:
        if not self._db_path.is_file():
            return False
        try:
            with self._connect() as db:
                for table, required in _REQUIRED_COLUMNS.items():
                    columns = {str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")')}
                    if not required.issubset(columns):
                        self.diagnostics.schema_mismatch += 1
                        return False
        except (OSError, sqlite3.Error):
            self.diagnostics.unreadable += 1
            return False
        return True

    def is_available(self) -> bool:
        return self._schema_ok()

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        if not self._schema_ok():
            return
        try:
            with self._connect() as db:
                self._session_rows = db.execute("SELECT * FROM session").fetchall()
                rows = db.execute(
                    "SELECT id, time_created, time_updated FROM session "
                    "WHERE parent_id IS NULL OR parent_id = '' ORDER BY time_created"
                ).fetchall()
            self.diagnostics.detected += len(rows)
            for row in rows:
                start = parse_ts(row["time_created"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                revision = float(row["time_updated"] or 0)
                if revision > 4_000_000_000:
                    revision /= 1000.0
                yield SessionRef(str(row["id"]), self.tool_name, start, [self._db_path], revision)
        except (ValueError, sqlite3.Error):
            self.diagnostics.unreadable += 1

    @staticmethod
    def _json(raw: Any) -> dict[str, Any]:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _children(rows: list[sqlite3.Row], root_id: str) -> tuple[str, ...]:
        parents = {str(row["id"]): str(row["parent_id"] or "") for row in rows}
        result: list[str] = []
        visiting = {root_id}

        def walk(parent: str, depth: int) -> None:
            if depth > 32:
                raise ValueError("delegation_depth_exceeded")
            for child in sorted(key for key, value in parents.items() if value == parent):
                if child in visiting:
                    raise ValueError("delegation_cycle")
                visiting.add(child)
                result.append(child)
                walk(child, depth + 1)
                visiting.remove(child)

        walk(root_id, 0)
        return tuple(result)

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        try:
            with self._connect() as db:
                session_rows = self._session_rows or db.execute("SELECT * FROM session").fetchall()
                by_id = {str(row["id"]): row for row in session_rows}
                descendants = self._children(session_rows, raw.session_id)
                session_ids = (raw.session_id, *descendants)
                placeholders = ",".join("?" for _ in session_ids)
                message_rows = db.execute(
                    f"SELECT * FROM message WHERE session_id IN ({placeholders}) ORDER BY time_created", session_ids
                ).fetchall()
                part_rows = db.execute(
                    f"SELECT * FROM part WHERE session_id IN ({placeholders}) ORDER BY time_created", session_ids
                ).fetchall()
                tool_rows = db.execute(
                    f"SELECT * FROM tool_usage WHERE session_id IN ({placeholders}) ORDER BY started_at", session_ids
                ).fetchall()
                model_rows = db.execute(
                    f"SELECT * FROM model_usage WHERE session_id IN ({placeholders}) ORDER BY started_at", session_ids
                ).fetchall()

            root = by_id[raw.session_id]
            message_data = {str(row["id"]): self._json(row["data"]) for row in message_rows}
            root_user_ids = {
                str(row["id"])
                for row in message_rows
                if str(row["session_id"]) == raw.session_id and message_data[str(row["id"])].get("role") == "user"
            }
            user_texts: list[str] = []
            user_times: list[str] = []
            part_by_call: dict[tuple[str, str], dict[str, Any]] = {}
            for row in part_rows:
                data = self._json(row["data"])
                if str(row["message_id"]) in root_user_ids and data.get("type") == "text" and isinstance(data.get("text"), str):
                    user_texts.append(data["text"][:500])
                    timestamp = parse_ts(row["time_created"])
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    user_times.append(timestamp.isoformat())
                if data.get("type") == "tool" and data.get("callID"):
                    part_by_call[(str(row["session_id"]), str(data["callID"]))] = data

            tool_counts: Counter[str] = Counter()
            tool_errors = 0
            saw_write = saw_exec = has_tests = False
            for row in tool_rows:
                name = str(row["tool_name"] or "").strip().lower()
                if not name:
                    continue
                tool_counts[name] += 1
                if str(row["status"] or "").lower() == "error":
                    tool_errors += 1
                part = part_by_call.get(
                    (str(row["session_id"]), str(row["tool_call_id"])), {}
                )
                state = part.get("state") if isinstance(part.get("state"), dict) else {}
                args = state.get("input") if isinstance(state.get("input"), dict) else {}
                if any(token in name for token in ("write", "edit", "patch")):
                    saw_write = True
                if any(token in name for token in ("bash", "shell", "exec", "command")):
                    saw_exec = True
                    command = str(args.get("command") or args.get("cmd") or "")
                    if is_validation_command(command):
                        has_tests = True

            input_tokens = sum(int(row["input_tokens"] or 0) for row in model_rows)
            output_tokens = sum(int(row["output_tokens"] or 0) for row in model_rows)
            cache_read = sum(int(row["cache_read_input_tokens"] or 0) for row in model_rows if "cache_read_input_tokens" in row.keys())
            cache_write = sum(int(row["cache_creation_input_tokens"] or 0) for row in model_rows if "cache_creation_input_tokens" in row.keys())
            models = sorted({str(row["model_id"]) for row in model_rows if row["model_id"]})
            assistant_count = sum(1 for data in message_data.values() if data.get("role") == "assistant")
            end_millis = max(int(by_id[item]["time_updated"] or 0) for item in session_ids)
            end = parse_ts(end_millis)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            files_modified = sum(int(by_id[item]["summary_files"] or 0) for item in session_ids if "summary_files" in by_id[item].keys())
            lines_added = sum(int(by_id[item]["summary_additions"] or 0) for item in session_ids if "summary_additions" in by_id[item].keys())
            lines_removed = sum(int(by_id[item]["summary_deletions"] or 0) for item in session_ids if "summary_deletions" in by_id[item].keys())

            record = SessionRecord(
                session_id=raw.session_id,
                tool_name=self.tool_name,
                tool_version=str(root["version"] or "") if "version" in root.keys() else None,
                project_path=str(root["directory"] or ""),
                start_time=raw.start_time.isoformat(),
                end_time=end.isoformat(),
                duration_minutes=max(0, int((end - raw.start_time).total_seconds() / 60)),
                first_prompt=user_texts[0] if user_texts else "",
                user_message_count=len(root_user_ids),
                assistant_message_count=assistant_count,
                top_user_messages=user_texts[:10],
                user_message_timestamps=user_times,
                message_hours=[parse_ts(item).hour for item in user_times],
                tool_counts=dict(tool_counts),
                tool_tier_counts=compute_tier_counts(dict(tool_counts)),
                tool_errors=tool_errors,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                lines_added=lines_added,
                lines_removed=lines_removed,
                files_modified=files_modified,
                models_used=models,
                uses_subagent=bool(descendants),
                subagent_invocation_count=len(descendants),
                has_verification_behavior=saw_write and saw_exec,
                has_test_commands=has_tests,
            )
            self._enrich_prompt_signals(record)
            self._enrich_agentic_signals(record)
            self.diagnostics.parsed += 1
            return record
        except Exception:
            self.diagnostics.corrupt += 1
            raise
