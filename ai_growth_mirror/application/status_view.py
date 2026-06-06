"""Console view logic for CLI status query."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
import click

from ..config import GrowthMirrorConfig
from ..infra.snapshots import load_latest_snapshot_meta
from ..product import SNAPSHOT_ARCHIVE_DIRNAME


def print_status_view(config: GrowthMirrorConfig, language: str | None = None) -> None:
    # 1. Resolve language
    lang = language or config.report.language or "zh"

    # 2. Calculate this week's start time (Monday 00:00:00)
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    # 3. Scan cache directory for this week's session records
    cache_dir = config.cache.dir
    records_dir = cache_dir / "records"
    this_week_sessions = []

    if records_dir.exists():
        for tool_dir in records_dir.iterdir():
            if tool_dir.is_dir():
                for file_path in tool_dir.glob("*.json"):
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        data = json.loads(content)
                        start_time_str = data.get("start_time", "")
                        if start_time_str:
                            clean_str = start_time_str.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(clean_str)
                            if dt.tzinfo is not None:
                                dt = dt.astimezone().replace(tzinfo=None)
                            if dt >= monday_start:
                                this_week_sessions.append((dt, data.get("session_id", "")))
                    except Exception:
                        continue

    session_count = len(this_week_sessions)
    target = 8
    percent = min(100, int((session_count / target) * 100))
    bar_length = 20
    filled_length = int(bar_length * session_count // target)
    filled_length = min(bar_length, filled_length)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # 4. Load prior action contract
    archive_root = Path.cwd() / SNAPSHOT_ARCHIVE_DIRNAME
    latest_meta = load_latest_snapshot_meta(archive_root)

    # 5. Output
    if lang == "zh":
        click.echo("=== AI Growth Mirror 练习进度状态 ===")
        click.echo(f"本周时间窗口: {monday_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {now.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"本周新增会话: {session_count} 个")
        click.echo(f"本周新增进度: [{bar}] {session_count}/{target} ({percent}%)")
    else:
        click.echo("=== AI Growth Mirror Practice Status ===")
        click.echo(f"Weekly window: {monday_start.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Sessions this week: {session_count}")
        click.echo(f"Weekly progress: [{bar}] {session_count}/{target} ({percent}%)")

    click.echo("")

    if latest_meta:
        snapshots_dir = archive_root / "snapshots"
        latest_snapshot_dir = snapshots_dir / latest_meta.snapshot_id
        profile_path = latest_snapshot_dir / "profile.json"

        priorities = []
        if profile_path.exists():
            try:
                profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
                priorities = profile_data.get("growth_plan", {}).get("priorities", [])
            except Exception:
                pass

        if priorities:
            if lang == "zh":
                click.echo("--- 上期行动合约提醒 ---")
            else:
                click.echo("--- Action Contract Reminder ---")
            for idx, p in enumerate(priorities, 1):
                title = p.get("title", "")
                success_signal = p.get("success_signal", "")
                week_1 = p.get("week_1_actions", [])

                if lang == "zh":
                    click.echo(f"{idx}. 核心提升目标: {title}")
                    if success_signal:
                        click.echo(f"   成功信号: {success_signal}")
                    if week_1:
                        click.echo(f"   练习行动: {week_1[0]}")
                else:
                    click.echo(f"{idx}. Core target: {title}")
                    if success_signal:
                        click.echo(f"   Success signal: {success_signal}")
                    if week_1:
                        click.echo(f"   Actions: {week_1[0]}")
        else:
            if lang == "zh":
                click.echo("暂无上期成长计划和行动合约。")
            else:
                click.echo("No previous action contract found.")
    else:
        if lang == "zh":
            click.echo("首次生成，暂无上期合约提醒。")
        else:
            click.echo("No history found (this is your first run).")
