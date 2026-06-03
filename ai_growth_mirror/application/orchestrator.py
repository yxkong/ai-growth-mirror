"""Application orchestrator — session collection and report generation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ..infra.readers import ADAPTER_BY_NAME
from ..domain.ingestion.model import (
    CollectedAdapterView,
    CollectionResult,
    ToolCollectorSpec,
)
from ..domain.session.model import SessionRecord
from ..domain.session.scope import SessionScope, apply_session_scope
from ..domain.session.tool_registry import (
    TOOL_CHOICES,
    resolve_requested_tool_names,
)
from ..infra.cache.store import CacheStore
from ..config import GrowthMirrorConfig, llm_auth_missing
from ..infra.enrichers.asset import scan_asset_roots
from ..domain.growth.scorer import (
    MIN_SESSION_READS_FOR_MIRROR_SCORE,
    MIN_SESSIONS_HARD,
    MIN_SESSIONS_WARN,
    aggregate,
)
from ..infra.extractors.llm import (
    default_session_read_worker_count,
    extract_session_reads_batch,
    should_read_session,
)
from ..infra.extractors.heuristic import build_heuristic_session_reads_batch
from ..infra.llm.factory import make_llm_client
from ..assets.prompts import prompt_asset_scope
from ..product import PRODUCT_RUNTIME_DIRNAME
from .personal_report_service import generate_personal_report

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "last_run_manifest.json"


class ReportGenerationError(Exception):
    """Base class for orchestrator failures surfaced to adapters."""


class NoToolDataError(ReportGenerationError):
    def __init__(self, *, tool_names: list[str]) -> None:
        self.tool_names = tool_names
        super().__init__("No AI coding tool data found.")


class NoSessionsInRangeError(ReportGenerationError):
    pass


class InsufficientSessionsError(ReportGenerationError):
    def __init__(
        self,
        *,
        count: int,
        minimum: int,
        filtered: bool,
        reason: str = "sessions",
    ) -> None:
        self.count = count
        self.minimum = minimum
        self.filtered = filtered
        self.reason = reason
        super().__init__(f"Need at least {minimum} sessions; got {count}.")


class MissingLlmAuthError(ReportGenerationError):
    pass


class LlmSetupError(ReportGenerationError):
    pass


def available_specs() -> dict[str, ToolCollectorSpec]:
    return {
        tool_name: ToolCollectorSpec(
            tool_name=tool_name,
            display_name=getattr(adapter_cls, "display_name", tool_name),
            adapter_cls=adapter_cls,
        )
        for tool_name, adapter_cls in ADAPTER_BY_NAME.items()
    }


def resolve_requested_tools(requested: tuple[str, ...] | list[str]) -> list[str]:
    return resolve_requested_tool_names(requested, list(available_specs().keys()))


def build_data_roots(
    *,
    adapter_cls,
    tool_cfg,
) -> list[Path]:
    """Return local data root only (no remote machine sync)."""
    primary = tool_cfg.data_root if tool_cfg and tool_cfg.data_root else adapter_cls.default_data_root
    return [primary]


def build_adapters(*, cfg: GrowthMirrorConfig, tool_names: list[str]) -> list:
    specs = available_specs()
    adapters = []
    for tool_name in tool_names:
        spec = specs.get(tool_name)
        if spec is None:
            continue
        tool_cfg = cfg.tools.get(tool_name)
        if tool_cfg and not tool_cfg.enabled:
            continue
        data_roots = build_data_roots(
            adapter_cls=spec.adapter_cls,
            tool_cfg=tool_cfg,
        )
        adapter = spec.adapter_cls(
            data_roots=data_roots,
            asset_roots=cfg.report.asset_roots or [],
        )
        if adapter.is_available():
            adapters.append(adapter)
    return adapters


def collect_sessions(
    *,
    cfg: GrowthMirrorConfig,
    tool_names: list[str],
    cache: CacheStore | None,
    since: datetime | None,
    until: datetime | None,
    force_refresh: bool = False,
) -> CollectionResult:
    adapters = build_adapters(cfg=cfg, tool_names=tool_names)
    result = CollectionResult(adapters=adapters)
    for adapter in adapters:
        sessions = list(
            adapter.iter_sessions(
                since=since,
                until=until,
                cache=cache,
                force_refresh=force_refresh,
            )
        )
        result.sessions.extend(sessions)
        result.adapter_views.append(
            CollectedAdapterView(
                tool_name=adapter.tool_name,
                display_name=adapter.display_name,
                session_count=len(sessions),
            )
        )
    if len(adapters) == 1:
        result.display_name = adapters[0].display_name
    else:
        result.display_name = " + ".join(adapter.display_name for adapter in adapters)
    return result


def write_run_manifest(
    *,
    cache: CacheStore,
    sessions: list[SessionRecord],
    since_dt: datetime | None,
    until_dt: datetime | None,
    run_id: str = "",
    runtime_dirname: str = PRODUCT_RUNTIME_DIRNAME,
) -> None:
    """Write a manifest of session IDs used in the last generate run."""
    manifest = {
        "run_id": run_id,
        "session_ids": [s.session_id for s in sessions],
        "since": since_dt.isoformat() if since_dt else None,
        "until": until_dt.isoformat() if until_dt else None,
        "session_count": len(sessions),
    }
    paths = [
        Path.cwd() / runtime_dirname / MANIFEST_FILENAME,
        cache.cache_dir / MANIFEST_FILENAME,
    ]
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            logger.info("Wrote manifest (%d sessions) to %s", len(sessions), path)
            return
        except OSError as exc:
            logger.warning("Failed to write manifest to %s: %s", path, exc)


def _build_sources_summary(
    sessions: list[SessionRecord],
    session_reads: list,
) -> dict[str, dict[str, dict[str, int]]]:
    session_read_ids = {(item.tool_name, item.session_id) for item in session_reads}
    sources_summary: dict[str, dict[str, dict[str, int]]] = {}
    for session in sessions:
        entry = sources_summary.setdefault(session.source_machine, {}).setdefault(
            session.tool_name,
            {"total": 0, "analyzed": 0},
        )
        entry["total"] += 1
        if (session.tool_name, session.session_id) in session_read_ids:
            entry["analyzed"] += 1
    return sources_summary


@dataclass
class GenerateReportRequest:
    tools: list[str]
    output_path: Path
    config_path: Path | None = None
    since: datetime | None = None
    until: datetime | None = None
    language: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    session_read_mode: str = "auto"
    max_sessions: int = 500
    workers: int | None = None
    redact: bool = False
    no_sidecar: bool = False
    no_cache: bool = False
    prompt_dirs: tuple[Path, ...] = ()
    asset_roots: list[Path] = field(default_factory=list)
    min_quality: str | None = None
    hub_root: Optional[Path] = None
    scope_filters: SessionScope = field(default_factory=SessionScope)
    progress: Callable[[str], None] | None = None
    # (done, total, fresh_done, fresh_total) — fresh_* = LLM calls only (excludes cache hits)
    on_session_read_progress: Callable[[int, int, int, int], None] | None = None
    write_manifest: bool = False
    run_id: str = ""


@dataclass
class GenerateReportResult:
    output_path: Path
    display_name: str
    session_count: int
    session_read_count: int
    session_read_mode: str
    growth_level: str = ""
    mirror_score: float = 0.0


def generate_report_artifacts(request: GenerateReportRequest) -> GenerateReportResult:
    cfg = GrowthMirrorConfig.load(request.config_path)
    if request.llm_provider:
        cfg.llm.provider = request.llm_provider
    if request.llm_model:
        cfg.llm.model = request.llm_model
    if request.llm_base_url:
        cfg.llm.base_url = request.llm_base_url
    if request.llm_api_key:
        cfg.llm.api_key = request.llm_api_key
    if request.language:
        cfg.report.language = request.language
    if request.asset_roots:
        cfg.report.asset_roots = request.asset_roots
    if request.min_quality:
        cfg.report.min_quality = request.min_quality

    progress = request.progress or (lambda _message: None)
    tool_names = resolve_requested_tools(request.tools)
    since_dt, until_dt = _effective_window(request.since, request.until)
    since_label = since_dt.strftime("%Y-%m-%d") if since_dt else "all time"
    until_label = until_dt.strftime("%Y-%m-%d") if until_dt else "now"

    adapters = build_adapters(cfg=cfg, tool_names=tool_names)
    if not adapters:
        raise NoToolDataError(tool_names=tool_names)

    cache = CacheStore(cfg.cache.dir)
    cache_for_iter = cache if cfg.cache.enabled else None
    auth_missing = llm_auth_missing(cfg.llm.provider, cfg.llm.api_key)
    effective_session_read_mode = _resolve_session_read_mode(
        requested=request.session_read_mode,
        auth_missing=auth_missing,
    )
    if effective_session_read_mode == "llm" and auth_missing:
        raise MissingLlmAuthError()

    with prompt_asset_scope(*cfg.report.prompt_dirs, *request.prompt_dirs):
        progress(f"Scanning sessions ({since_label} -> {until_label})...")
        collected = collect_sessions(
            cfg=cfg,
            tool_names=tool_names,
            cache=cache_for_iter,
            since=since_dt,
            until=until_dt,
            force_refresh=bool(request.no_cache),
        )
        for item in collected.adapter_views:
            progress(f"  {item.display_name}: {item.session_count} sessions")

        sessions = collected.sessions
        if not sessions:
            raise NoSessionsInRangeError()

        scope_filters = request.scope_filters
        if scope_filters.has_filters:
            before_filter_count = len(sessions)
            progress("Applying session filters:")
            if scope_filters.repos:
                progress(f"  repo: {', '.join(scope_filters.repos)}")
            if scope_filters.dirs:
                progress(
                    "  dir: "
                    + ", ".join(
                        str(path.expanduser().resolve(strict=False))
                        for path in scope_filters.dirs
                    )
                )
            if scope_filters.keywords:
                progress(f"  keyword: {', '.join(scope_filters.keywords)}")
            sessions = apply_session_scope(sessions, scope_filters)
            progress(f"Sessions after filters: {len(sessions)} of {before_filter_count}")

        if not sessions:
            raise NoSessionsInRangeError()

        if len(sessions) < MIN_SESSIONS_HARD:
            raise InsufficientSessionsError(
                count=len(sessions),
                minimum=MIN_SESSIONS_HARD,
                filtered=scope_filters.has_filters,
            )

        if len(sessions) < MIN_SESSIONS_WARN:
            progress(
                f"[Warn] Only {len(sessions)} sessions found (recommended: >={MIN_SESSIONS_WARN}). "
                "Five-axis mirror score and section insights may be less stable."
            )

        progress(f"\nTotal: {len(sessions)} sessions")

        llm_client = None
        if effective_session_read_mode == "llm":
            progress(
                f"[LLM] 初始化客户端：provider={cfg.llm.provider}, model={cfg.llm.model}, "
                f"base_url={cfg.llm.base_url or '(default)'}"
            )
            try:
                llm_client = make_llm_client(
                    cfg.llm.provider,
                    model=cfg.llm.model,
                    api_key=cfg.llm.api_key,
                    base_url=cfg.llm.base_url,
                )
                progress(f"[LLM] 客户端就绪，准备分析 {len(sessions)} 个会话")
            except (ImportError, ValueError) as exc:
                if request.session_read_mode == "auto":
                    progress(
                        f"LLM setup failed: {exc}。已自动切换到本地 heuristic session reads。"
                    )
                    effective_session_read_mode = "heuristic"
                else:
                    raise LlmSetupError(str(exc)) from exc

        coaching_llm_client = llm_client
        if coaching_llm_client is None and cfg.llm.api_key:
            try:
                coaching_llm_client = make_llm_client(
                    cfg.llm.provider,
                    model=cfg.llm.model,
                    api_key=cfg.llm.api_key,
                    base_url=cfg.llm.base_url,
                )
                progress(
                    f"[Coaching] LLM 客户端就绪（session-read 模式={effective_session_read_mode}，"
                    "coaching 独立调用）"
                )
            except Exception as exc:
                progress(
                    f"[Coaching] 个性化教练未启用，继续使用本地 heuristic 建议：{exc}"
                )
                coaching_llm_client = None

        eligible_count = sum(1 for session in sessions if should_read_session(session))
        if effective_session_read_mode == "heuristic":
            progress(
                f"Building session reads (heuristic/offline): {eligible_count} eligible sessions..."
            )
            all_session_reads, session_read_attempted = build_heuristic_session_reads_batch(
                sessions,
                language=cfg.report.language,
                max_sessions=request.max_sessions,
                min_quality=cfg.report.min_quality,
            )
            progress(
                f"Session reads built: {len(all_session_reads)} "
                "(offline heuristic mode, no external LLM call)"
            )
        else:
            effective_workers = (
                request.workers
                if request.workers is not None
                else default_session_read_worker_count(eligible_count)
            )
            progress(
                f"Building session reads (LLM): {eligible_count} eligible sessions × "
                f"{effective_workers} concurrent workers..."
            )
            all_session_reads, session_read_attempted = extract_session_reads_batch(
                sessions,
                llm=llm_client,
                cache=cache,
                max_workers=request.workers,
                max_sessions=request.max_sessions,
                force=request.no_cache,
                on_progress=request.on_session_read_progress,
                language=cfg.report.language,
                min_quality=cfg.report.min_quality,
            )
            failed_count = sum(
                1 for session_read in all_session_reads if getattr(session_read, "extraction_failed", False)
            )
            success_count = len(all_session_reads) - failed_count
            progress(
                f"[SessionRead] 提取完成：成功 {success_count} / {len(all_session_reads)} 个"
            )
            if failed_count == 0:
                progress(f"Session reads built: {len(all_session_reads)}")
            else:
                fail_pct = round(failed_count / len(all_session_reads) * 100) if all_session_reads else 0
                progress(
                    f"Session reads built: {len(all_session_reads)} "
                    f"({success_count} ok / {failed_count} failed -> using defaults, {fail_pct}%)"
                )
                if fail_pct >= 10:
                    progress(
                        f"[Warn] {fail_pct}% of session reads failed (likely LLM rate-limit / timeout). "
                        "Delivery-closure and asset-creation signals may be understated. "
                        "Re-run later or with `--workers N` to throttle."
                    )

        sources_summary = _build_sources_summary(sessions, all_session_reads)
        quality_eligible = eligible_count

        if len(all_session_reads) < MIN_SESSIONS_HARD:
            raise InsufficientSessionsError(
                count=len(all_session_reads),
                minimum=MIN_SESSIONS_HARD,
                filtered=False,
                reason="session_reads",
            )

        if len(all_session_reads) < MIN_SESSION_READS_FOR_MIRROR_SCORE:
            progress(
                f"[Warn] Only {len(all_session_reads)} session reads built - mirror score will be skipped "
                f"(requires >={MIN_SESSION_READS_FOR_MIRROR_SCORE})."
            )

        enrichment_roots: list[Path] = list(cfg.report.asset_roots or [])
        if request.hub_root:
            enrichment_roots.insert(0, request.hub_root)
        local_method_frameworks = list(cfg.report.local_method_frameworks or [])
        asset_stats = None
        if enrichment_roots or local_method_frameworks:
            try:
                asset_stats = scan_asset_roots(
                    enrichment_roots,
                    since=since_dt,
                    until=until_dt,
                    local_method_frameworks=local_method_frameworks,
                )
            except Exception:
                pass

        stats = aggregate(
            sessions,
            all_session_reads,
            tool_name="all" if len(collected.adapters) > 1 else collected.adapters[0].tool_name,
            agent_asset=asset_stats,
        )
        progress(
            f"[Stats] 聚合完成：等级={stats.growth_level or 'N/A'}, "
            f"得分={stats.mirror_score:.1f}, 会话数={stats.session_count}"
        )

        extraction_failed = session_read_attempted - len(all_session_reads)
        output_path = request.output_path.expanduser()
        progress(f"\nGenerating personal report -> {output_path}")
        generate_personal_report(
            sessions=sessions,
            session_reads=all_session_reads,
            stats=stats,
            tool_display_name=collected.display_name,
            output_path=output_path,
            language=cfg.report.language,
            redact=request.redact,
            sources_summary=sources_summary,
            quality_eligible=quality_eligible,
            extraction_failed=extraction_failed,
            since=since_dt,
            until=until_dt,
            scope_filters=scope_filters,
            since_label=since_label,
            until_label=until_label,
            write_sidecar=not request.no_sidecar,
            llm=coaching_llm_client,
            session_read_mode=effective_session_read_mode,
            progress=progress,
        )
        progress(
            f"[Done] 报告已生成：{output_path}  "
            f"（等级 {stats.growth_level or 'N/A'} · {stats.mirror_score:.0f} 分）"
        )

        if request.write_manifest:
            write_run_manifest(
                cache=cache,
                sessions=sessions,
                since_dt=since_dt,
                until_dt=until_dt,
                run_id=request.run_id,
            )

    return GenerateReportResult(
        output_path=output_path,
        display_name=collected.display_name,
        session_count=len(sessions),
        session_read_count=len(all_session_reads),
        session_read_mode=effective_session_read_mode,
        growth_level=stats.growth_level or "",
        mirror_score=stats.mirror_score,
    )


def _effective_window(since: datetime | None, until: datetime | None) -> tuple[datetime | None, datetime | None]:
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    if since is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
    else:
        since_dt = since.replace(tzinfo=local_tz) if since.tzinfo is None else since
    until_dt = None
    if until is not None:
        until_dt = until.replace(tzinfo=local_tz) if until.tzinfo is None else until
        until_dt = until_dt.replace(hour=23, minute=59, second=59)
    return since_dt, until_dt


def _resolve_session_read_mode(*, requested: str, auth_missing: bool) -> str:
    if requested == "auto":
        return "heuristic" if auth_missing else "llm"
    return requested
