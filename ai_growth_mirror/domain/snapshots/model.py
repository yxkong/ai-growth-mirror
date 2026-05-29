"""Domain contracts for snapshot archive index entries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SnapshotIndexEntry:
    snapshot_id: str
    created_at: str
    tool_display_name: str
    report_title: str
    date_range: str
    report_path: str
    report_json_path: str
    profile_path: str
    summary_path: str
    normalized_summary_path: str
    compare_hint: str
