"""Snapshot archive persistence, loading, and payload conversion."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..domain.snapshots.model import (
    SnapshotCoverage,
    SnapshotIndexEntry,
    SnapshotMethodAssets,
    SnapshotPromptQuality,
    SnapshotSource,
    SnapshotMeta,
)
from ..domain.snapshots.projection import build_actionable_friction_counts, topic_from_friction
from ..domain.snapshots.trajectory import assess_snapshot_point_confidence
from ..product import CLI_NAME, LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES
from .io.atomic import atomic_write_json, atomic_write_text

logger = logging.getLogger(__name__)

INDEX_FILENAME = "index.json"
SNAPSHOTS_DIRNAME = "snapshots"
COMPARISONS_DIRNAME = "comparisons"


def new_snapshot_id(archive_root: Path) -> str:
    snapshots_root = archive_root / SNAPSHOTS_DIRNAME
    snapshots_root.mkdir(parents=True, exist_ok=True)
    return _new_snapshot_id(snapshots_root)

def relative_to_archive(path: Path, archive_root: Path) -> str:
    return str(path.relative_to(archive_root))


def _remove_task_created_directory(candidate: Path, root: Path) -> None:
    if candidate.parent.resolve() != root.resolve() or not candidate.name:
        raise RuntimeError("Refusing to remove snapshot directory outside its root")
    if candidate.exists():
        shutil.rmtree(candidate)


def write_snapshot_bundle(
    *,
    archive_root: Path,
    snapshot_id: str,
    artifacts: dict[str, str],
    entry: SnapshotIndexEntry,
) -> Path:
    snapshots_root = archive_root / SNAPSHOTS_DIRNAME
    snapshots_root.mkdir(parents=True, exist_ok=True)
    snapshot_dir = snapshots_root / snapshot_id
    staging_dir = snapshots_root / f".{snapshot_id}.{uuid.uuid4().hex}.tmp"
    staging_dir.mkdir(parents=False, exist_ok=False)
    published = False
    try:
        for relative_name, content in artifacts.items():
            atomic_write_text(staging_dir / relative_name, content)
        os.replace(staging_dir, snapshot_dir)
        published = True
        _update_snapshot_index(archive_root=archive_root, entry=entry)
        return snapshot_dir
    except Exception:
        if staging_dir.exists():
            _remove_task_created_directory(staging_dir, snapshots_root)
        if published and snapshot_dir.exists():
            _remove_task_created_directory(snapshot_dir, snapshots_root)
        raise


def write_comparison_artifacts(*, output_path: Path, html: str, payload: dict[str, Any]) -> Path:
    atomic_write_json(output_path.with_suffix(".json"), payload)
    atomic_write_text(output_path, html)
    return output_path


def load_previous_snapshot_source(archive_root: Path) -> SnapshotSource | None:
    candidates: list[tuple[str, Path, str]] = []
    for root in _candidate_snapshot_roots(archive_root):
        try:
            index = load_snapshot_index(root)
        except Exception as exc:
            logger.warning(
                "AGM-SNAPSHOT-READ-SKIP source=index exception_type=%s",
                type(exc).__name__,
            )
            continue
        for entry in index:
            candidates.append((entry.created_at, root, entry.snapshot_id))
    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    for _created_at, root, snapshot_id in candidates:
        try:
            return load_snapshot_source(root / SNAPSHOTS_DIRNAME / snapshot_id)
        except Exception as exc:
            logger.warning(
                "AGM-SNAPSHOT-READ-SKIP source=snapshot exception_type=%s",
                type(exc).__name__,
            )
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
        except Exception as exc:
            logger.warning(
                "AGM-SNAPSHOT-READ-SKIP source=index exception_type=%s",
                type(exc).__name__,
            )
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
        except Exception as exc:
            logger.warning(
                "AGM-SNAPSHOT-READ-SKIP source=snapshot exception_type=%s",
                type(exc).__name__,
            )
            continue
    return sources


def load_snapshot_source(snapshot_dir: Path) -> SnapshotSource:
    profile = read_snapshot_json(snapshot_dir / "profile.json")
    summary = read_snapshot_json(snapshot_dir / "summary.json")
    report = read_snapshot_json(snapshot_dir / "report.json", default={})
    normalized_summary = read_snapshot_json(snapshot_dir / "normalized-summary.json", default={})
    source = snapshot_source_from_payloads(
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
        except TypeError as exc:
            logger.warning(
                "AGM-SNAPSHOT-READ-SKIP source=index-entry exception_type=%s",
                type(exc).__name__,
            )
            continue
    return entries


def load_latest_snapshot_meta(archive_root: Path) -> SnapshotMeta | None:
    index = load_snapshot_index(archive_root)
    if not index:
        return None
    latest = index[0]
    return SnapshotMeta(
        snapshot_id=latest.snapshot_id,
        created_at=latest.created_at,
        tool_display_name=latest.tool_display_name,
        report_title=latest.report_title,
        date_range=latest.date_range,
    )


def snapshot_source_from_payloads(
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
    training_evidence = normalized_summary.get("training_evidence", {}) if isinstance(normalized_summary, dict) else {}
    profile_prompt_coach = profile.get("prompt_coach", {}) if isinstance(profile, dict) else {}
    prompt_quality_dimensions = _prompt_quality_dimensions_from_payloads(
        stats=stats,
        prompt_coach=training_evidence,
        profile_prompt_coach=profile_prompt_coach,
    )
    actionable_friction_counts = build_actionable_friction_counts(
        pq_deficits=dict(stats.get("pq_deficit_counts", {}) or {}),
        friction_type_counts=dict(stats.get("friction_type_counts", {}) or {}),
    )

    action_contracts = []
    growth_plan_data = profile.get("growth_plan", {})
    if isinstance(growth_plan_data, dict):
        priorities = growth_plan_data.get("priorities", [])
        if isinstance(priorities, list):
            for p in priorities:
                if isinstance(p, dict) and p.get("key"):
                    action_contracts.append({
                        "axis_key": p.get("key"),
                        "title": p.get("title", ""),
                        "success_signal": p.get("success_signal", ""),
                        "week_1_actions": p.get("week_1_actions", []),
                        "week_2_actions": p.get("week_2_actions", []),
                    })
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
        assessment_policy_version=str(
            stats.get("assessment_policy_version")
            or summary.get("assessment_policy_version")
            or (profile.get("stats", {}) if isinstance(profile.get("stats"), dict) else {}).get("assessment_policy_version")
            or ""
        ),
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
            training_evidence=training_evidence,
        ),
        sample_count=int(coverage.get("session_read_count", coverage.get("session_count", stats.get("session_count", 0))) or 0),
        human_intervention_session_rate=_as_float(stats.get("human_intervention_session_rate")),
        action_contracts=action_contracts,
    )
    snapshot_source.point_confidence = assess_snapshot_point_confidence(snapshot_source)
    return snapshot_source


def _build_archive_evidence(
    *,
    report: dict[str, Any],
    normalized_summary: dict[str, Any],
    summary: dict[str, Any],
    training_evidence: dict[str, Any],
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
                topic = topic_from_friction(str(signal.get("category", "")))
                if topic:
                    _push(rows, topic, description)
        for signal in item.get("momentum_signals", [])[:3]:
            description = str(signal.get("description", "")).strip()
            if description:
                _push(rows, "overall", description)
    evidence_summary = str(training_evidence.get("evidence_summary", "")).strip()
    if evidence_summary:
        _push(rows, "prompt_quality", evidence_summary)
    for takeaway in training_evidence.get("takeaways", [])[:3]:
        evidence = str(takeaway.get("evidence", "")).strip()
        if evidence:
            _push(rows, "prompt_quality", evidence)
    for deficit in training_evidence.get("top_deficits", [])[:3]:
        description = str(deficit.get("description", "")).strip()
        if description:
            _push(rows, "prompt_quality", description)
    for card in training_evidence.get("rewrite_cards", [])[:3]:
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
    atomic_write_json(index_path, index_data)


def _candidate_snapshot_roots(primary_archive_root: Path) -> list[Path]:
    roots = [primary_archive_root]
    for dirname in LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES:
        legacy_root = primary_archive_root.with_name(dirname)
        if legacy_root not in roots:
            roots.append(legacy_root)
    return roots


def read_snapshot_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
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
