"""LLM-backed session-read extraction."""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from contextvars import copy_context
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from jinja2 import Environment

from ...assets.prompts import build_prompt_environment, normalize_report_language
from ...domain.common.contracts import LlmCallRequest, LlmGateway
from ...domain.session.model import SessionRecord
from ...domain.session.heuristics import (
    classify_session_quality,
    detect_active_clarification,
    is_recovery_continuation,
    passes_quality_gate as _passes_quality_gate,
)
from ...domain.signals.framework import detect_frameworks, summarise_for_hint
from ...domain.signals.model import MomentumSignal, ResistanceSignal, SessionRead
from ...domain.signals.payloads import parse_session_read_payload
from ...domain.signals.taxonomy import (
    MOMENTUM_DRIVERS,
    RESISTANCE_ATTRIBUTIONS,
    RESISTANCE_SEVERITIES,
    canonicalize_momentum,
    canonicalize_resistance,
)
from ..cache.store import CacheStore
from ..llm.execution import FACET_SESSION_TIMEOUT_SEC, complete_json_with_retries
from ..llm.limiter import AdaptiveLimiter

logger = logging.getLogger(__name__)

_LOW_DATA_TOOLS = {"gemini_cli"}
_CLAUDE_NATIVE_READS_DIR = Path.home() / ".claude" / "usage-data" / "facets"
_SESSION_READ_SYSTEM_PROMPT_CACHE: dict[str, str] = {}
_RETRY_DELAYS = (5.0, 15.0, 30.0, 60.0)

MIN_USER_MESSAGES = 2
MIN_DURATION_MINUTES = 1
MIN_PROMPT_WORDS = 3


@dataclass(frozen=True)
class _BatchProgress:
    done: int
    total: int
    fresh_done: int
    fresh_total: int


def _authoring_hints_for(meta: SessionRecord) -> str:
    hints: list[str] = []
    if meta.skill_files_authored > 0:
        hints.append(f"{meta.skill_files_authored} skill/agent file(s) authored")
    if meta.hook_config_modified:
        hints.append("hook config modified")
    if meta.mcp_server_authored:
        hints.append("mcp server file/config touched")
    return "; ".join(hints)


def _workflow_hints_for(meta: SessionRecord) -> str:
    hints: list[str] = []
    framework_hint = summarise_for_hint(detect_frameworks(meta))
    if framework_hint:
        hints.append(framework_hint)
    plan_calls = sum(1 for command in meta.slash_commands if command in {"/plan", "/spec"})
    if plan_calls:
        hints.append(f"{plan_calls} /plan or /spec slash command(s)")
    todo_calls = meta.tool_counts.get("TodoWrite", 0) + meta.tool_counts.get("todo_write", 0)
    if todo_calls:
        hints.append(f"{todo_calls} TodoWrite call(s)")
    return "; ".join(hints)


def _parse_resistance_signals(raw: object) -> list[ResistanceSignal]:
    if not isinstance(raw, list):
        return []
    parsed: list[ResistanceSignal] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            confidence = int(item.get("confidence", 70))
        except (TypeError, ValueError):
            confidence = 70
        if confidence < 70:
            continue
        category = canonicalize_resistance(str(item.get("category", "")))
        if not category:
            continue
        attribution = str(item.get("attribution", "")).strip()
        if attribution not in RESISTANCE_ATTRIBUTIONS:
            attribution = "user-actionable"
        severity = str(item.get("severity", "medium")).strip().lower()
        if severity not in RESISTANCE_SEVERITIES:
            severity = "medium"
        parsed.append(
            ResistanceSignal(
                category=category,
                attribution=attribution,
                description=str(item.get("description", ""))[:280],
                severity=severity,
                confidence=max(0, min(100, confidence)),
            )
        )
    return parsed


def _parse_momentum_signals(raw: object) -> list[MomentumSignal]:
    if not isinstance(raw, list):
        return []
    parsed: list[MomentumSignal] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            confidence = int(item.get("confidence", 70))
        except (TypeError, ValueError):
            confidence = 70
        if confidence < 70:
            continue
        category = canonicalize_momentum(str(item.get("category", "")))
        if not category:
            continue
        driver = str(item.get("driver", "")).strip()
        if driver not in MOMENTUM_DRIVERS:
            driver = "ai-driven"
        parsed.append(
            MomentumSignal(
                category=category,
                driver=driver,
                label=str(item.get("label", ""))[:80],
                description=str(item.get("description", ""))[:280],
                confidence=max(0, min(100, confidence)),
            )
        )
    return parsed


def _load_native_claude_session_read(meta: SessionRecord) -> Optional[SessionRead]:
    artifact = _CLAUDE_NATIVE_READS_DIR / f"{meta.session_id}.json"
    if not artifact.exists():
        return None
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception:
        return None

    outcome = payload.get("outcome", "unclear")
    if outcome not in {
        "fully_achieved",
        "mostly_achieved",
        "partially_achieved",
        "ongoing",
        "unclear",
    }:
        outcome = "unclear"

    if meta.mcp_server_authored:
        capability_focus = "tooling_author"
        capability_depth = "moderate"
    elif meta.skill_files_authored > 0 or meta.hook_config_modified:
        capability_focus = "workflow_builder"
        capability_depth = "moderate"
    else:
        capability_focus = "none"
        capability_depth = "incidental"

    return SessionRead(
        session_id=meta.session_id,
        tool_name=meta.tool_name,
        work_summary=payload.get("work_summary") or payload.get("session_focus") or "",
        work_intent_mix=payload.get("work_intent_mix") or payload.get("goal_mix") or {},
        delivery_outcome=outcome,
        user_readback=payload.get("response_reads") or payload.get("user_satisfaction_counts") or {},
        support_value=payload.get("claude_helpfulness", payload.get("helpfulness", "helpful")),
        collaboration_shape=(
            payload.get("collaboration_shape")
            or payload.get("session_shape")
            or payload.get("session_type")
            or "single_task"
        ),
        resistance_signals=_parse_resistance_signals(
            payload.get("resistance_signals") or payload.get("blockers")
        ),
        momentum_signals=_parse_momentum_signals(
            payload.get("momentum_signals") or payload.get("accelerators")
        ),
        resistance_summary=payload.get("resistance_summary") or payload.get("blocker_summary") or "",
        key_gain=payload.get("key_gain") or payload.get("standout_contribution") or "",
        session_takeaway=payload.get("session_takeaway") or payload.get("session_synopsis") or "",
        confidence="high",
        capability_focus=capability_focus,
        capability_depth=capability_depth,
        work_style="freeform",
    )


def _jinja_env() -> Environment:
    return build_prompt_environment()


def _session_read_system_prompt(env: Environment, *, report_language: str = "zh") -> str:
    language = normalize_report_language(report_language)
    cached = _SESSION_READ_SYSTEM_PROMPT_CACHE.get(language)
    if cached is None:
        cached = env.get_template("session_read/system.md.j2").render(
            report_language=language,
        )
        _SESSION_READ_SYSTEM_PROMPT_CACHE[language] = cached
    return cached


def _sanitize(text: str | None, max_chars: int = 300) -> str:
    if not text:
        return ""
    return text.replace("\n", " ").replace("\r", " ").replace("\t", " ")[:max_chars]


def _tool_counts_summary(tool_counts: dict[str, int]) -> str:
    if not tool_counts:
        return "none recorded"
    ranked = sorted(tool_counts.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name}x{count}" for name, count in ranked[:8])


def should_read_session(meta: SessionRecord) -> bool:
    return _should_extract(meta)


def _should_extract(meta: SessionRecord) -> bool:
    indexed_prompt = bool(meta.unique_skills_used or meta.slash_commands or meta.skill_invocation_count > 0)
    enough_turns = meta.user_message_count >= MIN_USER_MESSAGES or (
        indexed_prompt and meta.user_message_count >= 1
    )
    autonomous_single_shot = meta.user_message_count >= 1 and meta.assistant_message_count >= 3
    if not (enough_turns or autonomous_single_shot):
        return False
    if meta.duration_minutes is not None and meta.duration_minutes < MIN_DURATION_MINUTES:
        return False
    if meta.prompt_word_count > 0 and meta.prompt_word_count < MIN_PROMPT_WORDS:
        return False
    return True


def _has_output_signals(meta: SessionRecord) -> bool:
    return (
        meta.files_modified > 0
        or meta.lines_added > 0
        or meta.lines_removed > 0
        or meta.git_commits > 0
        or sum(meta.tool_counts.values()) >= 10
    )


def _output_summary(meta: SessionRecord) -> str:
    summary: list[str] = []
    if meta.files_modified > 0:
        summary.append(f"{meta.files_modified} files modified")
    if meta.lines_added > 0 or meta.lines_removed > 0:
        summary.append(f"+{meta.lines_added}/-{meta.lines_removed} lines")
    if meta.git_commits > 0:
        summary.append(f"{meta.git_commits} commits")
    total_calls = sum(meta.tool_counts.values())
    if total_calls:
        success_rate = round((1 - meta.tool_errors / total_calls) * 100) if total_calls else 100
        summary.append(f"{success_rate}% tool success rate ({total_calls} calls)")
    return ", ".join(summary) if summary else "no measurable output"


def _is_high_quality(meta: SessionRecord) -> bool:
    return bool(meta.tool_counts) or bool(
        meta.lines_added + meta.lines_removed or meta.git_commits or meta.files_modified
    )


def _cached_session_read(
    cache: CacheStore,
    meta: SessionRecord,
    *,
    force: bool,
    language: str,
) -> Optional[SessionRead]:
    if force:
        return None
    return cache.read_analysis(
        meta.tool_name,
        meta.session_id,
        source_mtime=meta._source_mtime or None,
        report_language=language,
        source_machine=meta.source_machine,
    )


def _friction_description(language: str, category: str) -> str:
    from ..i18n.catalog import load_catalog
    catalog = load_catalog("fallback_signals", language)
    blockers = catalog.get("blockers", {})
    key = category.replace("-", "_")
    return blockers.get(key, "")


def _write_session_read(
    cache: CacheStore,
    session_read: SessionRead,
    meta: SessionRecord,
    *,
    language: str,
) -> SessionRead:
    session_read._source_mtime = meta._source_mtime
    session_read._report_language = language
    # Active-clarification is a turn-structure signal derived from the raw
    # session, not from the LLM judgement, so we compute it with the same shared
    # rule used by the heuristic extractor to keep both modes aligned.
    session_read.active_clarification = detect_active_clarification(meta)

    # Exclude continuation messages from off-track misclassification
    all_msgs = []
    if meta.first_prompt:
        all_msgs.append(meta.first_prompt)
    if meta.top_user_messages:
        all_msgs.extend(meta.top_user_messages)

    has_continuation = any(is_recovery_continuation(msg) for msg in all_msgs)
    if has_continuation:
        corrected_signals = []
        has_off_track = False
        for sig in session_read.resistance_signals:
            if sig.category == "off-track":
                has_off_track = True
                corrected_signals.append(
                    ResistanceSignal(
                        category="environmental-recovery",
                        attribution="environmental",
                        description=_friction_description(language, "environmental-recovery"),
                        severity="low",
                        confidence=sig.confidence
                    )
                )
            else:
                corrected_signals.append(sig)

        has_env_rec = any(sig.category == "environmental-recovery" for sig in corrected_signals)
        if not has_env_rec:
            corrected_signals.append(
                ResistanceSignal(
                    category="environmental-recovery",
                    attribution="environmental",
                    description=_friction_description(language, "environmental-recovery"),
                    severity="low",
                    confidence=85
                )
            )
        session_read.resistance_signals = corrected_signals

    cache.write_analysis(session_read, source_machine=meta.source_machine)
    return session_read


def _render_session_read_prompt(meta: SessionRecord, *, language: str) -> tuple[str, str]:
    env = _jinja_env()
    system_prompt = _session_read_system_prompt(env, report_language=language)
    top_messages = ""
    if meta.top_user_messages:
        top_messages = "\n".join(
            f"  {index + 1}. {message}"
            for index, message in enumerate(meta.top_user_messages)
        )
    user_prompt = env.get_template("session_read/user.md.j2").render(
        tool_display_name=meta.tool_name.replace("_", " ").title(),
        project_path=meta.project_path,
        duration_minutes=meta.duration_minutes,
        user_message_count=meta.user_message_count,
        user_messages_shown=len(meta.top_user_messages),
        first_prompt=_sanitize(meta.first_prompt),
        top_user_messages=top_messages,
        tool_has_tool_calls=bool(meta.tool_counts),
        tool_counts_summary=_tool_counts_summary(meta.tool_counts),
        tool_errors=meta.tool_errors,
        has_output_signals=_has_output_signals(meta),
        output_summary=_output_summary(meta),
        ai_authoring_hints=_authoring_hints_for(meta),
        workflow_style_hints=_workflow_hints_for(meta),
        report_language=language,
    )
    return system_prompt, user_prompt


def extract_session_read_for_session(
    meta: SessionRecord,
    llm: LlmGateway,
    cache: CacheStore,
    force: bool = False,
    language: str = "zh",
    limiter: "AdaptiveLimiter | None" = None,
) -> Optional[SessionRead]:
    if not _should_extract(meta):
        return None

    language = normalize_report_language(language)
    cached = _cached_session_read(cache, meta, force=force, language=language)
    if cached is not None:
        return cached

    if meta.tool_name == "claude_code":
        native = _load_native_claude_session_read(meta)
        if native is not None:
            _attach_prompt_quality(native, meta, llm, language=language)
            return _write_session_read(cache, native, meta, language=language)

    system_prompt, prompt = _render_session_read_prompt(meta, language=language)
    try:
        raw = complete_json_with_retries(
            llm=llm,
            request=LlmCallRequest(
                prompt=prompt,
                cacheable_system=system_prompt,
                max_tokens=4096,
            ),
            retry_delays=_RETRY_DELAYS,
            limiter=limiter,
            logger=logger,
            log_context=f"session-read:{meta.tool_name}/{meta.session_id}",
        )
    except Exception as exc:
        logger.warning("Session read failed for %s/%s: %s", meta.tool_name, meta.session_id, exc)
        return SessionRead(
            session_id=meta.session_id,
            tool_name=meta.tool_name,
            confidence="low",
            extraction_failed=True,
        )

    confidence = "low" if meta.tool_name in _LOW_DATA_TOOLS else "high"
    session_read = parse_session_read_payload(
        raw=raw,
        session_id=meta.session_id,
        tool_name=meta.tool_name,
        confidence=confidence,
    )
    _attach_prompt_quality(session_read, meta, llm, language=language)
    return _write_session_read(cache, session_read, meta, language=language)


def _attach_prompt_quality(
    session_read: SessionRead,
    meta: SessionRecord,
    llm: LlmGateway,
    *,
    language: str = "zh",
) -> None:
    from ..extractors.heuristic import build_prompt_quality_proxy
    from ..extractors.prompt_quality import extract_prompt_lens, should_extract_prompt_lens

    attempted = should_extract_prompt_lens(meta)
    prompt_lens = (
        extract_prompt_lens(
            meta,
            llm,
            outcome=session_read.delivery_outcome,
            had_course_correction=False,
            language=language,
        )
        if attempted
        else None
    )
    if prompt_lens is None:
        status = "llm_failed" if attempted else "insufficient_input"
        prompt_lens = build_prompt_quality_proxy(
            meta,
            language=language,
            evaluation_status=status,
        )
    session_read.prompt_lens = prompt_lens


def _time_stratify(sessions: list[SessionRecord], n: int) -> list[SessionRecord]:
    if len(sessions) <= n:
        return list(sessions)
    ordered = sorted(sessions, key=lambda session: session.start_time or "")
    bucket = len(ordered) / n
    selected = {int((index + 0.5) * bucket) for index in range(n)}
    return [ordered[index] for index in sorted(selected)]


def _stratified_sample(eligible: list[SessionRecord], max_sessions: int) -> list[SessionRecord]:
    if max_sessions == 0 or len(eligible) <= max_sessions:
        return list(eligible)

    grouped: dict[tuple[str, str], list[SessionRecord]] = {}
    for session in eligible:
        grouped.setdefault((session.tool_name, session.source_machine), []).append(session)

    total = len(eligible)
    sampled: list[SessionRecord] = []
    for bucket in grouped.values():
        quota = max(1, round(len(bucket) / total * max_sessions))
        strong = [session for session in bucket if _is_high_quality(session)]
        normal = [session for session in bucket if not _is_high_quality(session)]
        if len(strong) >= quota:
            sampled.extend(_time_stratify(strong, quota))
            continue
        sampled.extend(strong)
        if quota > len(strong):
            sampled.extend(_time_stratify(normal, quota - len(strong)))

    if len(sampled) > max_sessions:
        sampled = _time_stratify(sampled, max_sessions)
    return sampled


def default_session_read_worker_count(eligible_count: int) -> int:
    return _default_max_workers(eligible_count)


def _default_max_workers(eligible_count: int) -> int:
    return min(16, max(4, eligible_count // 40))


def _emit_progress(callback: Optional[Callable[[int, int, int, int], None]], progress: _BatchProgress) -> None:
    if callback is None:
        return
    callback(progress.done, progress.total, progress.fresh_done, progress.fresh_total)


def _eligible_sessions(
    sessions: list[SessionRecord],
    *,
    min_quality: str = "medium",
) -> tuple[list[SessionRecord], list[tuple[SessionRecord, str]]]:
    eligible: list[SessionRecord] = []
    filtered: list[tuple[SessionRecord, str]] = []
    for session in sessions:
        if _should_extract(session) and _passes_quality_gate(session, min_quality):
            eligible.append(session)
            continue
        if not _passes_quality_gate(session, min_quality):
            reason = f"quality-gated ({session.quality_tag} < {min_quality})"
        elif session.user_message_count < MIN_USER_MESSAGES and session.assistant_message_count < 3:
            reason = f"low-engagement (user_msgs={session.user_message_count}, asst_msgs={session.assistant_message_count})"
        elif session.duration_minutes is not None and session.duration_minutes < MIN_DURATION_MINUTES:
            reason = f"too-short ({session.duration_minutes}min < {MIN_DURATION_MINUTES}min)"
        else:
            reason = f"short-prompt ({session.prompt_word_count} words < {MIN_PROMPT_WORDS})"
        filtered.append((session, reason))
    return eligible, filtered


def extract_session_reads_batch(
    sessions: list[SessionRecord],
    llm: LlmGateway,
    cache: CacheStore,
    max_workers: Optional[int] = None,
    max_sessions: int = 50,
    force: bool = False,
    on_progress: Optional[Callable[[int, int, int, int], None]] = None,
    language: str = "zh",
    min_quality: str = "medium",
) -> tuple[list[SessionRead], int]:
    language = normalize_report_language(language)
    eligible, filtered = _eligible_sessions(sessions, min_quality=min_quality)
    if logger.isEnabledFor(logging.INFO):
        logger.debug(
            "Session-read filter: %d total -> %d eligible, %d filtered",
            len(sessions),
            len(eligible),
            len(filtered),
        )
        for session, reason in filtered:
            logger.info(
                "  FILTERED  [%s] %s/%s -> %s",
                session.source_machine,
                session.tool_name,
                session.session_id[:16],
                reason,
            )

    sampled = _stratified_sample(eligible, max_sessions)
    if logger.isEnabledFor(logging.INFO):
        sampled_ids = {session.session_id for session in sampled}
        for session in eligible:
            if session.session_id not in sampled_ids:
                logger.info(
                    "  NOT_SAMPLED [%s] %s/%s -> quota limit",
                    session.source_machine,
                    session.tool_name,
                    session.session_id[:16],
                )
        for session in sampled:
            logger.info(
                "  SAMPLED   [%s] %s/%s",
                session.source_machine,
                session.tool_name,
                session.session_id[:16],
            )

    cached_reads: list[SessionRead] = []
    pending: list[SessionRecord] = []
    for session in sampled:
        cached = _cached_session_read(cache, session, force=force, language=language)
        if cached is not None:
            cached_reads.append(cached)
        else:
            pending.append(session)

    workers = max_workers if max_workers is not None else _default_max_workers(len(sampled))
    fresh_total = len(pending)
    progress = _BatchProgress(
        done=len(cached_reads),
        total=len(sampled),
        fresh_done=0,
        fresh_total=fresh_total,
    )
    _emit_progress(on_progress, progress)

    if logger.isEnabledFor(logging.INFO):
        logger.info(
            "Session-read extraction: %d eligible sessions (%d cache hits, %d fresh) across %d workers",
            len(sampled),
            len(cached_reads),
            len(pending),
            workers,
        )

    limiter = AdaptiveLimiter(initial=workers)
    results: list[SessionRead] = list(cached_reads)
    progress_state = {"done": progress.done, "fresh_done": 0}
    stop_signal = threading.Event()
    heartbeat: threading.Thread | None = None
    if on_progress is not None and fresh_total > 0:
        def _heartbeat() -> None:
            while not stop_signal.wait(2.0):
                _emit_progress(
                    on_progress,
                    _BatchProgress(
                        done=progress_state["done"],
                        total=len(sampled),
                        fresh_done=progress_state["fresh_done"],
                        fresh_total=fresh_total,
                    ),
                )

        heartbeat = threading.Thread(target=_heartbeat, daemon=True)
        heartbeat.start()

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(
                    copy_context().run,
                    extract_session_read_for_session,
                    session,
                    llm,
                    cache,
                    force,
                    language,
                    limiter,
                ): session
                for session in pending
            }
            for future in as_completed(future_map):
                session = future_map[future]
                try:
                    result = future.result(timeout=FACET_SESSION_TIMEOUT_SEC)
                    if result is not None:
                        results.append(result)
                except FuturesTimeoutError:
                    logger.warning(
                        "Session-read timed out for %s/%s after %.0fs",
                        session.tool_name,
                        session.session_id,
                        FACET_SESSION_TIMEOUT_SEC,
                    )
                except Exception as exc:
                    logger.warning(
                        "Session-read failed %s/%s: %s",
                        session.tool_name,
                        session.session_id,
                        exc,
                    )
                progress_state["done"] += 1
                progress_state["fresh_done"] += 1
                _emit_progress(
                    on_progress,
                    _BatchProgress(
                        done=progress_state["done"],
                        total=len(sampled),
                        fresh_done=progress_state["fresh_done"],
                        fresh_total=fresh_total,
                    ),
                )
    finally:
        if heartbeat is not None:
            stop_signal.set()
            heartbeat.join(timeout=0.5)

    return results, len(sampled)
