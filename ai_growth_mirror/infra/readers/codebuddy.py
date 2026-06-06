"""Adapter for CodeBuddy AI coding assistant session logs.

CodeBuddy stores conversation transcripts as JSONL files under::

    ~/.codebuddy/projects/<project-hash>/<sessionId>.jsonl

Each line is a JSON object representing a message turn.  The format resembles
Cursor's agent-transcripts with ``<user_query>`` tags wrapping user prompts and
``tool_use`` blocks in assistant content arrays.

Supported data sources
-----------------------
- **transcript JSONL** (primary): ``~/.codebuddy/projects/<hash>/*.jsonl``
  Full per-session transcript with user messages, assistant responses, and tool calls.

- **history.jsonl** (fallback): ``~/.codebuddy/history.jsonl``
  Global history index; lighter-weight but with less rich tool-call data.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

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

_USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE
)
_PATH_INPUT_KEYS = (
    "path", "file_path", "target_file", "target_notebook",
    "notebook_path", "filePath", "targetFile", "AbsolutePath",
)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from a JSONL file, skipping bad lines."""
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def _extract_user_text(obj: dict) -> str:
    """Extract the human-written prompt from a user message object.

    Handles two formats:
    1. ``content`` is a string (possibly wrapping text in ``<user_query>`` tags).
    2. ``content`` is a list of content blocks (text parts).
    """
    content = obj.get("content", "")
    if isinstance(content, str):
        text = content.strip()
        match = _USER_QUERY_RE.search(text)
        if match:
            return match.group(1).strip()
        return text
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                chunk = part.get("text", "")
                if chunk:
                    chunks.append(chunk)
            elif isinstance(part, str):
                chunks.append(part)
        return "\n".join(chunks).strip()
    return ""


def _first_prompt_from_text(text: str) -> str:
    """Return a clean first-prompt preview, stripping XML tags if present."""
    if not text:
        return ""
    match = _USER_QUERY_RE.search(text)
    if match:
        return match.group(1).strip()[:500]
    return text[:500]


def _path_from_tool_input(tool_input: object) -> str:
    """Extract a file path from a tool-use input dict."""
    if not isinstance(tool_input, dict):
        return ""
    for key in _PATH_INPUT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _command_from_tool_input(tool_input: object) -> str:
    """Extract a shell command from a tool-use input dict."""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd", "CommandLine"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _message_timestamp(obj: dict) -> Optional[datetime]:
    """Parse a timestamp from a message object."""
    for key in ("timestamp", "created_at", "ts"):
        raw = obj.get(key)
        if not raw:
            continue
        try:
            ts = parse_ts(raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        except Exception:
            continue
    return None


class CodeBuddyAdapter(BaseSessionAdapter):
    """Session adapter for CodeBuddy (Tencent Cloud CodeBuddy).

    Reads conversation transcripts from the ``~/.codebuddy/projects/`` directory.

    Default data root (Windows)::

        %USERPROFILE%\\.codebuddy

    Default data root (macOS / Linux)::

        ~/.codebuddy
    """

    tool_name = "codebuddy"
    display_name = "CodeBuddy"
    default_data_root = Path.home() / ".codebuddy"

    @property
    def _projects_dir(self) -> Path:
        return self.data_root / "projects"

    @property
    def _history_file(self) -> Path:
        return self.data_root / "history.jsonl"

    # ── BaseSessionAdapter interface ──────────────────────────────────────

    def is_available(self) -> bool:
        if self._projects_dir.exists():
            for _ in self._iter_transcript_files():
                return True
        return self._history_file.exists()

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        seen: set[str] = set()

        # Primary: per-project transcript JSONL files
        for jsonl_path in sorted(self._iter_transcript_files()):
            session_id = jsonl_path.stem
            if session_id in seen:
                continue
            start_time = self._read_transcript_start_time(jsonl_path)
            try:
                source_mtime = jsonl_path.stat().st_mtime
            except OSError:
                source_mtime = 0.0
            seen.add(session_id)
            yield SessionRef(
                session_id=session_id,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=[jsonl_path],
                source_mtime=source_mtime,
            )

        # Fallback: global history.jsonl (sessions without project-specific transcripts)
        if self._history_file.exists():
            for obj in _iter_jsonl(self._history_file):
                sid = obj.get("session_id") or obj.get("sessionId") or obj.get("id")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                raw_ts = obj.get("timestamp") or obj.get("created_at") or obj.get("updated_at")
                if raw_ts:
                    try:
                        start_time = parse_ts(raw_ts)
                    except Exception:
                        start_time = datetime.now(timezone.utc)
                else:
                    try:
                        start_time = datetime.fromtimestamp(
                            self._history_file.stat().st_mtime, tz=timezone.utc
                        )
                    except OSError:
                        start_time = datetime.now(timezone.utc)
                yield SessionRef(
                    session_id=str(sid),
                    tool_name=self.tool_name,
                    start_time=start_time,
                    source_paths=[self._history_file],
                    source_mtime=_max_mtime([self._history_file]),
                )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        source_file = raw.source_paths[0]
        if source_file.suffix.lower() == ".jsonl":
            if source_file.name == "history.jsonl":
                return self._parse_history_session(raw)
            return self._parse_transcript(raw)
        return self._create_minimal_session(raw)

    # ── internal: transcript discovery ────────────────────────────────────

    def _iter_transcript_files(self) -> Iterator[Path]:
        """Yield all transcript JSONL files under the projects directory."""
        projects = self._projects_dir
        if not projects.exists():
            return
        for child in sorted(projects.iterdir()):
            if not child.is_dir():
                continue
            for jsonl in sorted(child.glob("*.jsonl")):
                if jsonl.is_file():
                    yield jsonl

    def _read_transcript_start_time(self, jsonl_path: Path) -> datetime:
        """Read the first timestamp from a transcript JSONL file."""
        for obj in _iter_jsonl(jsonl_path):
            ts = _message_timestamp(obj)
            if ts is not None:
                return ts
        try:
            stat = jsonl_path.stat()
            return datetime.fromtimestamp(
                min(stat.st_ctime, stat.st_mtime), tz=timezone.utc
            )
        except OSError:
            return datetime.now(timezone.utc)

    # ── internal: transcript parsing ──────────────────────────────────────

    def _parse_transcript(self, raw: SessionRef) -> SessionRecord:
        """Parse a full transcript JSONL file into a SessionRecord."""
        jsonl_path = raw.source_paths[0]

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
        models_used: list[str] = []
        user_message_timestamps: list[str] = []
        message_hours: list[int] = []
        last_timestamp: Optional[datetime] = None

        try:
            stat = jsonl_path.stat()
            end_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            end_ts = raw.start_time
        start_ts = raw.start_time

        for obj in _iter_jsonl(jsonl_path):
            ts = _message_timestamp(obj)
            if ts is not None:
                last_timestamp = ts

            role = obj.get("role", "")

            # ── user message ─────────────────────────────────────────────
            if role == "user":
                user_text = _extract_user_text(obj)
                if user_text:
                    user_message_count += 1
                    if not first_prompt:
                        first_prompt = _first_prompt_from_text(
                            obj.get("content", "") if isinstance(obj.get("content"), str) else user_text
                        )
                    if len(top_user_messages) < 5:
                        top_user_messages.append(user_text[:300])
                    if ts is not None:
                        user_message_timestamps.append(ts.isoformat())
                        message_hours.append(ts.astimezone().hour)

                    # Detect skill attachments in user prompt
                    content_str = str(obj.get("content", ""))
                    _has_skill_attach = (
                        "manually_attached_skills" in content_str.lower()
                        or "<agent_skill" in content_str
                        or "<available_skills" in content_str
                    )
                    if _has_skill_attach:
                        skill_invocation_count += 1
                        for _fp in re.findall(
                            r'<agent_skill[^>]+fullPath=["\']([^"\']+)["\']', content_str
                        ):
                            _folder = Path(_fp).parent.name
                            if _folder and _folder not in ("", ".", "skills", "skills-cursor"):
                                unique_skills_from_attach.add(_folder)
                        if not unique_skills_from_attach:
                            for _desc in re.findall(
                                r'<agent_skill[^>]*>([^<]{5,100})</agent_skill>', content_str
                            ):
                                _desc = _desc.strip()
                                if _desc:
                                    unique_skills_from_attach.add(_desc[:60])
                        if unique_skills_from_attach:
                            skill_files_authored.add("__attached_skills__")

                # Flush autonomous chain on user turn
                if current_chain:
                    chain_lengths.append(current_chain)
                    current_chain = 0
                pending_write = False
                continue

            # ── assistant message ─────────────────────────────────────────
            if role != "assistant":
                continue

            assistant_message_count += 1
            content = obj.get("content", [])
            if not isinstance(content, list):
                # Content might be a string in some formats
                if isinstance(content, str) and content.strip():
                    # Check for model info embedded in content
                    model = obj.get("model")
                    if model and model not in models_used:
                        models_used.append(model)
                continue

            for part in content:
                if not isinstance(part, dict):
                    continue

                part_type = part.get("type", "")

                # ── text block ────────────────────────────────────────────
                if part_type == "text":
                    text = part.get("text", "")
                    # Try to extract model name from text if not yet found
                    if text and not models_used:
                        model = obj.get("model")
                        if model and model not in models_used:
                            models_used.append(model)
                    continue

                # ── tool_use block ────────────────────────────────────────
                if part_type != "tool_use":
                    continue

                tool_name = str(part.get("name", "")).strip()
                if not tool_name:
                    continue

                normalized = tool_name.lower()
                tool_counts[normalized] += 1
                current_chain += 1

                tool_input = part.get("input", {})

                # ── path extraction ───────────────────────────────────────
                path = _path_from_tool_input(tool_input)
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

                # ── capability flags ──────────────────────────────────────
                if normalized in SUBAGENT_TOOL_NAMES or "task" in normalized or "subagent" in normalized:
                    uses_subagent = True
                    subagent_invocation_count += 1
                if "mcp" in normalized:
                    uses_mcp = True
                if "web_search" in normalized or normalized == "websearch":
                    uses_web_search = True
                if "web_fetch" in normalized or "fetch" in normalized:
                    uses_web_fetch = True

                # ── write / exec classification ───────────────────────────
                if normalized in WRITE_TOOL_NAMES or normalize_tool_name(normalized) in ("write", "edit"):
                    pending_write = True

                if normalized in EXEC_TOOL_NAMES or normalize_tool_name(normalized) == "bash":
                    command = _command_from_tool_input(tool_input).lower()
                    if command:
                        shell_commands.append(command)
                    if pending_write:
                        has_verification = True
                        pending_write = False
                    if any(p in command for p in TEST_PATTERNS):
                        has_test_commands = True

        # Flush final chain
        if current_chain:
            chain_lengths.append(current_chain)

        # ── project path detection ────────────────────────────────────────
        project_path = _common_prefix_path(list(file_paths))
        if not project_path:
            project_path = _project_hash_to_hint(jsonl_path)

        duration_minutes = max(int((end_ts - start_ts).total_seconds() // 60), 0)

        session = SessionRecord(
            session_id=raw.session_id,
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
            unique_skills_used=sorted(unique_skills_from_attach),
            subagent_invocation_count=subagent_invocation_count,
            skill_files_authored=len(skill_files_authored),
            hook_config_modified=hook_config_modified,
            mcp_server_authored=mcp_server_authored,
            entrypoint="ide",
            user_message_timestamps=user_message_timestamps,
            message_hours=message_hours,
        )
        return session

    def _parse_history_session(self, raw: SessionRef) -> SessionRecord:
        """Parse a session entry from the global history.jsonl fallback."""
        session_id = raw.session_id
        first_prompt = ""
        project_path = ""
        user_message_count = 0

        for obj in _iter_jsonl(raw.source_paths[0]):
            sid = obj.get("session_id") or obj.get("sessionId") or obj.get("id")
            if str(sid) != session_id:
                continue
            first_prompt = obj.get("title") or obj.get("summary") or obj.get("first_prompt") or ""
            project_path = obj.get("cwd") or obj.get("project_path") or obj.get("workspace") or ""
            user_message_count = obj.get("message_count") or obj.get("turn_count") or 0
            break

        return SessionRecord(
            session_id=session_id,
            tool_name=self.tool_name,
            project_path=str(project_path),
            start_time=raw.start_time.isoformat(),
            end_time=raw.start_time.isoformat(),
            duration_minutes=0,
            first_prompt=str(first_prompt)[:500],
            user_message_count=int(user_message_count) if user_message_count else 0,
            assistant_message_count=0,
            tool_counts={},
            files_modified=0,
            languages={},
            models_used=[],
            uses_subagent=False,
            uses_mcp=False,
            uses_web_search=False,
            uses_web_fetch=False,
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


# ── shared utilities ──────────────────────────────────────────────────────




def _project_hash_to_hint(jsonl_path: Path) -> str:
    """Derive a project name hint from the transcript path."""
    parts = jsonl_path.parts
    try:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    except ValueError:
        pass
    return ""
