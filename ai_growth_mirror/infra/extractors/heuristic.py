"""Offline heuristic session-read construction for local-only report generation.

This module exists for environments where the product can read raw session
logs locally but cannot call the semantic LLM extractor. The output is not as
rich as full extraction, but it is stable enough to drive the personal growth
report and version comparisons.
"""
from __future__ import annotations

from pathlib import Path as _Path

from ..i18n.catalog import load_catalog
from ...domain.session.model import SessionRecord
from ...domain.signals.model import (
    MomentumSignal,
    PromptLensFinding,
    PromptLensScores,
    PromptLensTakeaway,
    ResistanceSignal,
    SessionRead,
)
from ..extractors.llm import _should_extract
from ...domain.session.heuristics import (
    classify_session_quality,
    passes_quality_gate as _passes_quality_gate,
)
from ...domain.signals.framework import aggregate_family, detect_frameworks

_FRICTION_DESC_KEYS = {
    "tool-ceiling": "tool_ceiling",
    "fuzzy-intent": "fuzzy_intent",
    "off-track": "off_track",
}


def _heuristic_i18n(language: str = "zh") -> dict:
    return load_catalog("fallback_signals", language)


def _i18n_text(language: str, section: str, key: str, default: str = "") -> str:
    node = _heuristic_i18n(language).get(section, {})
    if not isinstance(node, dict):
        return default
    value = node.get(key, default)
    return value if isinstance(value, str) else default


def _i18n_format(language: str, key: str, default: str = "", **kwargs: str) -> str:
    template = _heuristic_i18n(language).get(key, default)
    if not isinstance(template, str) or not template:
        return default
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def _i18n_section_format(
    language: str,
    section: str,
    key: str,
    default: str = "",
    **kwargs: str,
) -> str:
    template = _i18n_text(language, section, key, default=default)
    if not template:
        return default
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def build_heuristic_session_reads_batch(
    sessions: list[SessionRecord],
    *,
    language: str = "zh",
    max_sessions: int = 0,
    min_quality: str = "medium",
) -> tuple[list[SessionRead], int]:
    """Build session reads locally from deterministic heuristics.

    Returns ``(session_reads, attempted_count)`` to mirror the LLM extractor's shape.
    ``attempted_count`` here equals the number of eligible sessions after the
    same substantive-session gate used by the LLM extractor.
    """
    eligible = [s for s in sessions if _should_extract(s) and _passes_quality_gate(s, min_quality)]
    if max_sessions and max_sessions > 0:
        eligible = eligible[:max_sessions]
    return [
        build_heuristic_session_read_for_session(session, language=language)
        for session in eligible
    ], len(eligible)


def build_heuristic_session_read_for_session(
    session: SessionRecord,
    *,
    language: str = "zh",
) -> SessionRead:
    goal_text = _goal_text(session, language)
    # Registry-based framework detection takes precedence over local heuristics.
    _fw_matches = detect_frameworks(session)
    _fw_family = aggregate_family(_fw_matches)
    workflow_style = _fw_family if _fw_family else _workflow_style(session)
    outcome = _outcome(session)
    helpfulness = _helpfulness(session, outcome)
    primary_success = _primary_success(session, workflow_style)
    blockers = _blockers(session, language)
    accelerators = _accelerators(session, workflow_style, language)
    prompt_quality = build_prompt_quality_proxy(
        session,
        language=language,
        evaluation_status="llm_unavailable",
    )
    creation_mode, creation_depth = _creation_mode(session)
    project_name = _Path(session.project_path).name if session.project_path else ""

    return SessionRead(
        session_id=session.session_id,
        tool_name=session.tool_name,
        work_summary=goal_text,
        work_intent_mix=_goal_categories(session),
        delivery_outcome=outcome,
        support_value=helpfulness,
        collaboration_shape="single_task",
        resistance_signals=blockers,
        momentum_signals=accelerators,
        resistance_summary=_blocker_summary(blockers, language),
        key_gain=primary_success,
        session_takeaway=_session_synopsis(
            session,
            project_name=project_name,
            workflow_style=workflow_style,
            outcome=outcome,
            language=language,
        ),
        confidence="medium",
        prompt_lens=prompt_quality,
        capability_focus=creation_mode,
        capability_depth=creation_depth,
        work_style=workflow_style,
        extraction_failed=False,
    )


def _goal_text(session: SessionRecord, language: str) -> str:
    first = (session.first_prompt or "").strip()
    if first:
        return first[:240]
    for msg in session.top_user_messages:
        msg = (msg or "").strip()
        if msg:
            return msg[:240]
    return _heuristic_i18n(language).get("goal_fallback", "Local session analysis")


def _goal_categories(session: SessionRecord) -> dict[str, int]:
    text = " ".join(
        [
            (session.first_prompt or "").lower(),
            " ".join(m.lower() for m in session.top_user_messages[:3]),
        ]
    )
    categories: dict[str, int] = {}
    # Keys align with the session_read work-intent taxonomy so report i18n stays one vocabulary.
    keyword_groups = {
        "implement_feature": ("implement", "实现", "开发", "编码", "build"),
        "debug_investigate": ("debug", "排查", "调查", "根因", "trace"),
        "fix_bug": ("修复", "报错", "bug", "异常", "fix "),
        "propose_change": ("design", "架构", "方案", "规划", "spec", "prd"),
        "refactor_code": ("refactor", "重构", "cleanup", "整理"),
        "write_docs": ("doc", "文档", "总结", "报告", "review"),
        "write_tests": ("test", "测试", "pytest", "unittest"),
        "quick_question": ("是什么", "为什么", "怎么", "请问", "explain"),
    }
    for key, words in keyword_groups.items():
        if any(word in text for word in words):
            categories[key] = 1
    if not categories:
        if session.files_modified > 0:
            categories["implement_feature"] = 1
        else:
            categories["research_exploration"] = 1
    return categories


def _workflow_style(session: SessionRecord) -> str:
    text = " ".join(
        [
            (session.first_prompt or "").lower(),
            " ".join(m.lower() for m in session.top_user_messages[:4]),
            " ".join(cmd.lower() for cmd in session.slash_commands),
        ]
    )
    plan = any(token in text for token in ("plan", "规划", "计划", "/plan"))
    spec = any(token in text for token in ("spec", "prd", "设计", "架构", "/spec"))
    tdd = session.has_test_commands and any(
        token in text
        for token in ("test first", "tests first", "先写测试", "测试先行", "tdd")
    )
    vibe = (
        session.user_message_count <= 3
        and not plan
        and not spec
        and not tdd
        and session.prompt_word_count <= 80
    )
    signal_count = sum(1 for flag in (plan, spec, tdd, vibe) if flag)
    if signal_count >= 2:
        return "adaptive"
    if spec:
        return "spec_driven"
    if plan:
        return "plan_driven"
    if tdd:
        return "tdd"
    if vibe:
        return "exploratory"
    return "freeform"


def _outcome(session: SessionRecord) -> str:
    changed = bool(
        session.files_modified > 0
        or session.lines_added > 0
        or session.lines_removed > 0
        or session.git_commits > 0
    )
    verified = bool(session.has_verification_behavior or session.has_test_commands)
    if changed and verified and session.tool_errors == 0:
        return "fully_achieved"
    if changed:
        return "mostly_achieved"
    if sum(session.tool_counts.values()) >= 4 or session.assistant_message_count >= 4:
        return "partially_achieved"
    return "ongoing"


def _helpfulness(session: SessionRecord, outcome: str) -> str:
    if outcome == "fully_achieved":
        return "very_helpful"
    if outcome == "mostly_achieved":
        return "helpful"
    if session.tool_errors > 0 and session.files_modified == 0:
        return "mixed"
    return "helpful"


def _primary_success(session: SessionRecord, workflow_style: str) -> str:
    if session.files_modified > 0 and (session.has_verification_behavior or session.has_test_commands):
        return "verified_delivery"
    if session.files_modified > 0:
        return "implemented_changes"
    if workflow_style in {"plan_driven", "spec_driven", "adaptive"}:
        return "structured_analysis"
    if session.tool_counts:
        return "useful_diagnosis"
    return "clarified_direction"


def _friction_description(language: str, category: str) -> str:
    key = _FRICTION_DESC_KEYS.get(category, category.replace("-", "_"))
    return _i18n_text(language, "friction_descriptions", key)


def _blockers(session: SessionRecord, language: str) -> list[ResistanceSignal]:
    points: list[ResistanceSignal] = []
    if session.tool_errors > 0:
        points.append(
            ResistanceSignal(
                category="tool-ceiling",
                attribution="environmental",
                description=_friction_description(language, "tool-ceiling"),
                severity="medium",
                confidence=82,
            )
        )
    if not session.prompt_has_code_context:
        points.append(
            ResistanceSignal(
                category="fuzzy-intent",
                attribution="user-actionable",
                description=_friction_description(language, "fuzzy-intent"),
                severity="medium",
                confidence=76,
            )
        )
    if session.user_interruptions >= 2:
        points.append(
            ResistanceSignal(
                category="off-track",
                attribution="user-actionable",
                description=_friction_description(language, "off-track"),
                severity="medium",
                confidence=74,
            )
        )
    return points[:3]


def _accelerators(
    session: SessionRecord,
    workflow_style: str,
    language: str,
) -> list[MomentumSignal]:
    patterns: list[MomentumSignal] = []
    if workflow_style in {"plan_driven", "spec_driven", "adaptive"}:
        patterns.append(
            MomentumSignal(
                category="planned-approach",
                driver="user-driven",
                label=_i18n_text(language, "pattern_labels", "planned_approach"),
                description=_i18n_text(language, "pattern_descriptions", "planned_approach"),
                confidence=80,
            )
        )
    if session.has_verification_behavior or session.has_test_commands:
        patterns.append(
            MomentumSignal(
                category="verify-loop",
                driver="user-driven",
                label=_i18n_text(language, "pattern_labels", "verify_loop"),
                description=_i18n_text(language, "pattern_descriptions", "verify_loop"),
                confidence=84,
            )
        )
    if session.files_modified > 0:
        patterns.append(
            MomentumSignal(
                category="step-by-step",
                driver="collaborative",
                label=_i18n_text(language, "pattern_labels", "step_by_step"),
                description=_i18n_text(language, "pattern_descriptions", "step_by_step"),
                confidence=78,
            )
        )
    if session.uses_mcp or session.uses_web_search or session.uses_web_fetch or len(session.tool_counts) >= 4:
        patterns.append(
            MomentumSignal(
                category="smart-tooling",
                driver="collaborative",
                label=_i18n_text(language, "pattern_labels", "smart_tooling"),
                description=_i18n_text(language, "pattern_descriptions", "smart_tooling"),
                confidence=74,
            )
        )
    return patterns[:4]


def _prompt_quality(
    session: SessionRecord,
    language: str,
    *,
    evaluation_status: str = "insufficient_input",
) -> PromptLensScores | None:
    pq = _heuristic_i18n(language).get("pq_texts", {})

    context = 38
    specificity = 42
    scope = 45
    timing = 48
    correction = 50
    findings: list[PromptLensFinding] = []
    takeaways: list[PromptLensTakeaway] = []

    if session.prompt_has_code_context:
        context += 34
        findings.append(
            PromptLensFinding(
                category="effective-context",
                type="strength",
                description=pq.get("effective_context_desc", ""),
                message_ref="User#1",
                impact="high",
                confidence=82,
            )
        )
        takeaways.append(
            PromptLensTakeaway(
                type="reinforce",
                category="effective-context",
                label=pq.get("reinforce_context_label", ""),
                message_ref="User#1",
                what_worked=pq.get("context_what_worked", ""),
                why_effective=pq.get("context_why_effective", ""),
            )
        )
    else:
        findings.append(
            PromptLensFinding(
                category="missing-context",
                type="deficit",
                description=pq.get("missing_context_desc", ""),
                message_ref="User#1",
                impact="high",
                confidence=78,
                suggested_improvement=pq.get("missing_context_improvement", ""),
            )
        )
        takeaways.append(
            PromptLensTakeaway(
                type="improve",
                category="missing-context",
                label=pq.get("improve_context_label", ""),
                message_ref="User#1",
                original=(session.first_prompt or "")[:140],
                better_prompt=pq.get("context_better_prompt", ""),
                why=pq.get("context_why_improve", ""),
            )
        )

    if session.prompt_has_constraint:
        specificity += 26
        scope += 18
        findings.append(
            PromptLensFinding(
                category="precise-request",
                type="strength",
                description=pq.get("precise_request_desc", ""),
                message_ref="User#1",
                impact="high",
                confidence=80,
            )
        )
    else:
        findings.append(
            PromptLensFinding(
                category="missing-acceptance-criteria",
                type="deficit",
                description=pq.get("missing_acceptance_desc", ""),
                message_ref="User#1",
                impact="medium",
                confidence=76,
                suggested_improvement=pq.get("missing_acceptance_improvement", ""),
            )
        )

    indexed_prompt = bool(session.unique_skills_used or session.slash_commands or session.skill_invocation_count > 0)
    if session.prompt_word_count < 18 and not indexed_prompt:
        specificity -= 12
        findings.append(
            PromptLensFinding(
                category="vague-request",
                type="deficit",
                description=pq.get("vague_request_desc", ""),
                message_ref="User#1",
                impact="medium",
                confidence=72,
                suggested_improvement=pq.get("vague_request_improvement", ""),
            )
        )

    if session.user_interruptions >= 2:
        timing -= 10
        correction -= 8
        findings.append(
            PromptLensFinding(
                category="unclear-correction",
                type="deficit",
                description=pq.get("unclear_correction_desc", ""),
                message_ref="User#N",
                impact="medium",
                confidence=71,
                suggested_improvement=pq.get("unclear_correction_improvement", ""),
            )
        )

    context = min(max(context, 0), 100)
    specificity = min(max(specificity, 0), 100)
    scope = min(max(scope, 0), 100)
    timing = min(max(timing, 0), 100)
    correction = min(max(correction, 0), 100)
    efficiency = round((context + specificity + scope + timing + correction) / 5)

    return PromptLensScores(
        source="heuristic",
        coverage="full" if session.user_message_count >= 5 else "light",
        evaluation_status=evaluation_status,
        evaluated_user_messages=session.user_message_count,
        context_provision=context,
        request_specificity=specificity,
        scope_management=scope,
        information_timing=timing,
        correction_quality=correction,
        efficiency_score=efficiency,
        findings=findings[:6],
        takeaways=takeaways[:3],
    )


def build_prompt_quality_proxy(
    session: SessionRecord,
    *,
    language: str,
    evaluation_status: str = "insufficient_input",
) -> PromptLensScores:
    """Build a lightweight prompt-quality proxy from stable local signals."""
    result = _prompt_quality(session, language, evaluation_status=evaluation_status)
    if result is not None:
        return result
    return PromptLensScores(
        source="heuristic",
        coverage="light",
        evaluation_status=evaluation_status,
        evaluated_user_messages=session.user_message_count,
    )


def _creation_mode(session: SessionRecord) -> tuple[str, str]:
    if session.mcp_server_authored:
        return "tooling_author", "substantial" if session.files_modified >= 3 else "moderate"
    if session.skill_files_authored > 0 or session.hook_config_modified:
        return "workflow_builder", "substantial" if session.skill_files_authored >= 2 else "moderate"
    # Having a rich personal skill set (used skills from own library) is a signal
    # of asset-oriented collaboration even when no files were edited this session.
    if session.unique_skills_used:
        n = len(session.unique_skills_used)
        strength = "substantial" if n >= 5 else "moderate" if n >= 2 else "incidental"
        return "workflow_builder", strength
    return "none", "incidental"


def _session_synopsis(
    session: SessionRecord,
    *,
    project_name: str,
    workflow_style: str,
    outcome: str,
    language: str,
) -> str:
    bs = _heuristic_i18n(language).get("brief_summary", {})
    labels = bs.get("workflow_labels", {}) if isinstance(bs.get("workflow_labels"), dict) else {}
    workflow_label = labels.get(workflow_style, labels.get("default", workflow_style))

    if project_name:
        project_segment = _i18n_section_format(
            language,
            "brief_summary",
            "project_with_name",
            project_name=project_name,
        )
    else:
        project_segment = _i18n_text(language, "brief_summary", "project_local")

    outcome_keys = {
        "fully_achieved": "outcome_fully",
        "mostly_achieved": "outcome_mostly",
        "partially_achieved": "outcome_partial",
        "ongoing": "outcome_ongoing",
    }
    outcome_segment = _i18n_text(
        language,
        "brief_summary",
        outcome_keys.get(outcome, "outcome_ongoing"),
    )

    return _i18n_section_format(
        language,
        "brief_summary",
        "template",
        project_segment=project_segment,
        workflow_label=workflow_label,
        outcome_segment=outcome_segment,
    )


def _blocker_summary(points: list[ResistanceSignal], language: str) -> str:
    if not points:
        return ""
    labels = ", ".join(point.category for point in points[:3])
    return _i18n_format(language, "friction_detail_template", labels=labels)


