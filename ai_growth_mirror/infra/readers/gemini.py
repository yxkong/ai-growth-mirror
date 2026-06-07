"""Reader for Gemini (Antigravity) AI coding assistant session logs.

Antigravity is Google DeepMind's AI coding assistant (IDE integration).
Its on-disk format is identical across both ``antigravity`` and
``antigravity-ide`` profiles.

Data layout (Windows default)::

    %USERPROFILE%\\.gemini\\antigravity\\brain\\
        <conversation_id>\\
            .system_generated\\logs\\
                transcript.jsonl   # full log — newer sessions
                overview.txt       # compact log — older sessions

Each file is JSONL (one JSON object per line).

Step structure
--------------
USER_INPUT  (source=USER_EXPLICIT)
    ``content`` — raw string that wraps the human prompt inside
    ``<USER_REQUEST>…</USER_REQUEST>`` XML tags.

PLANNER_RESPONSE  (source=MODEL)
    ``tool_calls`` — list of ``{"name": str, "args": dict}`` objects.
    In the compact *overview.txt* format the arg values may themselves be
    JSON-encoded strings (double-serialised); ``_unwrap_args`` handles that.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional
from ...domain.session.heuristics import (
    EXEC_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    TEST_PATTERNS,
    WRITE_TOOL_NAMES,
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
)


# ── constants ─────────────────────────────────────────────────────────────────

_USER_REQUEST_RE = re.compile(
    r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL | re.IGNORECASE
)
_ACTIVE_DOC_RE = re.compile(r"Active Document:\s*([^\n(]+)")

# tool args keys that may carry file / directory paths
_PATH_ARG_KEYS = (
    "TargetFile",
    "AbsolutePath",
    "SearchPath",
    "Cwd",
    "target_file",
    "file_path",
    "path",
    "DirectoryPath",
)

# Gemini-specific tool sets (complement the shared domain sets)
_GEMINI_EXEC_TOOLS = frozenset({"run_command", "execute_command"})
_GEMINI_WRITE_TOOLS = frozenset({
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "create_file",
    "edit_file",
})
_GEMINI_SUBAGENT_TOOLS = frozenset({"invoke_subagent", "define_subagent"})


# ── helpers ───────────────────────────────────────────────────────────────────

def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from a JSONL file, skipping bad lines."""
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


def _extract_user_request(content: str) -> str:
    """Pull the human-written text out of a USER_INPUT content string.

    Handles three layouts:
    1. ``<USER_REQUEST>text</USER_REQUEST>`` — standard, matched by regex.
    2. ``<USER_REQUEST>text`` (no closing tag) — older overview.txt format.
    3. Raw text without any XML wrapper — very old sessions.
    """
    if not content:
        return ""
    # Case 1: well-formed tag pair
    m = _USER_REQUEST_RE.search(content)
    if m:
        return m.group(1).strip()[:500]
    # Case 2: opening tag only — grab everything after it up to next XML tag
    open_match = re.search(r"<USER_REQUEST>\s*", content, re.IGNORECASE)
    if open_match:
        after = content[open_match.end():]
        # Trim at the first XML tag boundary (e.g. <ADDITIONAL_METADATA>)
        trimmed = re.split(r"<[A-Z_]+>", after, maxsplit=1)[0]
        return trimmed.strip()[:500]
    # Case 3: no wrapper — strip any XML tags and return raw
    clean = re.sub(r"<[A-Z_]+>.*?</[A-Z_]+>", "", content, flags=re.DOTALL)
    return clean.strip()[:500]


def _path_from_args(args: Any) -> list[str]:
    """Extract file-path strings from a tool-call ``args`` dict."""
    if not isinstance(args, dict):
        return []
    paths: list[str] = []
    for key in _PATH_ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    return paths


def _command_from_args(args: Any) -> str:
    """Extract shell command string from run_command-style args."""
    if not isinstance(args, dict):
        return ""
    return str(
        args.get("CommandLine")
        or args.get("command")
        or args.get("cmd")
        or ""
    )


def _unwrap_args(args: Any) -> Any:
    """Strip one layer of JSON-string encoding from arg values.

    The compact *overview.txt* format sometimes double-encodes arg values
    (e.g. ``{"TargetFile": "\"d:\\\\path\\\\file.py\""}``).
    """
    if not isinstance(args, dict):
        return args
    result: dict[str, Any] = {}
    for k, v in args.items():
        if (
            isinstance(v, str)
            and len(v) >= 2
            and v.startswith('"')
            and v.endswith('"')
        ):
            try:
                result[k] = json.loads(v)
            except Exception:
                result[k] = v
        else:
            result[k] = v
    return result


def _find_log_file(conv_dir: Path) -> Optional[Path]:
    """Return the best log file under a conversation directory.

    Prefers ``transcript.jsonl`` (richer) over ``overview.txt`` (compact).
    """
    logs_dir = conv_dir / ".system_generated" / "logs"
    if not logs_dir.exists():
        return None
    for name in ("transcript.jsonl", "overview.txt"):
        candidate = logs_dir / name
        if candidate.exists():
            return candidate
    return None


# ── accumulator ───────────────────────────────────────────────────────────────

@dataclass
class _GeminiAccumulator:
    session_id: str
    start_time: datetime
    project_path: str = ""
    first_prompt: str = ""
    top_user_messages: list[str] = field(default_factory=list)
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    files_modified: int = 0
    languages: dict[str, int] = field(default_factory=dict)
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
    turns_until_first_file_write: Optional[int] = None
    unique_skills: set[str] = field(default_factory=set)
    user_message_timestamps: list[str] = field(default_factory=list)
    message_hours: list[int] = field(default_factory=list)
    autonomous_chain_lengths: list[int] = field(default_factory=list)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    _seen_paths: set[str] = field(default_factory=set)
    _last_timestamp: Optional[datetime] = None
    _current_chain: int = 0
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
        # Flush autonomous tool-call chain on each user turn
        if self._current_chain:
            self.autonomous_chain_lengths.append(self._current_chain)
            self._current_chain = 0
        self._saw_write = False
        self._saw_exec = False

    def add_tool_call(
        self,
        name: str,
        args: Any,
        timestamp: Optional[datetime],
        *,
        asset_roots: tuple[Path, ...],
    ) -> None:
        normalized = (name or "").strip().lower()
        if not normalized:
            return
        self.tool_counts[normalized] = self.tool_counts.get(normalized, 0) + 1
        self._current_chain += 1
        if timestamp is not None:
            self._last_timestamp = timestamp

        # ── capability flags ──────────────────────────────────────────────
        if (
            normalized in _GEMINI_SUBAGENT_TOOLS
            or normalized in SUBAGENT_TOOL_NAMES
            or "subagent" in normalized
            or "invoke" in normalized
        ):
            self.uses_subagent = True
            self.subagent_invocation_count += 1

        if "mcp" in normalized:
            self.uses_mcp = True

        if "search_web" in normalized or "web_search" in normalized or normalized == "search":
            self.uses_web_search = True
        if "read_url" in normalized or "fetch" in normalized or "browser" in normalized:
            self.uses_web_fetch = True

        # ── write / exec classification ───────────────────────────────────
        is_write = normalized in _GEMINI_WRITE_TOOLS or normalized in WRITE_TOOL_NAMES
        is_exec = normalized in _GEMINI_EXEC_TOOLS or normalized in EXEC_TOOL_NAMES
        if is_write:
            self._saw_write = True
            if self.turns_until_first_file_write is None:
                self.turns_until_first_file_write = max(1, self.user_message_count)
        if is_exec:
            self._saw_exec = True
            cmd = _command_from_args(args).lower()
            if any(pat in cmd for pat in TEST_PATTERNS):
                self.has_test_commands = True
            if self._saw_write:
                self.has_verification_behavior = True

        # ── path extraction ───────────────────────────────────────────────
        for p in _path_from_args(args):
            if p not in self._seen_paths:
                self._seen_paths.add(p)
                self.files_modified = len(self._seen_paths)
            lang = detect_language(p)
            if lang:
                self.languages[lang] = self.languages.get(lang, 0) + 1
            authorship = detect_authorship_path(p, asset_roots)
            if authorship == "skill":
                self.skill_files_authored += 1
            elif authorship == "hook":
                self.hook_config_modified = True
            elif authorship == "mcp":
                self.mcp_server_authored = True
            # Skill fingerprint: agent read a SKILL.md from a skill folder
            if normalized in SKILL_READ_TOOL_NAMES:
                skill_name = extract_skill_name_from_path(p)
                if skill_name:
                    self.unique_skills.add(skill_name)
                    self.skill_invocation_count += 1

    def finalize(self, tool_name: str) -> SessionRecord:
        if self._current_chain:
            self.autonomous_chain_lengths.append(self._current_chain)

        end_time = self._last_timestamp.isoformat() if self._last_timestamp else None
        duration: Optional[int] = None
        if self._last_timestamp is not None:
            duration = max(
                0, int((self._last_timestamp - self.start_time).total_seconds() / 60)
            )

        record = SessionRecord(
            session_id=self.session_id,
            tool_name=tool_name,
            project_path=self.project_path,
            start_time=self.start_time.isoformat(),
            end_time=end_time,
            duration_minutes=duration,
            first_prompt=self.first_prompt,
            user_message_count=self.user_message_count,
            assistant_message_count=self.assistant_message_count,
            tool_counts=self.tool_counts,
            tool_tier_counts=compute_tier_counts(self.tool_counts),
            # Gemini transcript.jsonl does not embed API usage data.
            # Token counts would only be character-based estimates, which are
            # unreliable. Set all token/cost fields to None and mark as estimated
            # so the report layer excludes them from aggregation and display.
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            total_cost_usd=None,
            tokens_estimated=True,
            files_modified=self.files_modified,
            languages=self.languages,
            message_hours=self.message_hours,
            user_message_timestamps=self.user_message_timestamps,
            uses_subagent=self.uses_subagent,
            uses_mcp=self.uses_mcp,
            uses_web_search=self.uses_web_search,
            uses_web_fetch=self.uses_web_fetch,
            top_user_messages=self.top_user_messages,
            autonomous_chain_lengths=self.autonomous_chain_lengths,
            has_verification_behavior=self.has_verification_behavior,
            has_test_commands=self.has_test_commands,
            skill_files_authored=self.skill_files_authored,
            hook_config_modified=self.hook_config_modified,
            mcp_server_authored=self.mcp_server_authored,
            subagent_invocation_count=self.subagent_invocation_count,
            skill_invocation_count=self.skill_invocation_count,
            unique_skills_used=sorted(self.unique_skills),
            entrypoint="ide",
            models_used=["gemini"],
            turns_until_first_file_write=self.turns_until_first_file_write,
        )
        BaseSessionAdapter._enrich_prompt_signals(record)
        BaseSessionAdapter._enrich_agentic_signals(record)
        return record


# ── adapter ───────────────────────────────────────────────────────────────────

class GeminiAdapter(BaseSessionAdapter):
    """Session adapter for Gemini (Antigravity) AI coding assistant.

    Reads conversation logs from the ``brain/`` directory inside the
    Antigravity data root.

    Default data root (Windows)::

        ~\\.gemini\\antigravity

    Supports both the standalone (``antigravity``) and IDE-embedded
    (``antigravity-ide``) profiles — pass either as ``data_roots``.

    Supported log files
    -------------------
    ``transcript.jsonl``
        Full step log; preferred when present (newer sessions).

    ``overview.txt``
        Compact step log; fallback for older sessions.
    """

    tool_name = "gemini"
    display_name = "Gemini"
    default_data_root = Path.home() / ".gemini" / "antigravity"

    @property
    def _brain_dir(self) -> Path:
        return self.data_root / "brain"

    # ── BaseSessionAdapter interface ──────────────────────────────────────────

    def is_available(self) -> bool:
        brain = self._brain_dir
        if not brain.exists():
            return False
        return any(
            conv_dir.is_dir() and _find_log_file(conv_dir) is not None
            for conv_dir in brain.iterdir()
        )

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        brain = self._brain_dir
        if not brain.exists():
            return
        for conv_dir in sorted(brain.iterdir()):
            if not conv_dir.is_dir():
                continue
            log_file = _find_log_file(conv_dir)
            if log_file is None:
                continue
            start_time = self._read_start_time(log_file)
            if start_time is None:
                try:
                    start_time = datetime.fromtimestamp(
                        conv_dir.stat().st_ctime, tz=timezone.utc
                    )
                except OSError:
                    start_time = datetime.now(timezone.utc)
            yield SessionRef(
                session_id=conv_dir.name,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=[log_file],
                source_mtime=_max_mtime([log_file]),
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        return self._parse_log(raw.session_id, raw.source_paths[0], raw.start_time)

    # ── internal ──────────────────────────────────────────────────────────────

    def _read_start_time(self, log_file: Path) -> Optional[datetime]:
        """Return timestamp of the first step in the log file."""
        for obj in _iter_jsonl(log_file):
            raw_ts = obj.get("created_at")
            if not raw_ts:
                continue
            try:
                ts = parse_iso(raw_ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
            except Exception:
                continue
        return None

    def _parse_log(
        self, session_id: str, log_file: Path, start_time: datetime
    ) -> SessionRecord:
        state = _GeminiAccumulator(session_id=session_id, start_time=start_time)
        project_candidates: list[str] = []

        for obj in _iter_jsonl(log_file):
            # ── parse timestamp ───────────────────────────────────────────
            timestamp: Optional[datetime] = None
            raw_ts = obj.get("created_at")
            if raw_ts:
                try:
                    timestamp = parse_iso(raw_ts)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            step_type = obj.get("type", "")
            source = obj.get("source", "")

            # ── user turn ─────────────────────────────────────────────────
            if step_type == "USER_INPUT":
                content = obj.get("content", "")
                user_text = _extract_user_request(content)
                if user_text:
                    state.add_user_message(user_text, timestamp)
                # Infer project path from Active Document metadata (first hit)
                if not project_candidates and content:
                    for m in _ACTIVE_DOC_RE.finditer(content):
                        doc = m.group(1).strip()
                        if doc:
                            project_candidates.append(doc)
                continue

            # ── model turn ────────────────────────────────────────────────
            if step_type == "PLANNER_RESPONSE" and source == "MODEL":
                content = obj.get("content", "")
                tool_calls = obj.get("tool_calls")
                if not isinstance(tool_calls, list):
                    if content:
                        state.assistant_message_count += 1
                    continue
                state.assistant_message_count += 1
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    name = tc.get("name", "")
                    args = tc.get("args", {})
                    # overview.txt may have the args dict as a JSON string
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    args = _unwrap_args(args)
                    state.add_tool_call(
                        name, args, timestamp, asset_roots=self.asset_roots
                    )
                continue

        # Derive project_path from first Active Document seen
        if not state.project_path and project_candidates:
            try:
                state.project_path = str(Path(project_candidates[0]).parent)
            except Exception:
                pass

        return state.finalize(self.tool_name)
