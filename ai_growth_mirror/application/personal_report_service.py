"""Personal report generation orchestration (I/O, LLM, view assembly)."""

from __future__ import annotations

import logging
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
from ..infra.snapshots import (
    load_previous_snapshot_source,
    load_recent_snapshot_sources,
)
from ..infra.io.atomic import atomic_write_json, atomic_write_text
from ..product import SNAPSHOT_ARCHIVE_DIRNAME
from .label_catalogs import load_report_label_catalogs
from .html_render import render_personal_report_html, render_share_card_html
from .summary_payload import build_personal_summary_payload
from .report_view import build_personal_report_view
from .snapshot_service import archive_personal_report_snapshot

logger = logging.getLogger(__name__)


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
    hide_wechat: bool = False,
    hide_email: bool = False,
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
        except Exception as exc:
            logger.warning(
                "AGM-COACHING-UNAVAILABLE exception_type=%s",
                type(exc).__name__,
            )

    previous_snapshot = load_previous_snapshot_source(
        output_path.parent / SNAPSHOT_ARCHIVE_DIRNAME
    )
    historical_snapshots = load_recent_snapshot_sources(
        output_path.parent / SNAPSHOT_ARCHIVE_DIRNAME,
        window_days=30,
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
        previous_snapshot=previous_snapshot,
        historical_snapshots=historical_snapshots,
        coaching=coaching,
        session_read_mode=session_read_mode,
        quality_eligible=quality_eligible or 0,
        extraction_failed=extraction_failed,
        catalogs=catalogs,
        hide_wechat=hide_wechat,
        hide_email=hide_email,
        llm=llm,
    )
    html = render_personal_report_html(view=view, language=language, redact=redact)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, html)
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
    summary_payload = build_personal_summary_payload(view)
    core_payload["growth_trajectory"] = summary_payload.get("growth_trajectory", {"available": False})
    if "training_evidence" in summary_payload:
        core_payload["training_evidence"] = summary_payload["training_evidence"]
    core_payload["growth_plan"] = summary_payload.get("growth_plan", {})
    if write_sidecar:
        sidecar_path = output_path.with_suffix(".json")
        atomic_write_json(sidecar_path, core_payload)
    share_html = render_share_card_html(
        summary_payload=summary_payload,
        template_labels=catalogs.template_labels,
        language=language,
    )
    share_path = output_path.with_name(f"{output_path.stem}-share.html")
    share_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(share_path, share_html)
    atomic_write_json(normalized_summary_path, summary_payload)
    archive_personal_report_snapshot(
        output_path=output_path,
        html=html,
        view=view,
        sidecar_payload=core_payload,
    )
