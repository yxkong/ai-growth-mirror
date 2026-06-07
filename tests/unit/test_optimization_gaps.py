"""Tests for the newly implemented architecture optimization gaps in AI Growth Mirror."""
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone

from ai_growth_mirror.domain.session.model import SessionRecord, SessionRef
from ai_growth_mirror.domain.growth.scorer import _compute_growth_level
from ai_growth_mirror.infra.readers.base import get_vscdb_mtime, BaseSessionAdapter
from ai_growth_mirror.infra.cache.store import CacheStore


def test_scorer_token_missing_normalization():
    """Verify that omitting token data doesn't unfairly drop scorer metrics."""
    # Scenario A: has token data, but total_token_volume is 0 (it gets penalized under 18% weight)
    _, score_with_zero_tokens, _ = _compute_growth_level(
        avg_chain=6.0,
        verification_rate=1.0,
        heavy_session_rate=0.4,
        heavy_session_count=5,
        total_token_volume=0,  # 0 volume
        mcp_session_rate=0.3,
        subagent_session_rate=0.3,
        total_subagent_invocations=10,
        web_session_rate=0.3,
        tool_build_rate=0.3,
        unique_skill_count=8,
        tier_diversity=4,
        distinct_tool_count=3,
        distinct_model_count=3,
        workflow_build_substantial_count=3,
        workflow_build_moderate_count=3,
        ai_authoring_distinct_categories=3,
        fully_achieved_rate=1.0,
        workflow_structured_count=8,
        session_count=20,
        skill_authored_count=10,
        hook_modified_session_count=5,
        mcp_authored_session_count=5,
        assetized_session_rate=0.8,
        direction_clarity_rate=1.0,
        context_grounding_rate=1.0,
        prompt_dimensions={"request_specificity": 90.0, "context_provision": 90.0, "scope_management": 90.0, "information_timing": 90.0, "correction_quality": 90.0},
        test_run_rate=1.0,
        code_verification_rate=1.0,
        commit_rate=1.0,
        total_files_modified=40,
        friction_by_attribution={"user-actionable": 0, "environmental": 0},
        asset_maturity_bonus=3.0,
        advanced_feature_ratio=0.8,
        skill_usage_session_rate=0.8,
        workflow_fingerprint_session_rate=0.8,
        workflow_reuse_depth=5,
        asset_authoring_session_rate=0.8,
        has_token_data=True,  # Counted!
    )

    # Scenario B: missing token data completely (weight gets dynamically normalized)
    _, score_normalized, _ = _compute_growth_level(
        avg_chain=6.0,
        verification_rate=1.0,
        heavy_session_rate=0.4,
        heavy_session_count=5,
        total_token_volume=0,  # 0 volume but...
        mcp_session_rate=0.3,
        subagent_session_rate=0.3,
        total_subagent_invocations=10,
        web_session_rate=0.3,
        tool_build_rate=0.3,
        unique_skill_count=8,
        tier_diversity=4,
        distinct_tool_count=3,
        distinct_model_count=3,
        workflow_build_substantial_count=3,
        workflow_build_moderate_count=3,
        ai_authoring_distinct_categories=3,
        fully_achieved_rate=1.0,
        workflow_structured_count=8,
        session_count=20,
        skill_authored_count=10,
        hook_modified_session_count=5,
        mcp_authored_session_count=5,
        assetized_session_rate=0.8,
        direction_clarity_rate=1.0,
        context_grounding_rate=1.0,
        prompt_dimensions={"request_specificity": 90.0, "context_provision": 90.0, "scope_management": 90.0, "information_timing": 90.0, "correction_quality": 90.0},
        test_run_rate=1.0,
        code_verification_rate=1.0,
        commit_rate=1.0,
        total_files_modified=40,
        friction_by_attribution={"user-actionable": 0, "environmental": 0},
        asset_maturity_bonus=3.0,
        advanced_feature_ratio=0.8,
        skill_usage_session_rate=0.8,
        workflow_fingerprint_session_rate=0.8,
        workflow_reuse_depth=5,
        asset_authoring_session_rate=0.8,
        has_token_data=False,  # Excluded!
    )

    # Missing token data should result in a higher score than penalizing 0 token volume directly
    assert score_normalized > score_with_zero_tokens


def test_vscdb_mtime_cache_thrashing_prevention(tmp_path: Path):
    """Test get_vscdb_mtime only updates when AI features change."""
    state_db = tmp_path / "state.vscdb"
    
    # 1. Initialize DB structure
    with sqlite3.connect(state_db) as conn:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            ("chat.input-history", json.dumps([{"inputText": "Hello AI"}]))
        )
    
    # Trigger first read
    mtime_1 = get_vscdb_mtime(state_db)
    assert mtime_1 > 0.0
    
    # 2. Simulate unrelated write (UI writes update st_mtime, but ItemTable AI keys don't change)
    time.sleep(0.01)
    # Touch file to force st_mtime change
    state_db.touch()
    
    mtime_2 = get_vscdb_mtime(state_db)
    # The revision mtime must NOT change because input history is identical
    assert mtime_2 == mtime_1
    
    # 3. Modify AI features (user enters new chat message)
    with sqlite3.connect(state_db) as conn:
        conn.execute(
            "UPDATE ItemTable SET value = ? WHERE key = ?",
            (json.dumps([{"inputText": "Hello AI"}, {"inputText": "New Message"}]), "chat.input-history")
        )
    state_db.touch()
    
    mtime_3 = get_vscdb_mtime(state_db)
    # Revision mtime must change now
    assert mtime_3 > mtime_1


def test_multi_machine_cache_isolation(tmp_path: Path):
    """Ensure records from different machines are saved in isolated directories."""
    store = CacheStore(tmp_path)
    
    local_rec = SessionRecord(
        session_id="session-123",
        tool_name="cursor",
        project_path="/local/repo",
        source_machine="local",
    )
    remote_rec = SessionRecord(
        session_id="session-123",
        tool_name="cursor",
        project_path="/remote/repo",
        source_machine="macbook-pro",
    )
    
    store.write_record(local_rec)
    store.write_record(remote_rec)
    
    # Verify different file locations
    local_file = tmp_path / "records" / "cursor" / "session-123.json"
    remote_file = tmp_path / "records" / "cursor" / "macbook-pro" / "session-123.json"
    
    assert local_file.exists()
    assert remote_file.exists()
    
    # Load back and verify they don't overwrite each other
    loaded_local = store.read_record("cursor", "session-123", source_machine="local")
    loaded_remote = store.read_record("cursor", "session-123", source_machine="macbook-pro")
    
    assert loaded_local.project_path == "/local/repo"
    assert loaded_remote.project_path == "/remote/repo"


class DummyAdapter(BaseSessionAdapter):
    tool_name = "dummy"
    display_name = "Dummy Tool"
    
    def __init__(self, data_root):
        super().__init__(data_root=data_root)
        
    def is_available(self) -> bool:
        return True
        
    def iter_raw_sessions(self):
        yield SessionRef(
            session_id="session-lazy",
            tool_name=self.tool_name,
            start_time=datetime.now(timezone.utc),
            source_paths=[],
            source_mtime=1234.5,
        )
        
    def parse_session(self, raw: SessionRef) -> SessionRecord:
        return SessionRecord(
            session_id=raw.session_id,
            tool_name=self.tool_name,
            project_path="/dummy/project",
            first_prompt="Real prompt details",
        )


def test_lazy_placeholder_parsing(tmp_path: Path):
    """Test placeholders are lazily instantiated and saved only when ensure_parsed is called."""
    cache = CacheStore(tmp_path)
    adapter = DummyAdapter(tmp_path)
    
    # 1. Iterate with cache enabled -> generates placeholder
    sessions = list(adapter.iter_sessions(cache=cache))
    assert len(sessions) == 1
    session = sessions[0]
    
    assert session._is_placeholder is True
    assert session.first_prompt == ""  # Blank while placeholder
    assert session.project_path == ""
    
    # Placeholder is NOT written to disk yet
    record_file = tmp_path / "records" / "dummy" / "session-lazy.json"
    assert not record_file.exists()
    
    # 2. Call ensure_parsed -> gets fully parsed and saved to cache
    session.ensure_parsed(cache)
    assert session._is_placeholder is False
    assert session.first_prompt == "Real prompt details"
    assert session.project_path == "/dummy/project"
    
    # Now it is written to disk
    assert record_file.exists()
    
    # 3. Iterate again -> Cache hit returns fully parsed record directly
    sessions_cached = list(adapter.iter_sessions(cache=cache))
    assert len(sessions_cached) == 1
    assert sessions_cached[0]._is_placeholder is False
    assert sessions_cached[0].first_prompt == "Real prompt details"
