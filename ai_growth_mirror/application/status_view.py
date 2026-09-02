"""Console view logic for the read-only CLI status query."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import click

from ..config import GrowthMirrorConfig
from ..infra.cache.store import CacheStore
from ..infra.snapshots import load_latest_snapshot_meta
from ..product import SNAPSHOT_ARCHIVE_DIRNAME
from .label_catalogs import load_status_labels

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatusPriority:
    title: str
    success_signal: str
    action: str


@dataclass(frozen=True)
class StatusView:
    monday_start: datetime
    now: datetime
    session_count: int
    target: int
    percent: int
    bar: str
    priorities: tuple[StatusPriority, ...]
    has_history: bool


def _parse_local_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _load_priorities(archive_root: Path) -> tuple[bool, tuple[StatusPriority, ...]]:
    try:
        latest_meta = load_latest_snapshot_meta(archive_root)
    except Exception as exc:
        logger.warning(
            "AGM-SNAPSHOT-READ-SKIP source=index exception_type=%s",
            type(exc).__name__,
        )
        return False, ()
    if latest_meta is None:
        return False, ()
    profile_path = archive_root / "snapshots" / latest_meta.snapshot_id / "profile.json"
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(
            "AGM-SNAPSHOT-READ-SKIP source=profile exception_type=%s",
            type(exc).__name__,
        )
        return True, ()
    if not isinstance(payload, dict):
        logger.warning(
            "AGM-SNAPSHOT-READ-SKIP source=profile exception_type=NonObjectPayload"
        )
        return True, ()
    growth_plan = payload.get("growth_plan", {})
    if not isinstance(growth_plan, dict):
        logger.warning(
            "AGM-SNAPSHOT-READ-SKIP source=profile exception_type=InvalidGrowthPlan"
        )
        return True, ()
    raw_priorities = growth_plan.get("priorities", [])
    if not isinstance(raw_priorities, list):
        logger.warning(
            "AGM-SNAPSHOT-READ-SKIP source=profile exception_type=InvalidPriorities"
        )
        return True, ()
    priorities: list[StatusPriority] = []
    for raw in raw_priorities:
        if not isinstance(raw, dict):
            continue
        actions = raw.get("week_1_actions", [])
        action = str(actions[0]) if isinstance(actions, list) and actions else ""
        priorities.append(
            StatusPriority(
                title=str(raw.get("title", "")),
                success_signal=str(raw.get("success_signal", "")),
                action=action,
            )
        )
    return True, tuple(priorities)


def build_status_view(config: GrowthMirrorConfig, *, now: datetime | None = None) -> StatusView:
    current = now or datetime.now()
    monday = current - timedelta(days=current.weekday())
    monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    seen: set[tuple[str, str, str]] = set()
    for source_machine, tool_name, session_id, payload in CacheStore(
        config.cache.dir
    ).iter_record_payloads():
        started_at = _parse_local_datetime(payload.get("start_time"))
        if started_at is None or started_at < monday_start:
            continue
        seen.add((source_machine, tool_name, session_id))

    target = config.report.weekly_session_target
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValueError("report.weekly_session_target must be a positive integer")
    session_count = len(seen)
    percent = min(100, int((session_count / target) * 100))
    bar_length = 20
    filled_length = min(bar_length, int(bar_length * session_count // target))
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    archive_root = Path(config.report.output_dir) / SNAPSHOT_ARCHIVE_DIRNAME
    has_history, priorities = _load_priorities(archive_root)
    return StatusView(
        monday_start=monday_start,
        now=current,
        session_count=session_count,
        target=target,
        percent=percent,
        bar=bar,
        priorities=priorities,
        has_history=has_history,
    )


def print_status_view(config: GrowthMirrorConfig, language: str | None = None) -> None:
    labels = load_status_labels(language or config.report.language or "zh")
    view = build_status_view(config)
    values = {
        "start": view.monday_start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": view.now.strftime("%Y-%m-%d %H:%M:%S"),
        "count": view.session_count,
        "target": view.target,
        "percent": view.percent,
        "bar": view.bar,
    }
    click.echo(labels["title"])
    click.echo(labels["weekly_window"].format(**values))
    click.echo(labels["weekly_sessions"].format(**values))
    click.echo(labels["weekly_progress"].format(**values))
    click.echo("")

    if view.priorities:
        click.echo(labels["contract_title"])
        for index, priority in enumerate(view.priorities, 1):
            click.echo(labels["target"].format(index=index, title=priority.title))
            if priority.success_signal:
                click.echo(labels["success_signal"].format(value=priority.success_signal))
            if priority.action:
                click.echo(labels["action"].format(value=priority.action))
    elif view.has_history:
        click.echo(labels["no_contract"])
    else:
        click.echo(labels["first_run"])


__all__ = ["StatusPriority", "StatusView", "build_status_view", "print_status_view"]
