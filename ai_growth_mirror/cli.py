"""CLI entry point for the growth mirror product."""
from __future__ import annotations

import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Optional
import click

from . import __version__
from .infra.readers import ADAPTER_BY_NAME
from .config import GrowthMirrorConfig, default_config_path, llm_auth_missing
from .product import PRIMARY_REPORT_FILENAME, SNAPSHOT_ARCHIVE_DIRNAME
from .application.run_identity import resolve_personal_run_id
from .application.orchestrator import (
    GenerateReportRequest,
    InsufficientSessionsError,
    LlmSetupError,
    MissingLlmAuthError,
    NoSessionsInRangeError,
    NoToolDataError,
    TOOL_CHOICES as INGEST_TOOL_CHOICES,
    generate_report_artifacts,
    resolve_requested_tools,
)
from .domain.session.scope import SessionScope
from .application.snapshot_service import compare_snapshots

_LOG_RUN_ID: ContextVar[str] = ContextVar("growth_mirror_log_run_id", default="-")
_LOG_STAGE: ContextVar[str] = ContextVar("growth_mirror_log_stage", default="-")
_LOG_REPORT_MODE: ContextVar[str] = ContextVar("growth_mirror_log_report_mode", default="-")


class _RunContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _LOG_RUN_ID.get()
        record.stage = _LOG_STAGE.get()
        record.report_mode = _LOG_REPORT_MODE.get()
        return True


def _set_log_context(*, run_id: str | None = None, stage: str | None = None, report_mode: str | None = None) -> None:
    if run_id is not None:
        _LOG_RUN_ID.set(run_id)
    if stage is not None:
        _LOG_STAGE.set(stage)
    if report_mode is not None:
        _LOG_REPORT_MODE.set(report_mode)


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] [run=%(run_id)s stage=%(stage)s mode=%(report_mode)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for _handler in logging.getLogger().handlers:
    _handler.addFilter(_RunContextFilter())
logger = logging.getLogger(__name__)

def _print_missing_llm_auth() -> None:
    config_path = default_config_path()
    click.echo(
        "未检测到可用的 LLM API Key。请通过以下任一方式提供：\n"
        f"1. 在 {config_path} 的 llm.api_key 中配置\n"
        "2. 通过 --api-key 显式传入\n"
        "3. 设置环境变量：DEEPSEEK_API_KEY / ZHIPUAI_API_KEY / OPENAI_API_KEY / "
        "ANTHROPIC_API_KEY / GOOGLE_API_KEY",
        err=True,
    )


@click.group(invoke_without_command=True)
@click.version_option(__version__, "--version", "-V")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Generate growth reports for AI coding sessions."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _parse_tool_choices(ctx, param, value):
    """Accept both comma-separated (-t a,b) and repeated (-t a -t b) tool flags."""
    resolved: list[str] = []
    for raw in value or ():
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            if name not in INGEST_TOOL_CHOICES:
                raise click.BadParameter(
                    f"{name!r} is not one of "
                    + ", ".join(repr(c) for c in INGEST_TOOL_CHOICES)
                    + ".",
                    ctx=ctx,
                    param=param,
                )
            if name not in resolved:
                resolved.append(name)
    return tuple(resolved) or ("all",)


@cli.command("generate")
@click.option(
    "--tools", "-t",
    multiple=True,
    callback=_parse_tool_choices,
    default=["all"],
    help=(
        "Which tools to include. Comma-separated or repeated, e.g. "
        "-t claude,codex or -t claude -t codex. Choices: "
        + ", ".join(INGEST_TOOL_CHOICES)
    ),
)
@click.option("--since", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Start date filter (YYYY-MM-DD)")
@click.option("--until", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="End date filter (YYYY-MM-DD)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path (default: ai-growth-mirror.html)")
@click.option("--config", "-c", type=click.Path(), default=None,
              help="Config YAML path (default: ./config.yaml if present, else ~/.ai-growth-mirror/config.yaml)")
@click.option("--prompt-dir", "prompt_dirs", multiple=True, type=click.Path(path_type=Path),
              help="External prompt asset directory. Repeat to layer overrides without editing source.")
@click.option("--no-cache", is_flag=True,
              help="Force re-analysis: ignore disk cache on read (no TTL; cache "
                   "normally survives until the session log changes or schema bumps). "
                   "Fresh results are still written back.")
@click.option("--llm", type=click.Choice(["claude", "gemini", "openai", "deepseek", "glm", "openai-compatible"]), default=None,
              help="LLM provider for analysis (overrides config)")
@click.option("--model", type=str, default=None,
              help="Model name (overrides config, e.g. aws-claude-sonnet-4-6, azure-gpt-5)")
@click.option("--base-url", type=str, default=None,
              help="Custom API base URL for OpenAI-compatible providers")
@click.option("--api-key", type=str, default=None,
              help="API key (overrides config and env vars)")
@click.option("--language", type=click.Choice(["en", "zh"]), default=None,
              help="Report language (overrides config)")
@click.option("--session-read-mode", "session_read_mode", type=click.Choice(["auto", "llm", "heuristic"]), default="auto",
              show_default=True,
              help="Session read mode. 'auto' falls back to local heuristics for "
                   "personal reports when LLM auth is unavailable.")
@click.option(
    "--asset-root",
    "asset_roots",
    multiple=True,
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=(),
    help="AI asset directory to treat as skill/prompt asset creation signals (repeatable). "
         "Example: --asset-root ~/my-agent-hub. Overrides config asset_roots.",
)
@click.option(
    "--hub-root",
    "hub_root",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Root directory of your agent hub (skills/prompts/rules). Used to compute asset footprint.",
)
@click.option(
    "--min-quality",
    type=click.Choice(["low", "medium", "high"]),
    default=None,
    help="Minimum session quality included in analysis (overrides config.report.min_quality).",
)
@click.option("--max-sessions", type=int, default=500,
              help="Max sessions for LLM session-read extraction per tool (default: 500, 0=unlimited). "
                   "Uses time-stratified sampling to ensure all time periods are covered.")
@click.option("--workers", type=int, default=None,
              help="Concurrent LLM calls during session-read extraction (default: auto-scaled "
                   "1 worker per ~50 sessions, capped at 16). Increase if your provider "
                   "tolerates higher RPS; decrease if you hit rate limits.")
@click.option("--no-sidecar", is_flag=True,
              help="Skip writing the report.json evidence sidecar next to the HTML report.")
@click.option("--redact", is_flag=True,
              help="Redact project names and internal identifiers for sharing with others")
@click.option("--min-sessions", type=int, default=None,
              help="Override minimum sessions limit (default: 5).")
@click.option("--repo", "scope_repos", multiple=True, type=str,
              help="Limit sessions to repository name/origin matches. Repeat for OR matching.")
@click.option("--dir", "scope_dirs", multiple=True, type=click.Path(path_type=Path),
              help="Limit sessions to project paths under this directory. Repeat for OR matching.")
@click.option("--keyword", "scope_keywords", multiple=True, type=str,
              help="Limit sessions to prompt/metadata keyword matches. Repeat for OR matching.")
@click.option("--hide-wechat", is_flag=True,
              help="Hide WeChat/Official Account from the report footer")
@click.option("--hide-email", is_flag=True,
              help="Hide Email from the report footer")
@click.option("--verbose", "-v", is_flag=True)
def generate_cmd(
    tools,
    since,
    until,
    output,
    config,
    prompt_dirs,
    no_cache,
    llm,
    model,
    base_url,
    api_key,
    language,
    session_read_mode,
    asset_roots,
    hub_root,
    min_quality,
    max_sessions,
    workers,
    no_sidecar,
    redact,
    min_sessions,
    scope_repos,
    scope_dirs,
    scope_keywords,
    hide_wechat,
    hide_email,
    verbose,
):
    """Generate AI Growth Mirror reports for AI coding sessions."""
    _set_log_context(run_id="-", stage="bootstrap", report_mode="personal")
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    cfg = GrowthMirrorConfig.load(Path(config) if config else None)
    if llm:
        cfg.llm.provider = llm
    if model:
        cfg.llm.model = model
    if base_url:
        cfg.llm.base_url = base_url
    if api_key:
        cfg.llm.api_key = api_key
    if language:
        cfg.report.language = language
    if asset_roots:
        cfg.report.asset_roots = list(asset_roots)
    if min_quality:
        cfg.report.min_quality = min_quality

    click.echo(
        f"[Config] 加载配置：provider={cfg.llm.provider}, model={cfg.llm.model}, "
        f"api_key={'已设置' if cfg.llm.api_key else '未设置'}",
        err=False,
    )

    auth_missing = llm_auth_missing(cfg.llm.provider, cfg.llm.api_key)
    if session_read_mode == "auto":
        effective_session_read_mode = "heuristic" if auth_missing else "llm"
    else:
        effective_session_read_mode = session_read_mode
    click.echo(f"[Mode] 分析模式：{effective_session_read_mode}（requested: {session_read_mode}）")

    if effective_session_read_mode == "llm" and auth_missing:
        _print_missing_llm_auth()
        sys.exit(1)

    selected_tool_names = resolve_requested_tools(list(tools))
    since_label = since.strftime("%Y-%m-%d") if since else "last-30-days"
    until_label = until.strftime("%Y-%m-%d") if until else "now"
    scope_filters = SessionScope(
        repos=tuple(
            r.strip()
            for r in (scope_repos if scope_repos else cfg.report.scope_repos)
            if r and str(r).strip()
        ),
        dirs=tuple(scope_dirs if scope_dirs else cfg.report.scope_dirs),
        keywords=tuple(
            k.strip()
            for k in (scope_keywords if scope_keywords else cfg.report.scope_keywords)
            if k and str(k).strip()
        ),
    )
    run_id = resolve_personal_run_id(
        tools=selected_tool_names,
        since_label=since_label,
        until_label=until_label,
        session_read_mode=effective_session_read_mode,
        language=language or cfg.report.language,
        scope_filters=scope_filters,
    )
    _set_log_context(run_id=run_id)
    run_started_at = time.monotonic()
    logger.info("CLI generate invoked (run_id=%s surface=personal)", run_id)
    click.echo(
        f"[Run] id={run_id} (stable scope id) report=personal session_read={effective_session_read_mode} "
        f"started={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    click.echo(
        f"[Run] id={run_id} mode=personal tools={','.join(selected_tool_names)} "
        f"window={since_label}->{until_label}"
    )
    logger.info(
        "Run context resolved: tools=%s since=%s until=%s output=%s profile=%s",
        ",".join(selected_tool_names),
        since_label,
        until_label,
        output or "(default)",
        "personal",
    )

    extract_started_at: float | None = None
    llm_wall_start: float | None = None
    session_read_plan_announced = False

    def progress(message: str) -> None:
        click.echo(message)

    def on_session_read_progress(
        done: int,
        total: int,
        fresh_done: int = 0,
        fresh_total: int = 0,
    ) -> None:
        nonlocal extract_started_at, llm_wall_start, session_read_plan_announced
        now = time.monotonic()
        if extract_started_at is None:
            extract_started_at = now
        if not session_read_plan_announced:
            session_read_plan_announced = True
            if fresh_total == 0:
                click.echo(
                    f"  [{run_id}] session_read：{total} 个全部命中缓存，无需 LLM 请求"
                )
            else:
                click.echo(
                    f"  [{run_id}] session_read：共 {total} 个，"
                    f"缓存 {total - fresh_total} · 待 LLM {fresh_total}（时长按实际请求动态估算）"
                )
        if fresh_total == 0:
            if done == total:
                click.echo()
            return
        if llm_wall_start is None:
            llm_wall_start = now
        elapsed = now - extract_started_at
        llm_elapsed = now - llm_wall_start
        timing_parts: list[str] = [f"elapsed={elapsed:.0f}s"]
        if fresh_done == 0 and llm_elapsed >= 3:
            timing_parts.append("等待首个 LLM 响应…")
        if fresh_done > 0 and llm_wall_start is not None:
            per_req = llm_elapsed / fresh_done
            timing_parts.append(f"~{per_req:.1f}s/req")
            remaining = fresh_total - fresh_done
            if remaining > 0:
                eta = per_req * remaining
                timing_parts.append(f"eta~{eta:.0f}s")
        timing = " " + " ".join(timing_parts) if timing_parts else ""
        llm_part = f" llm {fresh_done}/{fresh_total}" if fresh_total else ""
        click.echo(
            f"\r  [{run_id}] extract {done}/{total}{llm_part}{timing}",
            nl=False,
        )
        if done == total:
            click.echo()
            logger.info(
                "Session-read extraction finished: %d/%d (%d llm) in %.1fs",
                done,
                total,
                fresh_total,
                elapsed,
            )

    effective_hide_wechat = hide_wechat or cfg.report.hide_wechat
    effective_hide_email = hide_email or cfg.report.hide_email

    request = GenerateReportRequest(
        tools=selected_tool_names,
        output_path=Path(output or PRIMARY_REPORT_FILENAME),
        config_path=Path(config) if config else None,
        since=since,
        until=until,
        language=language or cfg.report.language,
        llm_provider=cfg.llm.provider,
        llm_model=cfg.llm.model,
        llm_base_url=cfg.llm.base_url,
        llm_api_key=cfg.llm.api_key,
        session_read_mode=session_read_mode,
        max_sessions=max_sessions,
        workers=workers,
        redact=redact,
        no_sidecar=no_sidecar,
        no_cache=no_cache,
        prompt_dirs=tuple(prompt_dirs),
        asset_roots=list(asset_roots or cfg.report.asset_roots or []),
        min_quality=min_quality or cfg.report.min_quality,
        hub_root=Path(hub_root) if hub_root else None,
        scope_filters=scope_filters,
        progress=progress,
        on_session_read_progress=on_session_read_progress,
        write_manifest=True,
        run_id=run_id,
        min_sessions=min_sessions,
        hide_wechat=effective_hide_wechat,
        hide_email=effective_hide_email,
    )

    _set_log_context(stage="collect")
    try:
        result = generate_report_artifacts(request)
    except NoToolDataError:
        click.echo("No AI coding tool data found. Checked:")
        for tool_name in selected_tool_names:
            adapter_cls = ADAPTER_BY_NAME.get(tool_name)
            if adapter_cls:
                click.echo(f"  - {adapter_cls.display_name}: {adapter_cls.default_data_root}")
        sys.exit(1)
    except NoSessionsInRangeError:
        if scope_filters.has_filters:
            click.echo(
                "No sessions matched the scope filters. Widen the filters or date range.",
                err=True,
            )
        else:
            click.echo("No sessions found for the specified date range.")
        sys.exit(1)
    except InsufficientSessionsError as exc:
        if exc.reason == "session_reads":
            click.echo(
                f"Only {exc.count} session(s) yielded usable session reads - need at least "
                f"{exc.minimum} for reliable analysis. Sessions may be too short or LLM calls failed.",
                err=True,
            )
            sys.exit(1)
        if exc.filtered:
            widen_hint = "Widen the date range, loosen the scope filters, or add more tools."
            suffix = " after filtering"
        else:
            widen_hint = "Widen the date range or add more tools."
            suffix = ""
        click.echo(
            f"Only {exc.count} session(s) found{suffix} — need at least "
            f"{exc.minimum} to generate a meaningful report. {widen_hint}",
            err=True,
        )
        sys.exit(1)
    except MissingLlmAuthError:
        _print_missing_llm_auth()
        sys.exit(1)
    except LlmSetupError as exc:
        click.echo(f"LLM setup failed: {exc}", err=True)
        sys.exit(1)

    _set_log_context(stage="done")
    total_elapsed = time.monotonic() - run_started_at
    logger.info("Run completed successfully in %.1fs", total_elapsed)
    click.echo(f"[Run] id={run_id} done total={total_elapsed:.0f}s")


@cli.command("compare")
@click.argument("left_snapshot_id", type=str)
@click.argument("right_snapshot_id", type=str)
@click.option("--archive-root", type=click.Path(path_type=Path), default=None,
              help=f"Snapshot archive root (default: ./{SNAPSHOT_ARCHIVE_DIRNAME})")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None,
              help="Output HTML path for the comparison page")
@click.option("--language", type=click.Choice(["en", "zh"]), default="zh",
              help="Comparison page language")
def compare_cmd(
    left_snapshot_id: str,
    right_snapshot_id: str,
    archive_root: Path | None,
    output: Path | None,
    language: str,
) -> None:
    """Generate a comparison page from two archived personal-report snapshots."""
    archive_dir = (archive_root or Path.cwd() / SNAPSHOT_ARCHIVE_DIRNAME).expanduser()
    out = compare_snapshots(
        archive_root=archive_dir,
        left_snapshot_id=left_snapshot_id,
        right_snapshot_id=right_snapshot_id,
        output_path=output.expanduser() if output else None,
        language=language,
    )
    click.echo(f"Comparison written to {out.resolve()} (JSON: {out.with_suffix('.json').resolve()})")


@cli.command("status")
@click.option("--config", "-c", type=click.Path(), default=None,
              help="Config YAML path (default: ./config.yaml if present, else ~/.ai-growth-mirror/config.yaml)")
@click.option("--language", type=click.Choice(["en", "zh"]), default=None,
              help="Report language (overrides config)")
def status_cmd(config: str | None, language: str | None) -> None:
    """Show status of weekly sessions and prior action contract."""
    from .application.status_view import print_status_view

    cfg = GrowthMirrorConfig.load(Path(config) if config else None)
    print_status_view(cfg, language)


@cli.group("cache")
def cache_group() -> None:
    """Inspect / maintain the analysis cache."""


@cache_group.command("prune")
@click.option("--config", "-c", "config_path", type=click.Path(), default=None,
              help="Config YAML path (default: ./config.yaml if present, else ~/.ai-growth-mirror/config.yaml)")
@click.option("--dry-run", is_flag=True,
              help="Report what would be deleted without removing anything.")
def cache_prune_cmd(config_path: Optional[str], dry_run: bool) -> None:
    """Delete cache entries whose SCHEMA_VERSION is out of date."""
    from .infra.cache.store import CacheStore

    cfg = GrowthMirrorConfig.load(Path(config_path) if config_path else None)
    cache = CacheStore(cfg.cache.dir)
    counts = cache.evict_stale(dry_run=dry_run)
    total = sum(counts.values())
    verb = "Would remove" if dry_run else "Removed"
    click.echo(
        f"{verb} {total} stale entries "
        f"(records={counts['records']}, reads={counts['reads']})."
    )


if __name__ == "__main__":
    cli()
