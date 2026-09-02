"""Application orchestration for snapshot archive and comparison use cases."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.snapshots.model import SnapshotIndexEntry
from ..infra.snapshots import (
    COMPARISONS_DIRNAME,
    SNAPSHOTS_DIRNAME,
    snapshot_source_from_payloads,
    load_snapshot_source,
    new_snapshot_id,
    read_snapshot_json,
    relative_to_archive,
    write_comparison_artifacts,
    write_snapshot_bundle,
)
from ..product import CLI_NAME, SNAPSHOT_ARCHIVE_DIRNAME
from .growth_trajectory import build_snapshot_compare_page_view
from .html_render import render_snapshot_compare_html
from .label_catalogs import load_report_label_catalogs
from .report_view import PersonalReportView
from .summary_payload import build_personal_summary_payload


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
        "assessment_policy_version": view.stats.assessment_policy_version,
        "strongest_label": strongest,
        "weakest_label": weakest,
        "next_focus": view.summary.next_focus,
        "share_title": view.summary.share_title,
        "share_lines": list(view.summary.share_lines),
    }


def archive_personal_report_snapshot(
    *,
    output_path: Path,
    html: str,
    view: PersonalReportView,
    sidecar_payload: dict[str, Any] | None,
) -> Path:
    archive_root = output_path.parent / SNAPSHOT_ARCHIVE_DIRNAME
    snapshot_id = new_snapshot_id(archive_root)
    snapshot_dir = archive_root / SNAPSHOTS_DIRNAME / snapshot_id
    summary = _build_snapshot_summary(snapshot_id=snapshot_id, view=view)
    meta = {
        "snapshot_id": snapshot_id,
        "created_at": summary["created_at"],
        "schema_version": "1.1",
        "artifact_type": "ai_growth_mirror_snapshot",
        "assessment_policy_version": view.stats.assessment_policy_version,
    }
    artifacts = {
        "report.html": html,
        "report.json": _json_text(sidecar_payload or {}),
        "profile.json": _json_text(asdict(view)),
        "summary.json": _json_text(summary),
        "normalized-summary.json": _json_text(build_personal_summary_payload(view)),
        "meta.json": _json_text(meta),
    }
    entry = SnapshotIndexEntry(
        snapshot_id=snapshot_id,
        created_at=summary["created_at"],
        tool_display_name=view.tool_display_name,
        report_title=view.report_title,
        date_range=view.date_range,
        report_path=relative_to_archive(snapshot_dir / "report.html", archive_root),
        report_json_path=relative_to_archive(snapshot_dir / "report.json", archive_root),
        profile_path=relative_to_archive(snapshot_dir / "profile.json", archive_root),
        summary_path=relative_to_archive(snapshot_dir / "summary.json", archive_root),
        normalized_summary_path=relative_to_archive(
            snapshot_dir / "normalized-summary.json", archive_root
        ),
        compare_hint=f"{CLI_NAME} compare {snapshot_id} <other_snapshot_id>",
    )
    return write_snapshot_bundle(
        archive_root=archive_root,
        snapshot_id=snapshot_id,
        artifacts=artifacts,
        entry=entry,
    )


def compare_snapshots(
    *,
    archive_root: Path,
    left_snapshot_id: str,
    right_snapshot_id: str,
    output_path: Path | None = None,
    language: str = "zh",
) -> Path:
    left_source = load_snapshot_source(archive_root / SNAPSHOTS_DIRNAME / left_snapshot_id)
    right_source = load_snapshot_source(archive_root / SNAPSHOTS_DIRNAME / right_snapshot_id)
    right_normalized = read_snapshot_json(
        archive_root / SNAPSHOTS_DIRNAME / right_snapshot_id / "normalized-summary.json",
        default={},
    )
    current_training_evidence = (
        right_normalized.get("training_evidence", {})
        if isinstance(right_normalized, dict)
        else {}
    )
    catalogs = load_report_label_catalogs(language)
    page = build_snapshot_compare_page_view(
        left_source=left_source,
        right_source=right_source,
        catalogs=catalogs,
        current_training_evidence_payload=current_training_evidence,
    )
    if output_path is None:
        output_path = (
            archive_root
            / COMPARISONS_DIRNAME
            / f"{left_snapshot_id}__vs__{right_snapshot_id}.html"
        )
    html = render_snapshot_compare_html(
        page=page,
        template_labels=catalogs.template_labels,
        language=language,
    )
    return write_comparison_artifacts(output_path=output_path, html=html, payload=page.data)


def build_snapshot_comparison(
    *,
    left_profile: dict[str, Any],
    right_profile: dict[str, Any],
    left_summary: dict[str, Any],
    right_summary: dict[str, Any],
    left_report: dict[str, Any] | None = None,
    right_report: dict[str, Any] | None = None,
    left_normalized_summary: dict[str, Any] | None = None,
    right_normalized_summary: dict[str, Any] | None = None,
    language: str = "zh",
) -> dict[str, Any]:
    left_source = snapshot_source_from_payloads(
        profile=left_profile,
        summary=left_summary,
        report=left_report or {},
        normalized_summary=left_normalized_summary or {},
    )
    right_source = snapshot_source_from_payloads(
        profile=right_profile,
        summary=right_summary,
        report=right_report or {},
        normalized_summary=right_normalized_summary or {},
    )
    catalogs = load_report_label_catalogs(language)
    current_training_evidence = (
        right_normalized_summary.get("training_evidence", {})
        if isinstance(right_normalized_summary, dict)
        else {}
    )
    page = build_snapshot_compare_page_view(
        left_source=left_source,
        right_source=right_source,
        catalogs=catalogs,
        current_training_evidence_payload=current_training_evidence,
    )
    return page.data


__all__ = [
    "archive_personal_report_snapshot",
    "build_snapshot_comparison",
    "compare_snapshots",
]
