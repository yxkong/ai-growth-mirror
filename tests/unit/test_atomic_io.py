"""Atomic text/JSON persistence guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_growth_mirror.infra.io.atomic import atomic_write_json, atomic_write_text
from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.snapshots.model import SnapshotIndexEntry
from ai_growth_mirror.infra.cache.store import CacheStore
from ai_growth_mirror.infra.snapshots import write_snapshot_bundle


def test_atomic_write_text_replaces_complete_file(tmp_path: Path) -> None:
    target = tmp_path / "result.txt"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "new\ncontent")

    assert target.read_text(encoding="utf-8") == "new\ncontent"
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_write_failure_preserves_old_file_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "result.txt"
    target.write_bytes(b"old-bytes")

    def _fail_replace(_source, _target) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("ai_growth_mirror.infra.io.atomic.os.replace", _fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        atomic_write_text(target, "new-content")

    assert target.read_bytes() == b"old-bytes"
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_write_json_uses_utf8_and_stable_format(tmp_path: Path) -> None:
    target = tmp_path / "payload.json"

    atomic_write_json(target, {"message": "可信", "count": 2})

    assert target.read_text(encoding="utf-8") == '{\n  "message": "可信",\n  "count": 2\n}'


def test_cache_write_failure_keeps_previous_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CacheStore(tmp_path / "cache")
    record = SessionRecord(session_id="s1", tool_name="codex", first_prompt="old")
    store.write_record(record)
    record_path = tmp_path / "cache" / "records" / "codex" / "s1.json"
    previous = record_path.read_bytes()

    def _fail_replace(_source, _target) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("ai_growth_mirror.infra.io.atomic.os.replace", _fail_replace)
    record.first_prompt = "new"

    with pytest.raises(OSError, match="replace failed"):
        store.write_record(record)

    assert record_path.read_bytes() == previous
    assert not list(record_path.parent.glob(".*.tmp"))


def test_snapshot_index_failure_removes_only_new_unindexed_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = tmp_path / "archive"
    entry = SnapshotIndexEntry(
        snapshot_id="snapshot-1",
        created_at="2026-09-02T00:00:00+00:00",
        tool_display_name="Synthetic",
        report_title="Synthetic report",
        date_range="",
        report_path="snapshots/snapshot-1/report.html",
        report_json_path="snapshots/snapshot-1/report.json",
        profile_path="snapshots/snapshot-1/profile.json",
        summary_path="snapshots/snapshot-1/summary.json",
        normalized_summary_path="snapshots/snapshot-1/normalized-summary.json",
        compare_hint="",
    )

    def _fail_index(*, archive_root: Path, entry: SnapshotIndexEntry) -> None:
        raise OSError("index failed")

    monkeypatch.setattr(
        "ai_growth_mirror.infra.snapshots._update_snapshot_index", _fail_index
    )

    with pytest.raises(OSError, match="index failed"):
        write_snapshot_bundle(
            archive_root=archive_root,
            snapshot_id="snapshot-1",
            artifacts={"profile.json": "{}", "report.html": "complete"},
            entry=entry,
        )

    snapshots_root = archive_root / "snapshots"
    assert not (snapshots_root / "snapshot-1").exists()
    assert not list(snapshots_root.glob(".*.tmp"))
