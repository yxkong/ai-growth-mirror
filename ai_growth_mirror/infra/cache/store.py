"""On-disk growth signal cache for AI Growth Mirror.

Two payload tiers, each with its own schema version:
  - session records  (SessionRecord)  → records/<tool>/<id>.json
  - session reads    (SessionRead)    → reads/<tool>/<id>.json

Schema bumps invalidate only the affected tier; other tiers survive intact.

There is **no time-based TTL**. Entries are reused until ``SCHEMA_VERSION`` changes
(``cache prune``) or the session's content revision stamp changes (see
``_source_mtime`` / ``SessionRef.source_mtime``).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...domain.cache_schema import (
    RECORD_SCHEMA_VERSION,
    SESSION_READ_SCHEMA_VERSION,
)
from ...domain.session.model import SessionRecord
from ...domain.signals.model import SessionRead
from ..io.atomic import atomic_write_json

logger = logging.getLogger(__name__)


def _is_cache_stale(*, cached_mtime: float, source_mtime: float) -> bool:
    """True when cached payload is older than the session's content revision.

    Both stamps must be positive. Unstamped entries with ``cached_mtime == 0`` stay
    valid until rewritten (or schema bump).
    """
    if source_mtime <= 0:
        return False
    if cached_mtime <= 0:
        return False
    return cached_mtime != source_mtime


@dataclass
class CacheManifest:
    """Summary of what's available in the cache for a given tool."""

    tool_name: str
    record_count: int = 0
    analysis_count: int = 0

    def has_analysis(self, session_id: str) -> bool:
        return self.analysis_count > 0


class CacheStore:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def _record_path(self, tool_name: str, session_id: str, source_machine: str = "local") -> Path:
        machine = source_machine or "local"
        if machine != "local":
            return self.cache_dir / "records" / tool_name / machine / f"{session_id}.json"
        return self.cache_dir / "records" / tool_name / f"{session_id}.json"

    def _analysis_path(self, tool_name: str, session_id: str, source_machine: str = "local") -> Path:
        machine = source_machine or "local"
        if machine != "local":
            return self.cache_dir / "reads" / tool_name / machine / f"{session_id}.json"
        return self.cache_dir / "reads" / tool_name / f"{session_id}.json"

    def read_record(
        self,
        tool_name: str,
        session_id: str,
        source_mtime: Optional[float] = None,
        source_machine: str = "local",
    ) -> Optional[SessionRecord]:
        """Load cached session record.

        If `source_mtime` is provided and both positive revision stamps differ, the entry is
        stale and None is returned.  There is no calendar TTL.  Pass
        ``source_mtime=None`` to skip the revision check.
        """
        path = self._record_path(tool_name, session_id, source_machine)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("SCHEMA_VERSION") != RECORD_SCHEMA_VERSION:
                return None
            if source_mtime is not None:
                cached_mtime = float(d.get("_source_mtime", 0.0) or 0.0)
                if _is_cache_stale(cached_mtime=cached_mtime, source_mtime=source_mtime):
                    return None
            return SessionRecord.from_dict(d)
        except Exception as exc:
            logger.warning(
                "AGM-CACHE-RECORD-INVALID tool=%s exception_type=%s",
                tool_name,
                type(exc).__name__,
            )
            return None

    def write_record(self, meta: SessionRecord) -> None:
        path = self._record_path(meta.tool_name, meta.session_id, meta.source_machine)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, meta.to_dict())

    def read_analysis(
        self,
        tool_name: str,
        session_id: str,
        source_mtime: Optional[float] = None,
        report_language: Optional[str] = None,
        source_machine: str = "local",
    ) -> Optional[SessionRead]:
        """Load cached session analysis, optionally gated by source_mtime freshness.

        See `read_record` docstring for the freshness contract.
        When ``report_language`` is set, only entries **already stamped** with a
        different locale are stale. Unstamped entries without ``_report_language`` still
        hit (prompt-only changes do not force a full session-read re-run).
        """
        path = self._analysis_path(tool_name, session_id, source_machine)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("SCHEMA_VERSION") != SESSION_READ_SCHEMA_VERSION:
                return None
            if source_mtime is not None:
                cached_mtime = float(d.get("_source_mtime", 0.0) or 0.0)
                if _is_cache_stale(cached_mtime=cached_mtime, source_mtime=source_mtime):
                    return None
            if report_language:
                cached_lang = str(d.get("_report_language", "") or "")
                if cached_lang and cached_lang != report_language:
                    return None
            return SessionRead.from_dict(d)
        except Exception as exc:
            logger.warning(
                "AGM-CACHE-READ-INVALID tool=%s exception_type=%s",
                tool_name,
                type(exc).__name__,
            )
            return None

    def write_analysis(self, session_read: SessionRead, source_machine: str = "local") -> None:
        path = self._analysis_path(session_read.tool_name, session_read.session_id, source_machine)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, session_read.to_dict())

    def iter_record_payloads(self):
        """Yield local and per-machine cached record payloads from supported layouts."""
        root = self.cache_dir / "records"
        if not root.is_dir():
            return
        for path in sorted(root.rglob("*.json")):
            relative = path.relative_to(root)
            if len(relative.parts) == 2:
                tool_name, _filename = relative.parts
                source_machine = "local"
            elif len(relative.parts) == 3:
                tool_name, source_machine, _filename = relative.parts
            else:
                logger.warning("AGM-CACHE-PATH-SKIP depth=%d", len(relative.parts))
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning(
                    "AGM-CACHE-RECORD-INVALID tool=%s exception_type=%s",
                    tool_name,
                    type(exc).__name__,
                )
                continue
            if not isinstance(payload, dict):
                logger.warning(
                    "AGM-CACHE-RECORD-INVALID tool=%s exception_type=NonObjectPayload",
                    tool_name,
                )
                continue
            yield source_machine, tool_name, str(payload.get("session_id") or path.stem), payload

    def manifest(self, tool_name: str) -> CacheManifest:
        """Return a lightweight summary of cached payloads for `tool_name`."""

        def _count(subdir: str) -> int:
            p = self.cache_dir / subdir / tool_name
            return len(list(p.rglob("*.json"))) if p.is_dir() else 0

        return CacheManifest(
            tool_name=tool_name,
            record_count=_count("records"),
            analysis_count=_count("reads"),
        )

    def evict_stale(self, *, dry_run: bool = False) -> dict[str, int]:
        """Remove cache files whose SCHEMA_VERSION no longer matches."""
        counts = {"records": 0, "reads": 0}
        if not self.cache_dir.is_dir():
            return counts

        layout = (
            ("records", "records", RECORD_SCHEMA_VERSION),
            ("reads", "reads", SESSION_READ_SCHEMA_VERSION),
        )
        for label, subdir_name, expected_version in layout:
            root = self.cache_dir / subdir_name
            if not root.is_dir():
                continue
            for path in root.rglob("*.json"):
                if not _schema_matches(path, expected_version):
                    counts[label] += 1
                    if not dry_run:
                        path.unlink(missing_ok=True)
        return counts


def _schema_matches(path: Path, expected: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("SCHEMA_VERSION") == expected
    except (OSError, json.JSONDecodeError):
        return False
