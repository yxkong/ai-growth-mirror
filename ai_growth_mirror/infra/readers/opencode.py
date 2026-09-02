"""Reader for OpenCode session metadata from .dat files.

OpenCode is an ephemeral-first AI coding tool — it does not persist full
conversation history to disk.  What is available:

  - ``opencode.global.dat``  — global app state containing:
      * ``notification.list`` — events with session ID, timestamp (epoch ms),
        project directory, event type (turn-complete, error, processing-error, …).
      * ``prompt-history``    — recent user prompts (text only, no timestamps,
        no session IDs — cannot be correlated to specific sessions).
      * ``server``            — project worktree list.
  - ``opencode.workspace.<ENCODED_PATH>.<HASH>.dat`` — per-project state:
      * ``workspace:model-selection`` — session ID → {agent, model} mapping.
      * ``workspace:vcs``            — git branch info.

Adapter design:

  - Sessions are reconstructed from ``notification.list`` events grouped by
    session ID.  Each ``turn-complete`` event counts as one user + assistant
    message pair.
  - Model and VCS info are retrieved by scanning workspace dat files.
  - All sessions are marked ``tokens_estimated=True`` because actual API usage
    data is not persisted.

Layout (Windows default)::

    %APPDATA%\\ai.opencode.desktop\\
        opencode.global.dat
        opencode.workspace.<encoded-path>.<hash>.dat   (0+ per project)
"""
from __future__ import annotations

import json
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ...domain.session.model import SessionRecord
from .base import BaseSessionAdapter, SessionRef, parse_iso

logger = logging.getLogger(__name__)


def _event_time_ms(event: dict[str, Any]) -> float | None:
    try:
        value = float(event.get("time"))
        datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return value
    except (TypeError, ValueError, OverflowError, OSError):
        return None


@dataclass(frozen=True)
class _OpenCodeSnapshot:
    events_by_session: dict[str, tuple[dict[str, Any], ...]]
    session_models: dict[str, dict[str, Any]]
    source_paths: tuple[Path, ...]
    source_revision: float


class OpenCodeAdapter(BaseSessionAdapter):
    """Session adapter for OpenCode."""

    tool_name = "opencode"
    display_name = "OpenCode"
    default_data_root = (
        Path(os.environ.get("APPDATA", "")) / "ai.opencode.desktop"
    )

    _GLOBAL_DAT = "opencode.global.dat"
    _WORKSPACE_GLOB = "opencode.workspace.*.dat"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._collection_snapshot: _OpenCodeSnapshot | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_dat(path: Path) -> dict[str, Any]:
        """Read an opencode ``.dat`` file (flat JSON with double-encoded values).

        Returns the fully decoded dictionary, or an empty dict on failure.
        """
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            logger.warning(
                "AGM-OPENCODE-SOURCE-UNREADABLE source_kind=%s exception_type=%s",
                "global" if path.name == OpenCodeAdapter._GLOBAL_DAT else "workspace",
                type(exc).__name__,
            )
            return {}
        decoded: dict[str, Any] = {}
        for key, value in raw.items():
            if not isinstance(value, str):
                decoded[key] = value
                continue
            try:
                decoded[key] = json.loads(value)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "AGM-OPENCODE-FIELD-SKIP source_kind=%s field=%s exception_type=%s",
                    "global" if path.name == OpenCodeAdapter._GLOBAL_DAT else "workspace",
                    key,
                    type(exc).__name__,
                )
        return decoded

    def _build_collection_snapshot(self) -> _OpenCodeSnapshot:
        """Read and index every relevant source exactly once for one collection."""
        global_path = self.data_root / self._GLOBAL_DAT
        workspace_paths = tuple(sorted(self.data_root.glob(self._WORKSPACE_GLOB)))
        source_paths = (global_path, *workspace_paths)
        parsed_sources: list[tuple[Path, dict[str, Any]]] = []
        for source_path in source_paths:
            parsed_sources.append((source_path, self._read_dat(source_path)))

        revision = hashlib.sha256()
        for source_path, payload in parsed_sources:
            try:
                relative_name = source_path.relative_to(self.data_root).as_posix()
            except ValueError:
                relative_name = source_path.name
            revision.update(relative_name.encode("utf-8", errors="replace"))
            revision.update(b"\0")
            revision.update(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            )
            revision.update(b"\0")
        source_revision = float(int.from_bytes(revision.digest()[:6], "big") + 1)

        global_data = parsed_sources[0][1] if parsed_sources else {}
        notification = global_data.get("notification", {})
        events = notification.get("list", []) if isinstance(notification, dict) else []
        grouped_events: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            session_id = str(event.get("session") or "global")
            if session_id == "global":
                continue
            grouped_events.setdefault(session_id, []).append(event)

        session_map: dict[str, dict[str, Any]] = {}
        for _path, ws in parsed_sources[1:]:
            # Model selection
            ms_raw = ws.get("workspace:model-selection", {})
            if isinstance(ms_raw, dict):
                sessions = ms_raw.get("session", {})
                if not isinstance(sessions, dict):
                    continue
                for sid, info in sessions.items():
                    if sid not in session_map:
                        entry = info if isinstance(info, dict) else {}
                        model_info = entry.get("model", {}) or {}
                        session_map[sid] = {
                            "model": model_info.get("modelID", ""),
                            "provider": model_info.get("providerID", ""),
                            "agent": entry.get("agent", ""),
                        }
        invalid_event_time = any(
            _event_time_ms(event) is None
            for items in grouped_events.values()
            for event in items
        )
        if invalid_event_time:
            logger.warning(
                "AGM-OPENCODE-EVENT-TIME-INVALID source_kind=global "
                "exception_type=InvalidTimestamp"
            )
        return _OpenCodeSnapshot(
            events_by_session={
                session_id: tuple(
                    sorted(
                        items,
                        key=lambda item: (
                            _event_time_ms(item) is None,
                            _event_time_ms(item) or 0.0,
                        ),
                    )
                )
                for session_id, items in grouped_events.items()
            },
            session_models=session_map,
            source_paths=source_paths,
            source_revision=source_revision,
        )

    def _snapshot(self, *, refresh: bool = False) -> _OpenCodeSnapshot:
        if refresh or self._collection_snapshot is None:
            self._collection_snapshot = self._build_collection_snapshot()
        return self._collection_snapshot

    # ------------------------------------------------------------------
    # BaseSessionAdapter contract
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return (self.data_root / self._GLOBAL_DAT).is_file()

    def iter_raw_sessions(self) -> Iterator[SessionRef]:
        global_path = self.data_root / self._GLOBAL_DAT
        if not global_path.is_file():
            return

        snapshot = self._snapshot(refresh=True)
        ordered_sessions = sorted(
            snapshot.events_by_session.items(),
            key=lambda item: item[1][0].get("time", 0) if item[1] else 0,
        )
        for sid, events in ordered_sessions:
            first_ts = next(
                (timestamp for event in events if (timestamp := _event_time_ms(event)) is not None),
                0.0,
            )
            start_time = datetime.fromtimestamp(
                first_ts / 1000, tz=timezone.utc
            )
            yield SessionRef(
                session_id=sid,
                tool_name=self.tool_name,
                start_time=start_time,
                source_paths=list(snapshot.source_paths),
                source_mtime=snapshot.source_revision,
            )

    def parse_session(self, raw: SessionRef) -> SessionRecord:
        snapshot = self._snapshot()
        session_events = list(snapshot.events_by_session.get(raw.session_id, ()))

        # Timing
        start_time = raw.start_time.isoformat()
        end_time: str | None = None
        if session_events:
            valid_times = [
                timestamp
                for event in session_events
                if (timestamp := _event_time_ms(event)) is not None
            ]
            if valid_times:
                last_ts = max(valid_times)
                end_dt = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc)
                end_time = end_dt.isoformat()

        turn_count = sum(
            1 for e in session_events if e.get("type") == "turn-complete"
        )

        # Project path from the first event
        project_path = (
            session_events[0].get("directory", "") if session_events else ""
        )

        ws_info = snapshot.session_models.get(raw.session_id, {})
        model_id: str = ws_info.get("model", "")

        models_used = [model_id] if model_id else []

        # Estimate duration
        duration: int | None = None
        if end_time and len(session_events) > 1:
            try:
                start = parse_iso(start_time)
                end = parse_iso(end_time)
                mins = int((end - start).total_seconds() / 60)
                duration = max(1, mins)
            except (TypeError, ValueError, OverflowError):
                duration = None

        record = SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            user_message_count=turn_count,
            assistant_message_count=turn_count,
            models_used=models_used,
            project_path=project_path,
            tokens_estimated=True,
        )

        return record
