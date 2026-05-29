"""Snapshot archive and comparison support for personal growth reports."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ..assets import TEMPLATES_DIR
from ..product import CLI_NAME, SNAPSHOT_ARCHIVE_DIRNAME
from .i18n.catalog import load_catalog

from ..application.report_view import PersonalReportView
from ..application.summary_payload import build_personal_summary_payload
from ..domain.snapshots.model import SnapshotIndexEntry

INDEX_FILENAME = "index.json"
SNAPSHOTS_DIRNAME = "snapshots"
COMPARISONS_DIRNAME = "comparisons"


def archive_personal_report_snapshot(
    *,
    output_path: Path,
    html: str,
    view: PersonalReportView,
    sidecar_payload: dict[str, Any] | None,
) -> Path:
    archive_root = output_path.parent / SNAPSHOT_ARCHIVE_DIRNAME
    snapshots_root = archive_root / SNAPSHOTS_DIRNAME
    snapshots_root.mkdir(parents=True, exist_ok=True)

    snapshot_id = _new_snapshot_id(snapshots_root)
    snapshot_dir = snapshots_root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    report_path = snapshot_dir / "report.html"
    report_json_path = snapshot_dir / "report.json"
    profile_path = snapshot_dir / "profile.json"
    summary_path = snapshot_dir / "summary.json"
    normalized_summary_path = snapshot_dir / "normalized-summary.json"
    meta_path = snapshot_dir / "meta.json"

    profile_dict = asdict(view)
    summary_dict = _build_snapshot_summary(snapshot_id=snapshot_id, view=view)
    meta_dict = {
        "snapshot_id": snapshot_id,
        "created_at": summary_dict["created_at"],
        "schema_version": "1.0",
        "artifact_type": "ai_growth_mirror_snapshot",
    }

    report_path.write_text(html, encoding="utf-8")
    report_json_path.write_text(
        json.dumps(sidecar_payload or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    profile_path.write_text(json.dumps(profile_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    normalized_summary_path.write_text(
        json.dumps(build_personal_summary_payload(view), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta_path.write_text(json.dumps(meta_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    _update_snapshot_index(
        archive_root=archive_root,
        entry=SnapshotIndexEntry(
            snapshot_id=snapshot_id,
            created_at=summary_dict["created_at"],
            tool_display_name=view.tool_display_name,
            report_title=view.report_title,
            date_range=view.date_range,
            report_path=_relative_to_archive(report_path, archive_root),
            report_json_path=_relative_to_archive(report_json_path, archive_root),
            profile_path=_relative_to_archive(profile_path, archive_root),
            summary_path=_relative_to_archive(summary_path, archive_root),
            normalized_summary_path=_relative_to_archive(normalized_summary_path, archive_root),
            compare_hint=f"{CLI_NAME} compare {snapshot_id} <other_snapshot_id>",
        ),
    )
    return snapshot_dir


def compare_snapshots(
    *,
    archive_root: Path,
    left_snapshot_id: str,
    right_snapshot_id: str,
    output_path: Path | None = None,
    language: str = "zh",
) -> Path:
    left_dir = archive_root / SNAPSHOTS_DIRNAME / left_snapshot_id
    right_dir = archive_root / SNAPSHOTS_DIRNAME / right_snapshot_id
    left_profile = json.loads((left_dir / "profile.json").read_text(encoding="utf-8"))
    right_profile = json.loads((right_dir / "profile.json").read_text(encoding="utf-8"))
    left_summary = json.loads((left_dir / "summary.json").read_text(encoding="utf-8"))
    right_summary = json.loads((right_dir / "summary.json").read_text(encoding="utf-8"))

    labels = load_catalog("template_labels", language)
    comparison = build_snapshot_comparison(
        left_profile=left_profile,
        right_profile=right_profile,
        left_summary=left_summary,
        right_summary=right_summary,
        language=language,
        labels=labels,
    )
    comparisons_root = archive_root / COMPARISONS_DIRNAME
    comparisons_root.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = comparisons_root / f"{left_snapshot_id}__vs__{right_snapshot_id}.html"

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("snapshot_compare.html.j2")
    html = template.render(
        comparison=comparison,
        language=language,
        labels=labels,
        theme_variant="snapshot",
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def build_snapshot_comparison(
    *,
    left_profile: dict[str, Any],
    right_profile: dict[str, Any],
    left_summary: dict[str, Any],
    right_summary: dict[str, Any],
    language: str = "zh",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    if labels is None:
        labels = load_catalog("template_labels", language)
    left_metrics = {
        item["key"]: item
        for item in left_profile.get("capability", {}).get("dimensions", [])
    }
    right_metrics = {
        item["key"]: item
        for item in right_profile.get("capability", {}).get("dimensions", [])
    }
    ordered_keys = list(dict.fromkeys([*left_metrics.keys(), *right_metrics.keys()]))
    capability_deltas: list[dict[str, Any]] = []
    for key in ordered_keys:
        left = left_metrics.get(key, {})
        right = right_metrics.get(key, {})
        left_score = float(left.get("score", 0.0))
        right_score = float(right.get("score", 0.0))
        capability_deltas.append(
            {
                "key": key,
                "label": right.get("label") or left.get("label") or key,
                "left_score": left_score,
                "right_score": right_score,
                "delta": round(right_score - left_score, 1),
            }
        )

    best_up = max(capability_deltas, key=lambda item: item["delta"])
    best_down = min(capability_deltas, key=lambda item: item["delta"])
    share_summary = [
        labels["snapshot_share_improvement"].format(
            label=best_up["label"],
            delta=f"{best_up['delta']:+.1f}",
        ),
        labels["snapshot_share_focus_shift"].format(
            focus=right_summary.get("next_focus", ""),
        ),
        labels["snapshot_share_weakest_shift"].format(
            from_label=left_summary.get("weakest_label", ""),
            to_label=right_summary.get("weakest_label", ""),
        ),
    ]
    headline = labels["snapshot_comparison_headline"].format(
        left_id=left_summary.get("snapshot_id"),
        right_id=right_summary.get("snapshot_id"),
        label=best_up["label"],
    )
    return {
        "headline": headline,
        "left": left_summary,
        "right": right_summary,
        "share_summary": share_summary,
        "capability_deltas": capability_deltas,
        "best_up": best_up,
        "best_down": best_down,
        "changed_focus": {
            "from": left_summary.get("next_focus", ""),
            "to": right_summary.get("next_focus", ""),
        },
    }


def load_snapshot_index(archive_root: Path) -> list[SnapshotIndexEntry]:
    """Load snapshot index entries sorted newest-first."""
    index_path = archive_root / INDEX_FILENAME
    if not index_path.exists():
        return []
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    entries: list[SnapshotIndexEntry] = []
    for item in index_data.get("snapshots", []):
        try:
            entries.append(SnapshotIndexEntry(**item))
        except TypeError:
            continue
    return entries


def _update_snapshot_index(*, archive_root: Path, entry: SnapshotIndexEntry) -> None:
    index_path = archive_root / INDEX_FILENAME
    if index_path.exists():
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index_data = {"schema_version": "1.0", "latest_snapshot_id": "", "snapshots": []}
    snapshots = []
    for item in index_data.get("snapshots", []):
        if item.get("snapshot_id") == entry.snapshot_id:
            continue
        item["compare_hint"] = f"{CLI_NAME} compare {item.get('snapshot_id', '<snapshot_id>')} <other_snapshot_id>"
        snapshots.append(item)
    snapshots.append(asdict(entry))
    snapshots.sort(key=lambda item: item["created_at"], reverse=True)
    index_data["latest_snapshot_id"] = entry.snapshot_id
    index_data["snapshots"] = snapshots
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_snapshot_summary(*, snapshot_id: str, view: PersonalReportView) -> dict[str, Any]:
    strongest = view.capability.strongest_label if view.capability else ""
    weakest = view.capability.weakest_label if view.capability else ""
    return {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_title": view.report_title,
        "tool_display_name": view.tool_display_name,
        "date_range": view.date_range,
        "headline": view.summary.headline,
        "stage": view.summary.growth_level,
        "score": view.summary.mirror_score,
        "strongest_label": strongest,
        "weakest_label": weakest,
        "next_focus": view.summary.next_focus,
        "share_title": view.summary.share_title,
        "share_lines": list(view.summary.share_lines),
    }


def _new_snapshot_id(snapshots_root: Path) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = base
    counter = 1
    while (snapshots_root / candidate).exists():
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _relative_to_archive(path: Path, archive_root: Path) -> str:
    return str(path.relative_to(archive_root))
