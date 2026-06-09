"""Shared reader utilities and BaseSessionAdapter ABC."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

from ...domain.session.model import SessionRecord, SessionRef
from ...domain.session.heuristics import (
    CODE_CONTEXT_PATTERNS,
    CONSTRAINT_WORDS,
    EXEC_TOOL_NAMES,
    READ_TOOL_NAMES,
    SUBAGENT_TOOL_NAMES,
    TEST_PATTERNS,
    WRITE_TOOL_NAMES,
    detect_authorship_path,
    enrich_advanced_features,
    enrich_agentic_signals,
    enrich_prompt_signals,
    enrich_task_contract_signals,
    is_validation_command,
)

if TYPE_CHECKING:
    from ..cache.store import CacheStore


class BaseSessionAdapter(ABC):
    """
    Contract: parse raw on-disk data for one AI coding tool,
    yield SessionRecord. No LLM calls, no caching.
    """
    tool_name: str       # class attribute, e.g. "codex"
    display_name: str    # "Codex CLI"
    default_data_root: Path

    def __init__(
        self,
        data_root: Optional[Path] = None,
        data_roots: Optional[list[Path]] = None,
        asset_roots: Optional[list[Path]] = None,
    ):
        if data_roots:
            self.data_roots: list[Path] = data_roots
        elif data_root:
            self.data_roots = [data_root]
        else:
            self.data_roots = [self.default_data_root]
        self.data_root: Path = self.data_roots[0]
        self.asset_roots: tuple[Path, ...] = tuple(asset_roots) if asset_roots else ()

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if any data_root exists and contains recognizable data."""
        ...

    @abstractmethod
    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        """
        Yield lightweight SessionRef handles without parsing full content.
        Must be fast — used for date filtering before full parse.
        Implementations read from self.data_root.
        """
        ...

    @abstractmethod
    def parse_session(self, raw: SessionRef) -> SessionRecord:
        """Parse one session fully. No LLM calls."""
        ...

    @staticmethod
    def _enrich_prompt_signals(session: SessionRecord) -> None:
        """Apply shared prompt heuristics from the domain layer."""
        enrich_prompt_signals(session)

    @staticmethod
    def _enrich_agentic_signals(session: SessionRecord) -> None:
        """Apply shared session heuristics from the domain layer."""
        enrich_agentic_signals(session)

    @staticmethod
    def _enrich_advanced_features(session: SessionRecord) -> None:
        """Derive higher-order collaboration features uniformly across readers."""
        enrich_advanced_features(session)

    @staticmethod
    def _enrich_task_contract_signals(session: SessionRecord) -> None:
        """Derive effective task-contract signals uniformly across readers."""
        enrich_task_contract_signals(session)

    def _quick_extract_project_path(self, raw: SessionRef) -> str:
        """Rapidly extract project path without parsing full session payload."""
        return ""

    def _iter_sessions_from_root(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        cache: Optional["CacheStore"] = None,
        force_refresh: bool = False,
        machine: str = "local",
    ) -> Iterator[SessionRecord]:
        """Iterate sessions from the current self.data_root.

        A session is included if its activity window [start_time, end_time]
        overlaps with [since, until]. This correctly handles resumed sessions
        whose start_time predates ``since`` but still have activity within range.

        Cache contract:
        - `cache=None`: pure parse-only path (no reads, no writes).
        - `cache=CacheStore` and `force_refresh=False` (default): mtime-gated
          read; on hit, skip parse_session entirely.  Cache miss triggers
          parse + write.
        - `cache=CacheStore` and `force_refresh=True`: always re-parse from
          source (skip the read), but still write the fresh result back to
          cache. Used by `ai-growth-mirror generate --no-cache` so a fresh
          report run leaves a usable cache for downstream recap commands.
        """
        for raw in self.iter_raw_sessions():
            # Quick reject: session started after the until boundary.
            if until and raw.start_time > until:
                continue
            session: Optional[SessionRecord] = None
            if cache is not None and raw.source_mtime > 0 and not force_refresh:
                session = cache.read_record(
                    self.tool_name, raw.session_id, source_mtime=raw.source_mtime, source_machine=machine
                )
            if session is None:
                if cache is not None:
                    # Lazy loading placeholder
                    project_path = self._quick_extract_project_path(raw)
                    session = SessionRecord(
                        session_id=raw.session_id,
                        tool_name=self.tool_name,
                        start_time=raw.start_time.isoformat(),
                        project_path=project_path,
                    )
                    session._is_placeholder = True
                    session._raw_ref = raw
                    session._adapter = self
                    session._source_mtime = raw.source_mtime
                else:
                    try:
                        session = self.parse_session(raw)
                    except Exception:
                        continue
                    session._source_mtime = raw.source_mtime
                    # Enrich prompt signals for adapters that don't compute them natively.
                    self._enrich_prompt_signals(session)
                    # Infer agentic signals from tool_counts when not natively available.
                    self._enrich_agentic_signals(session)

            # Enrich advanced features only for fully-loaded records.
            if not session._is_placeholder:
                self._enrich_advanced_features(session)
                self._enrich_task_contract_signals(session)
            if since:
                # Determine the session's last-activity timestamp.
                last_activity = raw.start_time
                if not session._is_placeholder:
                    if session.end_time:
                        try:
                            last_activity = parse_iso(session.end_time)
                            if last_activity.tzinfo is None:
                                from datetime import timezone as _tz
                                last_activity = last_activity.replace(tzinfo=_tz.utc)
                        except Exception:
                            pass
                    elif session.user_message_timestamps:
                        try:
                            last_ts = parse_iso(session.user_message_timestamps[-1])
                            if last_ts.tzinfo is None:
                                from datetime import timezone as _tz
                                last_ts = last_ts.replace(tzinfo=_tz.utc)
                            last_activity = last_ts
                        except Exception:
                            pass
                # Exclude only if the entire session ended before ``since``.
                if last_activity < since:
                    continue
            yield session

    def iter_sessions(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        cache: Optional["CacheStore"] = None,
        force_refresh: bool = False,
    ) -> Iterator[SessionRecord]:
        """Iterate sessions across all data roots, deduplicating by (machine, session_id).

        Pass `cache` to enable mtime-gated cache reuse — cuts re-parse time
        on stable session sets to near-zero.  When omitted, every session
        is parsed directly from source (used by tests and callers that do
        not hold a CacheStore).

        Pass `force_refresh=True` (with `cache` set) to force re-parse from
        source while still writing the fresh result back to cache — the
        intended semantics of `ai-growth-mirror generate --no-cache`.
        """
        seen: set[tuple[str, str]] = set()
        for i, root in enumerate(self.data_roots):
            self.data_root = root
            # Index 0 is always the local root; subsequent roots are from
            # local tool data root only
            machine = "local" if i == 0 else root.parent.name
            for session in self._iter_sessions_from_root(
                since, until, cache=cache, force_refresh=force_refresh, machine=machine
            ):
                dedupe_key = (machine, session.session_id)
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    session.source_machine = machine
                    yield session

    def raw_token_totals(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> tuple[int, int, int, int]:
        """Return (input, output, cache_read, cache_write) tokens across ALL sessions
        including sub-agents, for accurate token accounting.
        Default: sum from the already-parsed root sessions (subclasses may override
        to include child sessions that are excluded from iter_sessions)."""
        total_in = total_out = total_cr = total_cw = 0
        for s in self.iter_sessions(since=since, until=until):
            total_in += s.input_tokens or 0
            total_out += s.output_tokens or 0
            total_cr += s.cache_read_tokens or 0
            total_cw += s.cache_write_tokens or 0
        return total_in, total_out, total_cr, total_cw


# ── Shared Utilities ──────────────────────────────────────────────────────────

def parse_iso(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, tolerating various formats."""
    from dateutil import parser as dateutil_parser
    return dateutil_parser.parse(ts)


def content_revision_mtime(value: datetime | str | int | float) -> float:
    """Map a session's last-activity timestamp to a cache revision stamp.

    Prefer this over whole-database ``stat().st_mtime`` when many sessions share
    one file (e.g. Cursor ``state.vscdb``) so unrelated edits do not invalidate
    every cached session read at once.
    """
    if not isinstance(value, datetime):
        value = parse_ts(value)
    if value.tzinfo is None:
        from datetime import timezone as _tz

        value = value.replace(tzinfo=_tz.utc)
    return value.timestamp()


def _max_mtime(paths: "list[Path]") -> float:
    """Return max(stat().st_mtime) over `paths`, or 0.0 if all unreadable.

    Used by adapters to compute SessionRef.source_mtime for cache
    invalidation.  Failures are silent so a missing remote-sync file
    doesn't crash the iteration; 0.0 mtime simply prevents cache hits
    (safe degraded behavior).
    """
    best = 0.0
    for p in paths:
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        if mt > best:
            best = mt
    return best


def parse_ts(value) -> datetime:
    """Parse timestamp from ISO string, Unix seconds (int/float), or Unix milliseconds."""
    from datetime import timezone
    if isinstance(value, (int, float)):
        # Milliseconds if > year 2100 in seconds (i.e. > ~4e9)
        if value > 4_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return parse_iso(str(value))


def detect_language(file_path: str) -> Optional[str]:
    """Return a human-readable language name from a file extension."""
    ext = Path(file_path).suffix.lower()
    EXT_MAP = {
        ".py": "Python", ".ts": "TypeScript", ".js": "JavaScript",
        ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
        ".cs": "C#", ".cpp": "C++", ".c": "C", ".sh": "Shell",
        ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
        ".toml": "TOML", ".sql": "SQL", ".html": "HTML", ".css": "CSS",
    }
    return EXT_MAP.get(ext)


# ---------------------------------------------------------------------------
# Skill-read fingerprint shared helper
# ---------------------------------------------------------------------------

# Recognise SKILL.md reads from any of these skill directory layouts:
#   .claude/skills/<name>/SKILL.md
#   .cursor/skills-cursor/<name>/SKILL.md
#   skills/share/<name>/SKILL.md
#   skills/projects/<project>/<name>/SKILL.md     (last two parts = folder/SKILL.md)
_SKILL_PATH_RE = re.compile(
    r"[/\\](?:skills(?:-cursor)?(?:[/\\](?:share|projects)[/\\][^/\\]+)?)[/\\]([^/\\]+)[/\\]SKILL\.md",
    re.IGNORECASE,
)

# Tool names whose primary purpose is reading a file (not writing)
SKILL_READ_TOOL_NAMES: frozenset[str] = frozenset({
    "readfile", "read", "get_file_contents", "fetchmcpresource",
    "read_file", "view_file",
})


def extract_skill_name_from_path(file_path: str) -> Optional[str]:
    """Return the skill folder name if *file_path* is a SKILL.md read, else None.

    Used by IDE transcript readers (Cursor, Gemini, Cline, CodeBuddy …) to
    detect which configured local-method frameworks were actually invoked in a
    session, by watching for assistant ReadFile calls to SKILL.md paths.
    """
    m = _SKILL_PATH_RE.search(file_path)
    if not m:
        return None
    name = m.group(1).strip()
    return name if name and name.lower() not in (".", "skills", "skills-cursor") else None


def is_absolute_path(p: str) -> bool:
    if not p:
        return False
    # POSIX absolute or Windows absolute (UNC or drive letter)
    if p.startswith("/") or p.startswith("\\"):
        return True
    if len(p) >= 3 and p[1] == ":" and p[2] in ("/", "\\"):
        return True
    return False


def _common_prefix_path(paths: list[str]) -> str:
    import os
    absolute_paths = [p for p in paths if p and is_absolute_path(p)]
    if not absolute_paths:
        return ""
    try:
        if len(absolute_paths) == 1:
            return str(Path(absolute_paths[0]).parent)
        return os.path.commonpath(absolute_paths)
    except Exception:
        return ""


_VSCDB_REVISION_CACHE: dict[str, tuple[str, float]] = {}


def get_vscdb_mtime(state_db: Path) -> float:
    """Extract a stable per-session mtime by watching key AI conversation keys.

    If those keys haven't changed, we return the previously cached mtime to prevent
    cache thrashing caused by unrelated UI state writes (which change file mtime).
    """
    import sqlite3
    import json

    if not state_db.exists():
        return 0.0

    try:
        db_mtime = state_db.stat().st_mtime
    except OSError:
        return 0.0

    db_path_str = str(state_db)

    try:
        with sqlite3.connect(state_db) as conn:
            cursor = conn.execute(
                "SELECT key, value FROM ItemTable "
                "WHERE key LIKE '%input-history%' "
                "OR key LIKE '%ai-agent-storage%' "
                "OR key LIKE '%modelMap%'"
            )
            rows = cursor.fetchall()
            features = sorted([(row[0], row[1]) for row in rows])
            feature_str = json.dumps(features)
    except Exception:
        feature_str = ""

    if db_path_str in _VSCDB_REVISION_CACHE:
        prev_hash, prev_mtime = _VSCDB_REVISION_CACHE[db_path_str]
        if prev_hash == feature_str:
            return prev_mtime

    _VSCDB_REVISION_CACHE[db_path_str] = (feature_str, db_mtime)
    return db_mtime
