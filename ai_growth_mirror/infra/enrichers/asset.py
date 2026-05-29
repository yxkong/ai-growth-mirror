"""Agent asset enricher — scan user-configured skill/prompt/rule directories.

This module is an *enricher*, not an adapter: it does not parse session logs.
Instead it scans one or more root directories (specified by the user via config
or CLI) to surface a snapshot of the user's AI asset library.

The output ``AgentAssetStats`` is injected into ``GrowthProfile`` at report
generation time, providing the "Agent Asset Footprint" card with evidence that
complements the session-derived ``ai_authoring_*`` counters.

Privacy notes
-------------
- All scanning is local and opt-in.
- No file contents are read — only file paths and modification times.
- The resulting stats contain only counts and relative paths; no absolute
  paths containing machine-specific prefixes are included in the report.
"""

from __future__ import annotations

from ...domain.growth.model import AgentAssetStats

import os
from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# File-name patterns recognised as AI asset files.
_SKILL_FILENAMES = frozenset({"SKILL.md", "skill.yaml", "skill.yml"})
_RULE_FILENAMES = frozenset({"PROJECT_RULES.md", "RULES.md", "AGENTS.md", "CLAUDE.md"})
_PROMPT_EXTENSIONS = frozenset({".prompt.md", ".prompt.j2", ".j2"})

# Sub-directory names that typically hold project-scoped assets
_PROJECT_DIR_NAMES = frozenset({"projects", "share"})




def scan_asset_roots(
    asset_roots: list[Path],
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> AgentAssetStats:
    """Scan every root in *asset_roots* and aggregate asset statistics.

    Parameters
    ----------
    asset_roots:
        Directories to scan (from config ``report.asset_roots`` or
        ``--asset-root`` CLI flag).
    since / until:
        Optional time window.  Only files whose ``mtime`` falls within this
        range are included in ``recently_modified_assets``.  If *since* is
        None every file counts as recent.
    """
    stats = AgentAssetStats()
    project_keys: set[str] = set()
    recent: list[tuple[float, str]] = []  # (mtime, relative_label)
    seen_files: set[str] = set()

    since_ts = since.timestamp() if since else None
    until_ts = until.timestamp() if until else None

    for root in asset_roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            continue
        stats.roots_scanned += 1
        _scan_dir(root, root, stats, project_keys, recent, seen_files, since_ts, until_ts)

    stats.hub_project_keys = sorted(project_keys)[:20]
    deduped_recent: dict[str, float] = {}
    for mtime, label in recent:
        deduped_recent[label] = max(mtime, deduped_recent.get(label, 0.0))
    stats.recently_modified_assets = [
        label
        for label, _mtime in sorted(
            deduped_recent.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20]
    ]
    stats.total_asset_files = (
        stats.skill_files_count + stats.prompt_files_count + stats.rule_files_count
    )
    return stats


def _scan_dir(
    path: Path,
    root: Path,
    stats: AgentAssetStats,
    project_keys: set[str],
    recent: list[tuple[float, str]],
    seen_files: set[str],
    since_ts: Optional[float],
    until_ts: Optional[float],
    depth: int = 0,
) -> None:
    """Recursively walk *path*, classify files, and update *stats* in place."""
    if depth > 6:
        return
    try:
        entries = list(os.scandir(path))
    except PermissionError:
        return

    for entry in entries:
        entry_path = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            # Collect project key names from conventional directories
            if entry.name in _PROJECT_DIR_NAMES:
                try:
                    for sub in os.scandir(entry_path):
                        if sub.is_dir():
                            project_keys.add(sub.name)
                except PermissionError:
                    pass
            # Skip hidden dirs except known asset locations
            if entry.name.startswith(".") and entry.name not in {".cursor", ".agents"}:
                continue
            _scan_dir(entry_path, root, stats, project_keys, recent, seen_files, since_ts, until_ts, depth + 1)
        elif entry.is_file(follow_symlinks=False):
            category = _classify_file(entry_path)
            if category is None:
                continue
            normalized_path = os.path.normcase(str(entry_path.resolve(strict=False)))
            if normalized_path in seen_files:
                continue
            seen_files.add(normalized_path)
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            # Apply time window filter for "recently modified" list
            in_window = (since_ts is None or mtime >= since_ts) and (
                until_ts is None or mtime <= until_ts
            )
            if category == "skill":
                stats.skill_files_count += 1
            elif category == "prompt":
                stats.prompt_files_count += 1
            elif category == "rule":
                stats.rule_files_count += 1
            if in_window:
                try:
                    rel = str(entry_path.relative_to(root))
                except ValueError:
                    rel = entry_path.name
                recent.append((mtime, rel))


def _classify_file(path: Path) -> Optional[str]:
    """Return 'skill' | 'prompt' | 'rule' | None."""
    name = path.name
    if name in _SKILL_FILENAMES:
        return "skill"
    if name in _RULE_FILENAMES:
        return "rule"
    lower = name.lower()
    if any(lower.endswith(ext) for ext in _PROMPT_EXTENSIONS):
        return "prompt"
    return None
