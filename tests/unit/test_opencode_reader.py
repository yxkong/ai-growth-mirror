"""Tests for OpenCodeAdapter — session reconstruction from .dat metadata."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ai_growth_mirror.infra.readers.base import SessionRef
from ai_growth_mirror.infra.readers.opencode import OpenCodeAdapter


def _make_global_dat(
    path: Path,
    events: list[dict],
    prompt_entries: list[dict] | None = None,
) -> Path:
    """Create a mock ``opencode.global.dat`` at *path* (which must be a
    directory).  Returns the file path."""
    dat = path / "opencode.global.dat"
    payload: dict = {
        "notification": json.dumps({"list": events}),
        "prompt-history": json.dumps({"entries": prompt_entries or []}),
        "server": json.dumps({
            "projects": {"local": [{"worktree": str(path.resolve())}]},
        }),
    }
    dat.write_text(json.dumps(payload), encoding="utf-8")
    return dat


def _make_workspace_dat(
    path: Path,
    filename: str,
    model_selection: dict | None = None,
    vcs: dict | None = None,
) -> Path:
    """Create a mock opencode workspace .dat file."""
    payload: dict = {}
    if model_selection is not None:
        payload["workspace:model-selection"] = json.dumps(model_selection)
    if vcs is not None:
        payload["workspace:vcs"] = json.dumps(vcs)
    dat = path / filename
    dat.write_text(json.dumps(payload), encoding="utf-8")
    return dat


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

def test_is_available_true_when_global_dat_exists(tmp_path: Path):
    _make_global_dat(tmp_path, [])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    assert adapter.is_available()


def test_is_available_false_when_no_data_root(tmp_path: Path):
    empty = tmp_path / "nonexistent"
    adapter = OpenCodeAdapter(data_root=empty)
    assert not adapter.is_available()


def test_is_available_false_when_global_dat_missing(tmp_path: Path):
    adapter = OpenCodeAdapter(data_root=tmp_path)
    assert not adapter.is_available()


# ---------------------------------------------------------------------------
# iter_raw_sessions
# ---------------------------------------------------------------------------

def test_iter_raw_sessions_empty_when_no_events(tmp_path: Path):
    _make_global_dat(tmp_path, [])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_raw_sessions())
    assert sessions == []


def test_iter_raw_sessions_skips_global_session(tmp_path: Path):
    _make_global_dat(tmp_path, [
        {"session": "global", "time": 1781256000000, "type": "error"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_raw_sessions())
    assert sessions == []


def test_iter_raw_sessions_yields_one_ref_per_session(tmp_path: Path):
    _make_global_dat(tmp_path, [
        {"session": "ses_aaa", "time": 1781256000000,
         "directory": str(tmp_path), "type": "turn-complete"},
        {"session": "ses_aaa", "time": 1781256005000,
         "directory": str(tmp_path), "type": "turn-complete"},
        {"session": "ses_bbb", "time": 1781257000000,
         "directory": str(tmp_path), "type": "error"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_raw_sessions())
    assert len(sessions) == 2
    assert sessions[0].session_id == "ses_aaa"
    assert sessions[1].session_id == "ses_bbb"
    assert sessions[0].tool_name == "opencode"


def test_iter_raw_sessions_start_time_from_first_event(tmp_path: Path):
    _make_global_dat(tmp_path, [
        {"session": "ses_1", "time": 1781256000000,
         "directory": str(tmp_path), "type": "error"},
        {"session": "ses_1", "time": 1781256009999,
         "directory": str(tmp_path), "type": "turn-complete"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    sessions = list(adapter.iter_raw_sessions())
    assert len(sessions) == 1
    expected = datetime.fromtimestamp(1781256000, tz=timezone.utc)
    assert sessions[0].start_time == expected


# ---------------------------------------------------------------------------
# parse_session
# ---------------------------------------------------------------------------

def test_parse_session_basic_fields(tmp_path: Path):
    _make_global_dat(tmp_path, [
        {"session": "ses_x", "time": 1781256000000,
         "directory": str(tmp_path), "type": "turn-complete"},
        {"session": "ses_x", "time": 1781256010000,
         "directory": str(tmp_path), "type": "turn-complete"},
        {"session": "ses_x", "time": 1781256020000,
         "directory": str(tmp_path), "type": "turn-complete"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    ref = SessionRef(
        session_id="ses_x",
        tool_name="opencode",
        start_time=datetime.fromtimestamp(1781256000, tz=timezone.utc),
        source_paths=[tmp_path / "opencode.global.dat"],
    )
    record = adapter.parse_session(ref)

    assert record.session_id == "ses_x"
    assert record.tool_name == "opencode"
    assert record.user_message_count == 3
    assert record.assistant_message_count == 3
    assert record.project_path == str(tmp_path)
    assert record.tokens_estimated is True
    # End time should be last event time
    assert record.end_time is not None


def test_parse_session_model_from_workspace(tmp_path: Path):
    _make_global_dat(tmp_path, [
        {"session": "ses_y", "time": 1781256000000,
         "directory": str(tmp_path), "type": "turn-complete"},
    ])
    _make_workspace_dat(
        tmp_path,
        "opencode.workspace.D--test.abc123.dat",
        model_selection={
            "session": {
                "ses_y": {
                    "agent": "build",
                    "model": {"modelID": "deepseek-v4-flash-free",
                              "providerID": "opencode"},
                },
            },
        },
    )
    adapter = OpenCodeAdapter(data_root=tmp_path)
    ref = SessionRef(
        session_id="ses_y",
        tool_name="opencode",
        start_time=datetime.fromtimestamp(1781256000, tz=timezone.utc),
        source_paths=[tmp_path / "opencode.global.dat"],
    )
    record = adapter.parse_session(ref)

    assert record.models_used == ["deepseek-v4-flash-free"]


def test_parse_session_no_turns(tmp_path: Path):
    """Session with only error events, no turn-complete."""
    _make_global_dat(tmp_path, [
        {"session": "ses_z", "time": 1781256000000,
         "directory": str(tmp_path), "type": "error"},
        {"session": "ses_z", "time": 1781256010000,
         "directory": str(tmp_path), "type": "error"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    ref = SessionRef(
        session_id="ses_z",
        tool_name="opencode",
        start_time=datetime.fromtimestamp(1781256000, tz=timezone.utc),
        source_paths=[tmp_path / "opencode.global.dat"],
    )
    record = adapter.parse_session(ref)

    assert record.session_id == "ses_z"
    assert record.user_message_count == 0
    assert record.assistant_message_count == 0
    assert record.end_time is not None


def test_parse_session_duration_computed(tmp_path: Path):
    """Duration in minutes should be computed from first/last event times."""
    _make_global_dat(tmp_path, [
        {"session": "ses_d", "time": 1781256000000,
         "directory": str(tmp_path), "type": "turn-complete"},
        {"session": "ses_d", "time": 1781257800000,  # 30 minutes later
         "directory": str(tmp_path), "type": "turn-complete"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    ref = SessionRef(
        session_id="ses_d",
        tool_name="opencode",
        start_time=datetime.fromtimestamp(1781256000, tz=timezone.utc),
        source_paths=[tmp_path / "opencode.global.dat"],
    )
    record = adapter.parse_session(ref)

    assert record.duration_minutes is not None
    assert record.duration_minutes >= 29  # ~30 min


def test_parse_session_empty_project_path_when_no_events(tmp_path: Path):
    """A session ref with no matching events should still produce a record."""
    _make_global_dat(tmp_path, [
        {"session": "other", "time": 1781256000000,
         "directory": str(tmp_path), "type": "turn-complete"},
    ])
    adapter = OpenCodeAdapter(data_root=tmp_path)
    ref = SessionRef(
        session_id="not_in_events",
        tool_name="opencode",
        start_time=datetime.fromtimestamp(1781256000, tz=timezone.utc),
        source_paths=[tmp_path / "opencode.global.dat"],
    )
    record = adapter.parse_session(ref)

    assert record.session_id == "not_in_events"
    assert record.project_path == ""
    assert record.user_message_count == 0


def test_malformed_encoded_field_does_not_discard_healthy_notifications(
    tmp_path: Path, caplog,
):
    global_path = tmp_path / "opencode.global.dat"
    global_path.write_text(
        json.dumps(
            {
                "notification": json.dumps(
                    {
                        "list": [
                            {
                                "session": "ses_healthy",
                                "time": 1781256000000,
                                "directory": str(tmp_path),
                                "type": "turn-complete",
                            }
                        ]
                    }
                ),
                "prompt-history": "{malformed-json",
            }
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        refs = list(OpenCodeAdapter(data_root=tmp_path).iter_raw_sessions())

    assert [ref.session_id for ref in refs] == ["ses_healthy"]
    assert "AGM-OPENCODE-FIELD-SKIP" in caplog.text


def test_workspace_content_change_changes_source_revision(tmp_path: Path):
    _make_global_dat(
        tmp_path,
        [
            {
                "session": "ses_revision",
                "time": 1781256000000,
                "directory": str(tmp_path),
                "type": "turn-complete",
            }
        ],
    )
    workspace = _make_workspace_dat(
        tmp_path,
        "opencode.workspace.project.hash.dat",
        model_selection={"session": {"ses_revision": {"model": {"modelID": "model-a"}}}},
    )
    first = list(OpenCodeAdapter(data_root=tmp_path).iter_raw_sessions())[0]

    workspace.write_text(
        json.dumps(
            {
                "workspace:model-selection": json.dumps(
                    {"session": {"ses_revision": {"model": {"modelID": "model-b"}}}}
                )
            }
        ),
        encoding="utf-8",
    )
    second = list(OpenCodeAdapter(data_root=tmp_path).iter_raw_sessions())[0]

    assert first.source_mtime > 0
    assert second.source_mtime > 0
    assert second.source_mtime != first.source_mtime
    assert workspace in second.source_paths


def test_collection_reads_each_workspace_only_once(
    tmp_path: Path, monkeypatch,
):
    _make_global_dat(
        tmp_path,
        [
            {"session": "ses_a", "time": 1781256000000, "type": "turn-complete"},
            {"session": "ses_b", "time": 1781257000000, "type": "turn-complete"},
        ],
    )
    workspace = _make_workspace_dat(
        tmp_path,
        "opencode.workspace.project.hash.dat",
        model_selection={
            "session": {
                "ses_a": {"model": {"modelID": "model-a"}},
                "ses_b": {"model": {"modelID": "model-b"}},
            }
        },
    )
    adapter = OpenCodeAdapter(data_root=tmp_path)
    original = adapter._read_dat
    reads: list[Path] = []

    def _tracking_read(path: Path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(adapter, "_read_dat", _tracking_read)
    refs = list(adapter.iter_raw_sessions())
    records = [adapter.parse_session(ref) for ref in refs]

    assert [record.models_used for record in records] == [["model-a"], ["model-b"]]
    assert reads.count(workspace) == 1


def test_malformed_event_time_does_not_break_healthy_session(tmp_path: Path, caplog):
    _make_global_dat(
        tmp_path,
        [
            {"session": "ses_time", "time": "not-a-time", "type": "error"},
            {
                "session": "ses_time",
                "time": 1781256000000,
                "type": "turn-complete",
            },
        ],
    )

    with caplog.at_level(logging.WARNING):
        adapter = OpenCodeAdapter(data_root=tmp_path)
        refs = list(adapter.iter_raw_sessions())
        record = adapter.parse_session(refs[0])

    assert refs[0].start_time == datetime.fromtimestamp(1781256000, tz=timezone.utc)
    assert record.user_message_count == 1
    assert "AGM-OPENCODE-EVENT-TIME-INVALID" in caplog.text


# ---------------------------------------------------------------------------
# Real-data validation belongs to an explicit integration run, not unit tests.
# ---------------------------------------------------------------------------
