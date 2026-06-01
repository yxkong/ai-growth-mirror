"""Snapshot archive loading and compare orchestration."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..application.growth_trajectory import build_snapshot_compare_page_view
from ..application.html_render import render_snapshot_compare_html
from ..application.label_catalogs import load_report_label_catalogs
from ..application.report_view import PersonalReportView
from ..application.summary_payload import build_personal_summary_payload
from ..domain.snapshots.model import (
    SnapshotCoverage,
    SnapshotIndexEntry,
    SnapshotMethodAssets,
    SnapshotPromptQuality,
    SnapshotSource,
)
from ..domain.snapshots.trajectory import assess_snapshot_point_confidence
from ..product import CLI_NAME, LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES, SNAPSHOT_ARCHIVE_DIRNAME

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
        "schema_version": "1.1",
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
    left_source = load_snapshot_source(archive_root / SNAPSHOTS_DIRNAME / left_snapshot_id)
    right_source = load_snapshot_source(archive_root / SNAPSHOTS_DIRNAME / right_snapshot_id)
    catalogs = load_report_label_catalogs(language)
    page = build_snapshot_compare_page_view(
        left_source=left_source,
        right_source=right_source,
        catalogs=catalogs,
    )
    comparisons_root = archive_root / COMPARISONS_DIRNAME
    comparisons_root.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = comparisons_root / f"{left_snapshot_id}__vs__{right_snapshot_id}.html"
    html = render_snapshot_compare_html(
        page=page,
        template_labels=catalogs.template_labels,
        language=language,
    )
    output_path.write_text(html, encoding="utf-8")
    output_path.with_suffix(".json").write_text(
        json.dumps(page.data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


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
    left_source = _snapshot_source_from_payloads(
        profile=left_profile,
        summary=left_summary,
        report=left_report or {},
        normalized_summary=left_normalized_summary or {},
    )
    right_source = _snapshot_source_from_payloads(
        profile=right_profile,
        summary=right_summary,
        report=right_report or {},
        normalized_summary=right_normalized_summary or {},
    )
    catalogs = load_report_label_catalogs(language)
    page = build_snapshot_compare_page_view(
        left_source=left_source,
        right_source=right_source,
        catalogs=catalogs,
    )
    return page.data


def load_previous_snapshot_source(archive_root: Path) -> SnapshotSource | None:
    candidates: list[tuple[str, Path, str]] = []
    for root in _candidate_snapshot_roots(archive_root):
        try:
            index = load_snapshot_index(root)
        except Exception:
            continue
        for entry in index:
            candidates.append((entry.created_at, root, entry.snapshot_id))
    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    for _created_at, root, snapshot_id in candidates:
        try:
            return load_snapshot_source(root / SNAPSHOTS_DIRNAME / snapshot_id)
        except Exception:
            continue
    return None


def load_recent_snapshot_sources(
    archive_root: Path,
    *,
    window_days: int = 30,
) -> list[SnapshotSource]:
    candidates: list[tuple[datetime, Path, str]] = []
    for root in _candidate_snapshot_roots(archive_root):
        try:
            index = load_snapshot_index(root)
        except Exception:
            continue
        for entry in index:
            created_at = _parse_created_at(entry.created_at)
            if created_at is None:
                continue
            candidates.append((created_at, root, entry.snapshot_id))
    if not candidates:
        return []

    latest_dt = max(item[0] for item in candidates)
    cutoff = latest_dt - timedelta(days=window_days)
    recent_candidates = [item for item in candidates if item[0] >= cutoff]
    recent_candidates.sort(key=lambda item: item[0])
    sources: list[SnapshotSource] = []
    seen: set[str] = set()
    for _created_at, root, snapshot_id in recent_candidates:
        source_key = f"{root}:{snapshot_id}"
        if source_key in seen:
            continue
        seen.add(source_key)
        try:
            sources.append(load_snapshot_source(root / SNAPSHOTS_DIRNAME / snapshot_id))
        except Exception:
            continue
    return sources


def load_snapshot_source(snapshot_dir: Path) -> SnapshotSource:
    profile = _read_json(snapshot_dir / "profile.json")
    summary = _read_json(snapshot_dir / "summary.json")
    report = _read_json(snapshot_dir / "report.json", default={})
    normalized_summary = _read_json(snapshot_dir / "normalized-summary.json", default={})
    source = _snapshot_source_from_payloads(
        profile=profile,
        summary=summary,
        report=report,
        normalized_summary=normalized_summary,
    )
    if not source.snapshot_id:
        source.snapshot_id = snapshot_dir.name
    return source


def load_snapshot_index(archive_root: Path) -> list[SnapshotIndexEntry]:
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


def _snapshot_source_from_payloads(
    *,
    profile: dict[str, Any],
    summary: dict[str, Any],
    report: dict[str, Any],
    normalized_summary: dict[str, Any],
) -> SnapshotSource:
    capabilities = normalized_summary.get("capabilities", [])
    if not capabilities:
        capabilities = profile.get("capability", {}).get("dimensions", [])
    axis_scores = {
        item.get("key", ""): float(item.get("score", 0.0))
        for item in capabilities
        if isinstance(item, dict) and item.get("key")
    }
    strongest = max(axis_scores, key=axis_scores.get) if axis_scores else ""
    weakest = min(axis_scores, key=axis_scores.get) if axis_scores else ""
    stats = report.get("stats", {}) if isinstance(report, dict) else {}
    coverage = report.get("coverage", {}) if isinstance(report, dict) else {}
    agent_asset = stats.get("agent_asset") or {}
    prompt_coach = normalized_summary.get("prompt_coach", {}) if isinstance(normalized_summary, dict) else {}
    profile_prompt_coach = profile.get("prompt_coach", {}) if isinstance(profile, dict) else {}
    prompt_quality_dimensions = _prompt_quality_dimensions_from_payloads(
        stats=stats,
        prompt_coach=prompt_coach,
        profile_prompt_coach=profile_prompt_coach,
    )
    actionable_friction_counts = _build_actionable_friction_counts(
        pq_deficits=dict(stats.get("pq_deficit_counts", {}) or {}),
        friction_type_counts=dict(stats.get("friction_type_counts", {}) or {}),
    )
    snapshot_source = SnapshotSource(
        snapshot_id=str(summary.get("snapshot_id", "")),
        created_at=str(summary.get("created_at", "")),
        date_range=str(summary.get("date_range", "")),
        tool_display_name=str(summary.get("tool_display_name", "")),
        growth_level=str(summary.get("stage", normalized_summary.get("summary", {}).get("growth_level", ""))),
        mirror_score=int(summary.get("score", normalized_summary.get("summary", {}).get("mirror_score", 0) or 0)),
        headline=str(summary.get("headline", normalized_summary.get("summary", {}).get("headline", ""))),
        next_focus=str(summary.get("next_focus", normalized_summary.get("summary", {}).get("next_focus", ""))),
        strongest_axis_key=strongest,
        weakest_axis_key=weakest,
        axis_scores=axis_scores,
        prompt_quality_dimensions=prompt_quality_dimensions,
        actionable_friction_counts=actionable_friction_counts,
        prompt_quality=SnapshotPromptQuality(
            efficiency_score=_as_float(stats.get("pq_avg_efficiency_score")),
            evaluated_sessions=int(stats.get("pq_sessions_evaluated", 0) or 0),
            llm_sessions=int(stats.get("pq_llm_session_count", 0) or 0),
            heuristic_sessions=int(stats.get("pq_heuristic_session_count", 0) or 0),
            light_sessions=int(stats.get("pq_light_session_count", 0) or 0),
            deficits=dict(stats.get("pq_deficit_counts", {}) or {}),
        ),
        friction_type_counts=dict(stats.get("friction_type_counts", {}) or {}),
        friction_by_attribution=dict(stats.get("friction_by_attribution", {}) or {}),
        method_assets=SnapshotMethodAssets(
            skill_files=int(agent_asset.get("skill_files", 0) or 0),
            prompt_files=int(agent_asset.get("prompt_files", 0) or 0),
            rule_files=int(agent_asset.get("rule_files", 0) or 0),
            total_asset_files=int(agent_asset.get("total_asset_files", 0) or 0),
            unique_skill_count=int(stats.get("unique_skill_count", 0) or 0),
            workflow_build_substantial_count=int(stats.get("workflow_build_substantial_count", 0) or 0),
            workflow_build_moderate_count=int(stats.get("workflow_build_moderate_count", 0) or 0),
            ai_authoring_distinct_categories=int(stats.get("ai_authoring_distinct_categories", 0) or 0),
            assetized_session_rate=float(stats.get("assetized_session_rate", 0.0) or 0.0),
        ),
        coverage=SnapshotCoverage(
            session_count=int(coverage.get("session_count", stats.get("session_count", 0)) or 0),
            session_read_count=int(coverage.get("session_read_count", 0) or 0),
            quality_eligible=int(coverage.get("quality_eligible", 0) or 0),
            extraction_failed=int(coverage.get("extraction_failed", 0) or 0),
            has_usage_data=_stats_have_usage(stats),
        ),
        evidence_by_topic=_build_archive_evidence(
            report=report,
            normalized_summary=normalized_summary,
            summary=summary,
            prompt_coach=prompt_coach,
        ),
        sample_count=int(coverage.get("session_read_count", coverage.get("session_count", stats.get("session_count", 0))) or 0),
    )
    snapshot_source.point_confidence = assess_snapshot_point_confidence(snapshot_source)
    return snapshot_source


def _build_archive_evidence(
    *,
    report: dict[str, Any],
    normalized_summary: dict[str, Any],
    summary: dict[str, Any],
    prompt_coach: dict[str, Any],
) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {
        "overall": [str(summary.get("headline", "")).strip()],
        "friction": [],
        "prompt_quality": [],
        "method_assets": [],
    }
    for item in report.get("session_read_summaries", [])[:12]:
        takeaway = str(item.get("session_takeaway", "")).strip()
        if takeaway:
            _push(rows, "overall", takeaway)
        for signal in item.get("resistance_signals", [])[:4]:
            description = str(signal.get("description", "")).strip()
            if description:
                _push(rows, "friction", description)
                topic = _topic_from_friction(str(signal.get("category", "")))
                if topic:
                    _push(rows, topic, description)
        for signal in item.get("momentum_signals", [])[:3]:
            description = str(signal.get("description", "")).strip()
            if description:
                _push(rows, "overall", description)
    evidence_summary = str(prompt_coach.get("evidence_summary", "")).strip()
    if evidence_summary:
        _push(rows, "prompt_quality", evidence_summary)
    for takeaway in prompt_coach.get("takeaways", [])[:3]:
        evidence = str(takeaway.get("evidence", "")).strip()
        if evidence:
            _push(rows, "prompt_quality", evidence)
    for deficit in prompt_coach.get("top_deficits", [])[:3]:
        description = str(deficit.get("description", "")).strip()
        if description:
            _push(rows, "prompt_quality", description)
    for card in prompt_coach.get("rewrite_cards", [])[:3]:
        why = str(card.get("why", "")).strip()
        if why:
            _push(rows, "prompt_quality", why)
    for item in normalized_summary.get("exemplars", [])[:3]:
        summary_text = str(item.get("summary", "")).strip()
        if summary_text:
            _push(rows, "method_assets", summary_text)
        reuse = str(item.get("next_reuse", "")).strip()
        if reuse:
            _push(rows, "method_assets", reuse)
    for item in normalized_summary.get("next_actions", [])[:2]:
        why = str(item.get("why", "")).strip()
        if why:
            _push(rows, "overall", why)
    return rows


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


def _candidate_snapshot_roots(primary_archive_root: Path) -> list[Path]:
    roots = [primary_archive_root]
    for dirname in LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES:
        legacy_root = primary_archive_root.with_name(dirname)
        if legacy_root not in roots:
            roots.append(legacy_root)
    return roots


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _prompt_quality_dimensions_from_payloads(
    *,
    stats: dict[str, Any],
    prompt_coach: dict[str, Any],
    profile_prompt_coach: dict[str, Any],
) -> dict[str, float]:
    dims = stats.get("pq_avg_dimensions", {}) or {}
    if dims:
        return {str(key): float(value or 0.0) for key, value in dims.items()}
    for payload in (prompt_coach, profile_prompt_coach):
        rows = payload.get("dimension_scores", []) if isinstance(payload, dict) else []
        if rows:
            converted: dict[str, float] = {}
            for row in rows:
                label = str(row.get("key") or row.get("label") or "").strip()
                if not label:
                    continue
                converted[_prompt_dimension_key(label)] = float(row.get("score", 0.0) or 0.0)
            if converted:
                return converted
    return {}


def _build_actionable_friction_counts(
    *,
    pq_deficits: dict[str, Any],
    friction_type_counts: dict[str, Any],
) -> dict[str, int]:
    return {
        "vague_request": int(pq_deficits.get("vague-request", 0) or 0) + int(friction_type_counts.get("fuzzy-intent", 0) or 0) + int(friction_type_counts.get("ambiguous-request", 0) or 0),
        "missing_context": int(pq_deficits.get("missing-context", 0) or 0) + int(friction_type_counts.get("missing-context", 0) or 0) + int(friction_type_counts.get("context-gap", 0) or 0) + int(friction_type_counts.get("context-confusion", 0) or 0),
        "scope_drift": int(pq_deficits.get("scope-drift", 0) or 0) + int(friction_type_counts.get("scope-creep", 0) or 0) + int(friction_type_counts.get("goal-drift", 0) or 0),
        "missing_acceptance_criteria": int(pq_deficits.get("missing-acceptance-criteria", 0) or 0) + int(friction_type_counts.get("missing-acceptance-criteria", 0) or 0) + int(friction_type_counts.get("incomplete-output", 0) or 0),
        "unclear_correction": int(pq_deficits.get("unclear-correction", 0) or 0) + int(friction_type_counts.get("off-track", 0) or 0) + int(friction_type_counts.get("outdated-context", 0) or 0) + int(friction_type_counts.get("recurring-pattern", 0) or 0),
    }


def _prompt_dimension_key(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "context_provision": "context_provision",
        "request_specificity": "request_specificity",
        "scope_management": "scope_management",
        "information_timing": "information_timing",
        "correction_quality": "correction_quality",
        "上下文建构": "context_provision",
        "请求具体度": "request_specificity",
        "范围管理": "scope_management",
        "信息时机": "information_timing",
        "纠错反馈": "correction_quality",
    }
    return mapping.get(normalized, mapping.get(label, normalized))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stats_have_usage(stats: dict[str, Any]) -> bool:
    return any(
        stats.get(key)
        for key in (
            "total_input_tokens",
            "total_output_tokens",
            "total_cache_read_tokens",
            "total_cache_write_tokens",
            "total_cost_usd",
        )
    )


def _topic_from_friction(category: str) -> str:
    return {
        "ambiguous-request": "intent_clarity",
        "context-confusion": "intent_clarity",
        "context-gap": "intent_clarity",
        "fuzzy-intent": "intent_clarity",
        "goal-drift": "adaptive_recovery",
        "incomplete-output": "delivery_closure",
        "missing-acceptance-criteria": "delivery_closure",
        "missing-context": "intent_clarity",
        "off-track": "adaptive_recovery",
        "outdated-context": "adaptive_recovery",
        "recurring-pattern": "adaptive_recovery",
        "reference-gap": "implementation_depth",
        "repetition": "execution_driving",
        "scope-creep": "execution_driving",
        "tool-ceiling": "implementation_depth",
    }.get(category, "")


def _push(rows: dict[str, list[str]], key: str, value: str) -> None:
    text = (value or "").strip()
    if not text:
        return
    bucket = rows.setdefault(key, [])
    if text not in bucket:
        bucket.append(text)


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
