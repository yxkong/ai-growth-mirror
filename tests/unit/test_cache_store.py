from pathlib import Path

from ai_growth_mirror.domain.cache_schema import (
    CACHE_SCHEMA_VERSION,
    RECORD_SCHEMA_VERSION,
    SESSION_READ_SCHEMA_VERSION,
)
from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.signals.model import SessionRead
from ai_growth_mirror.infra.cache.store import CacheStore


def test_cache_schema_versions_are_aligned():
    assert RECORD_SCHEMA_VERSION == SESSION_READ_SCHEMA_VERSION == CACHE_SCHEMA_VERSION
    assert SessionRecord.SCHEMA_VERSION == SessionRead.SCHEMA_VERSION == CACHE_SCHEMA_VERSION


def test_cache_meta_roundtrip(tmp_path: Path):
    workspace_tmp = tmp_path / "cache"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    store = CacheStore(workspace_tmp)
    meta = SessionRecord(session_id="abc", tool_name="claude_code", start_time="2026-01-01T00:00:00Z")
    store.write_record(meta)
    loaded = store.read_record("claude_code", "abc")
    assert loaded is not None
    assert loaded.session_id == "abc"


def test_cache_revision_change_is_stale_even_when_revision_decreases(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    meta = SessionRecord(
        session_id="revision",
        tool_name="opencode",
        start_time="2026-01-01T00:00:00Z",
    )
    meta._source_mtime = 9.0
    store.write_record(meta)

    assert store.read_record("opencode", "revision", source_mtime=9.0) is not None
    assert store.read_record("opencode", "revision", source_mtime=4.0) is None
