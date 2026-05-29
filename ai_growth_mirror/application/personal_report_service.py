"""Personal report generation orchestration (I/O, LLM, view assembly)."""

from __future__ import annotations

import json as _json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ..domain.common.contracts import LlmGateway

from ..domain.growth.capability import compute_capability_scores
from ..domain.growth.coaching import CoachingContent
from ..domain.growth.evidence import build_core_evidence, core_evidence_to_dict
from ..domain.growth.model import GrowthProfile
from ..domain.session.model import SessionRecord
from ..domain.session.scope import SessionScope
from ..domain.signals.model import SessionRead
from ..infra.llm.coach import generate_growth_guidance
from ..infra.snapshots import archive_personal_report_snapshot, load_snapshot_index
from ..product import LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES, SNAPSHOT_ARCHIVE_DIRNAME
from .label_catalogs import load_report_label_catalogs
from .html_render import render_personal_report_html, render_share_card_html
from .summary_payload import build_personal_summary_payload
from .report_view import build_personal_report_view


def generate_personal_report(
    *,
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    stats: GrowthProfile,
    tool_display_name: str,
    output_path: Path,
    language: str = "zh",
    redact: bool = False,
    sources_summary: dict | None = None,
    quality_eligible: int | None = None,
    extraction_failed: int = 0,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    scope_filters: SessionScope | None = None,
    since_label: str = "",
    until_label: str = "",
    write_sidecar: bool = True,
    llm: Optional["LlmGateway"] = None,
    session_read_mode: str = "heuristic",
    progress: Callable[[str], None] | None = None,
) -> None:
    capability_scores = compute_capability_scores(stats)
    catalogs = load_report_label_catalogs(language)
    period_label = (
        f"{since_label} → {until_label}"
        if since_label or until_label
        else ""
    )

    coaching: CoachingContent | None = None
    if llm is not None:
        try:
            if progress:
                progress("[Coaching] 生成个性化成长指导内容...")
            coaching = generate_growth_guidance(
                stats=stats,
                capability_scores=capability_scores,
                llm=llm,
                language=language,
                tool_display_name=tool_display_name,
                period_label=period_label,
            )
            if coaching and progress:
                progress("[Coaching] 个性化内容生成完成")
        except Exception:
            pass

    prev_profile, prev_snapshot_created_at = _load_previous_profile(
        output_path.parent / SNAPSHOT_ARCHIVE_DIRNAME
    )

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=session_reads,
        stats=stats,
        tool_display_name=tool_display_name,
        redact=redact,
        since=since,
        until=until,
        asset_stats=stats.agent_asset,
        prev_profile=prev_profile,
        prev_snapshot_created_at=prev_snapshot_created_at,
        coaching=coaching,
        session_read_mode=session_read_mode,
        catalogs=catalogs,
    )
    html = render_personal_report_html(view=view, language=language, redact=redact)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    normalized_summary_path = output_path.with_name(f"{output_path.stem}.summary.json")

    core_payload = core_evidence_to_dict(
        build_core_evidence(
            sessions=sessions,
            facets=session_reads,
            stats=stats,
            tool_display_name=tool_display_name,
            sources_summary=sources_summary or {},
            scope_filters=scope_filters or SessionScope(),
            since_label=since_label,
            until_label=until_label,
            quality_eligible=quality_eligible,
            extraction_failed=extraction_failed,
            redact=redact,
        )
    )
    if write_sidecar:
        sidecar_path = output_path.with_suffix(".json")
        sidecar_path.write_text(
            _json.dumps(core_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    summary_payload = build_personal_summary_payload(view)
    share_html = render_share_card_html(
        summary_payload=summary_payload,
        template_labels=catalogs.template_labels,
        language=language,
    )
    share_path = output_path.with_name(f"{output_path.stem}-share.html")
    share_path.parent.mkdir(parents=True, exist_ok=True)
    share_path.write_text(share_html, encoding="utf-8")
    normalized_summary_path.write_text(
        _json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    archive_personal_report_snapshot(
        output_path=output_path,
        html=html,
        view=view,
        sidecar_payload=core_payload,
    )


def _load_previous_profile(archive_root: Path) -> tuple[dict[str, object] | None, str]:
    """Load the previous snapshot profile, if available, before writing the current one."""
    candidates: list[tuple[str, Path, str]] = []
    for root in _candidate_snapshot_roots(archive_root):
        try:
            index = load_snapshot_index(root)
        except Exception:
            continue
        for entry in index:
            candidates.append((entry.created_at, root, entry.snapshot_id))
    if not candidates:
        return None, ""

    candidates.sort(key=lambda item: item[0], reverse=True)
    for created_at, root, snapshot_id in candidates:
        profile_path = root / "snapshots" / snapshot_id / "profile.json"
        try:
            return _json.loads(profile_path.read_text(encoding="utf-8")), created_at
        except Exception:
            continue
    return None, ""


def _candidate_snapshot_roots(primary_archive_root: Path) -> list[Path]:
    roots = [primary_archive_root]
    for dirname in LEGACY_SNAPSHOT_ARCHIVE_DIRNAMES:
        legacy_root = primary_archive_root.with_name(dirname)
        if legacy_root not in roots:
            roots.append(legacy_root)
    return roots
