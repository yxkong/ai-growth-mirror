"""Disk cache invalidates on content revision + schema, not calendar TTL."""

from pathlib import Path

from ai_growth_mirror.domain.cache_schema import SESSION_READ_SCHEMA_VERSION
from ai_growth_mirror.domain.signals.model import SessionRead
from ai_growth_mirror.infra.cache.store import CacheStore, _is_cache_stale


def test_is_cache_stale_requires_positive_stamps():
    assert not _is_cache_stale(cached_mtime=0.0, source_mtime=100.0)
    assert not _is_cache_stale(cached_mtime=50.0, source_mtime=0.0)
    assert _is_cache_stale(cached_mtime=50.0, source_mtime=100.0)
    assert _is_cache_stale(cached_mtime=100.0, source_mtime=50.0)
    assert not _is_cache_stale(cached_mtime=100.0, source_mtime=100.0)


def test_read_analysis_reuses_unstamped_mtime(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    facets = SessionRead(
        session_id="s1",
        tool_name="codex",
        delivery_outcome="mostly_achieved",
        _source_mtime=0.0,
    )
    store.write_analysis(facets)
    loaded = store.read_analysis("codex", "s1", source_mtime=999.0)
    assert loaded is not None
    assert loaded.delivery_outcome == "mostly_achieved"


def test_read_analysis_invalidates_when_revision_changes(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    facets = SessionRead(
        session_id="s1",
        tool_name="codex",
        delivery_outcome="mostly_achieved",
        _source_mtime=100.0,
    )
    store.write_analysis(facets)
    assert store.read_analysis("codex", "s1", source_mtime=100.0) is not None
    assert store.read_analysis("codex", "s1", source_mtime=50.0) is None
    assert store.read_analysis("codex", "s1", source_mtime=200.0) is None


def test_read_analysis_hits_without_language_stamp(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    facets = SessionRead(
        session_id="s1",
        tool_name="codex",
        delivery_outcome="mostly_achieved",
        _source_mtime=100.0,
    )
    store.write_analysis(facets)
    assert store.read_analysis("codex", "s1", source_mtime=100.0, report_language="zh") is not None


def test_read_analysis_misses_only_when_stamped_language_differs(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    facets = SessionRead(
        session_id="s1",
        tool_name="codex",
        delivery_outcome="mostly_achieved",
        _source_mtime=100.0,
        _report_language="en",
    )
    store.write_analysis(facets)
    assert store.read_analysis("codex", "s1", source_mtime=100.0, report_language="en") is not None
    assert store.read_analysis("codex", "s1", source_mtime=100.0, report_language="zh") is None


def test_schema_mismatch_misses(tmp_path: Path):
    store = CacheStore(tmp_path / "cache")
    path = store._analysis_path("codex", "s1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"SCHEMA_VERSION": "0.1", "session_id": "s1", "tool_name": "codex"}',
        encoding="utf-8",
    )
    assert store.read_analysis("codex", "s1", source_mtime=1.0) is None
    assert SESSION_READ_SCHEMA_VERSION != "0.1"
