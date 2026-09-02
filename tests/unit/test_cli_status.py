"""CLI `status` command output: with-history and no-history paths."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from ai_growth_mirror.application.label_catalogs import STATUS_LABEL_KEYS, load_status_labels
from ai_growth_mirror.application.status_view import print_status_view
from ai_growth_mirror.config import GrowthMirrorConfig
from ai_growth_mirror.product import SNAPSHOT_ARCHIVE_DIRNAME


def test_status_catalogs_match_the_single_application_schema() -> None:
    expected = set(STATUS_LABEL_KEYS)
    assert set(load_status_labels("zh")) == expected
    assert set(load_status_labels("en")) == expected


def _make_config(cache_dir: Path, language: str = "zh") -> GrowthMirrorConfig:
    cfg = GrowthMirrorConfig()
    cfg.cache.dir = cache_dir
    cfg.report.language = language
    return cfg


def _write_record(
    cache_dir: Path,
    tool: str,
    session_id: str,
    start_time: str,
    source_machine: str = "local",
) -> None:
    records_dir = cache_dir / "records" / tool
    if source_machine != "local":
        records_dir /= source_machine
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


def test_status_counts_local_and_per_machine_records_once(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "cache"
    now = datetime.now().isoformat()
    _write_record(cache_dir, "codex", "same", now)
    _write_record(cache_dir, "codex", "same", now, source_machine="laptop")
    _write_record(cache_dir, "codex", "remote", now, source_machine="desktop")

    print_status_view(_make_config(cache_dir))

    assert "本周新增会话: 3 个" in capsys.readouterr().out


def test_status_uses_report_output_dir_for_snapshot_history(tmp_path: Path, capsys, monkeypatch):
    cwd = tmp_path / "cwd"
    output_dir = tmp_path / "reports"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    archive_root = output_dir / SNAPSHOT_ARCHIVE_DIRNAME
    _write_history(
        archive_root,
        "20260901-100000",
        [{"title": "输出目录契约", "success_signal": "命中", "week_1_actions": ["验证"]}],
    )
    cfg = _make_config(tmp_path / "cache")
    cfg.report.output_dir = output_dir

    print_status_view(cfg)

    assert "输出目录契约" in capsys.readouterr().out


def test_status_uses_configured_weekly_target(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _make_config(tmp_path / "cache")
    cfg.report.weekly_session_target = 12

    print_status_view(cfg)

    assert "0/12" in capsys.readouterr().out


def test_status_warns_and_skips_corrupt_record(tmp_path: Path, capsys, caplog, monkeypatch):
    monkeypatch.chdir(tmp_path)
    corrupt = tmp_path / "cache" / "records" / "codex" / "broken.json"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text("{broken", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        print_status_view(_make_config(tmp_path / "cache"))

    assert "本周新增会话: 0 个" in capsys.readouterr().out
    assert "AGM-CACHE-RECORD-INVALID" in caplog.text


def test_status_warns_and_skips_non_object_profile(
    tmp_path: Path, capsys, caplog, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    archive_root = tmp_path / SNAPSHOT_ARCHIVE_DIRNAME
    _write_history(archive_root, "snapshot-invalid", [])
    profile_path = archive_root / "snapshots" / "snapshot-invalid" / "profile.json"
    profile_path.write_text("[]", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        print_status_view(_make_config(tmp_path / "cache"))

    assert "AGM-SNAPSHOT-READ-SKIP source=profile" in caplog.text
    assert "NonObjectPayload" in caplog.text
    assert "暂无上期成长计划和行动合约。" in capsys.readouterr().out


def test_status_scans_one_thousand_records_under_ci_budget(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "cache"
    now = datetime.now().isoformat()
    for index in range(1_000):
        _write_record(cache_dir, "codex", f"s-{index}", now, source_machine="machine")

    started = time.perf_counter()
    print_status_view(_make_config(cache_dir))
    elapsed = time.perf_counter() - started

    assert "本周新增会话: 1000 个" in capsys.readouterr().out
    assert elapsed < 0.5
