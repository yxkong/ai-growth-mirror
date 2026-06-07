"""CLI `status` command output: with-history and no-history paths."""

import json
from datetime import datetime
from pathlib import Path

from ai_growth_mirror.application.status_view import print_status_view
from ai_growth_mirror.config import GrowthMirrorConfig
from ai_growth_mirror.infra.snapshots import SNAPSHOT_ARCHIVE_DIRNAME


def _make_config(cache_dir: Path, language: str = "zh") -> GrowthMirrorConfig:
    cfg = GrowthMirrorConfig()
    cfg.cache.dir = cache_dir
    cfg.report.language = language
    return cfg


def _write_record(cache_dir: Path, tool: str, session_id: str, start_time: str) -> None:
    records_dir = cache_dir / "records" / tool
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / f"{session_id}.json").write_text(
        json.dumps({"session_id": session_id, "start_time": start_time}),
        encoding="utf-8",
    )


def _write_history(archive_root: Path, snapshot_id: str, priorities: list[dict]) -> None:
    snapshot_dir = archive_root / "snapshots" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "profile.json").write_text(
        json.dumps({"growth_plan": {"priorities": priorities}}, ensure_ascii=False),
        encoding="utf-8",
    )
    index = {
        "schema_version": "1.0",
        "latest_snapshot_id": snapshot_id,
        "snapshots": [
            {
                "snapshot_id": snapshot_id,
                "created_at": "2026-06-01 10:00:00",
                "tool_display_name": "Codex CLI",
                "report_title": "test report",
                "date_range": "2026-05-01 – 2026-05-31",
                "report_path": f"snapshots/{snapshot_id}/report.html",
                "report_json_path": f"snapshots/{snapshot_id}/report.json",
                "profile_path": f"snapshots/{snapshot_id}/profile.json",
                "summary_path": f"snapshots/{snapshot_id}/summary.json",
                "normalized_summary_path": f"snapshots/{snapshot_id}/normalized-summary.json",
                "compare_hint": f"ai-growth-mirror compare {snapshot_id} <other_snapshot_id>",
            }
        ],
    }
    (archive_root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )


def test_status_no_history_outputs_first_run_hint(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _make_config(tmp_path / "cache")
    print_status_view(cfg)
    out = capsys.readouterr().out
    assert "首次生成，暂无上期合约提醒。" in out
    assert "本周新增进度" in out


def test_status_with_history_shows_progress_and_contract(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "cache"
    _write_record(cache_dir, "codex", "s1", datetime.now().isoformat())

    archive_root = tmp_path / SNAPSHOT_ARCHIVE_DIRNAME
    _write_history(
        archive_root,
        "20260601-100000",
        [
            {
                "title": "提升协作框定",
                "success_signal": "首轮即给出验收条件",
                "week_1_actions": ["每次任务首轮补齐验收标准"],
            }
        ],
    )

    print_status_view(_make_config(cache_dir))
    out = capsys.readouterr().out
    assert "上期行动合约提醒" in out
    assert "提升协作框定" in out
    assert "1/8" in out


def test_status_no_history_english(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _make_config(tmp_path / "cache", language="en")
    print_status_view(cfg)
    out = capsys.readouterr().out
    assert "No history found" in out
