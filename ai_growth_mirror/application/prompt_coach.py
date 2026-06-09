"""Application-owned prompt coach assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.growth.coaching import CoachingContent
from ..domain.growth.model import GrowthProfile
from ..domain.growth.prompting import (
    assess_closure_guidance,
    assess_prompt_style,
    build_friction_synthesis_intents,
)
from ..domain.session.model import SessionRecord
from ..domain.signals.model import PromptLensTakeaway, SessionRead
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from .prompt_coach_views import (
        PromptCoachClosureGuidanceView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachFrictionSynthesisView,
        PromptCoachPromptStyleView,
        PromptCoachRewriteCardView,
        PromptCoachSourceSummaryView,
        PromptCoachView,
    )

TOP_DEFICIT_ORDER = (
    "missing-context",
    "vague-request",
    "late-constraint",
    "unclear-correction",
    "scope-drift",
    "missing-acceptance-criteria",
    "assumption-not-surfaced",
)

DEFICIT_DIMENSION_MAP = {
    "missing-context": "context_provision",
    "vague-request": "request_specificity",
    "late-constraint": "information_timing",
    "unclear-correction": "correction_quality",
    "scope-drift": "scope_management",
    "missing-acceptance-criteria": "request_specificity",
    "assumption-not-surfaced": "context_provision",
}

DIMENSION_SCENE_MAP = {
    "context_provision": "requirements_design",
    "request_specificity": "code_review",
    "scope_management": "architecture_refactor",
    "information_timing": "bug_triage",
    "correction_quality": "bug_triage",
}


def build_prompt_coach_view(
    *,
    stats: GrowthProfile,
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
    coaching: CoachingContent | None = None,
) -> "PromptCoachView":
    from .prompt_coach_views import (
        PromptCoachClosureGuidanceView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachFrictionSynthesisView,
        PromptCoachPromptStyleView,
        PromptCoachRewriteCardView,
        PromptCoachSourceSummaryView,
        PromptCoachView,
    )

    pc_i18n = catalogs.view_model.get("prompt_coach", {})
    trainer_i18n = pc_i18n.get("trainer", {})
    dim_labels = catalogs.view_model.get("pq_dim_labels", {})
    evaluated_messages = sum(
        read.prompt_lens.evaluated_user_messages
        for read in session_reads
        if read.prompt_lens is not None
    )
    source_summary = PromptCoachSourceSummaryView(
        llm_session_count=stats.pq_llm_session_count,
        heuristic_session_count=stats.pq_heuristic_session_count,
        light_session_count=stats.pq_light_session_count,
        evaluated_user_messages=evaluated_messages,
        run_mode="llm" if session_read_mode == "llm" else "heuristic_only",
        llm_evaluated_count=stats.pq_llm_evaluated_count,
        insufficient_count=stats.pq_insufficient_count,
        llm_failed_count=stats.pq_llm_failed_count,
        llm_unavailable_count=stats.pq_llm_unavailable_count,
    )
    dimension_scores = [
        PromptCoachDimensionView(label=dim_labels.get(key, key), score=round(float(score), 1))
        for key, score in sorted((stats.pq_avg_dimensions or {}).items(), key=lambda item: item[1])
    ]
    prompt_style_signal, trigger_maturity = assess_prompt_style(sessions, session_reads)
    top_deficit_keys = _rank_top_deficits(stats, prompt_style=prompt_style_signal.prompt_style)
    closure_signal = assess_closure_guidance(sessions, session_reads)
    top_deficits = [
        PromptCoachDeficitView(
            id=f"deficit:{key.replace('-', '_')}",
            category=key,
            label=_deficit_label(key, catalogs, prompt_style=prompt_style_signal.prompt_style),
            description=_deficit_copy(key, prompt_style_signal, catalogs).get("description", ""),
            impact=_deficit_copy(key, prompt_style_signal, catalogs).get("impact", ""),
            confidence=_deficit_confidence(stats, key),
            evidence_refs=_evidence_refs_for_deficit(key, session_reads, stats),
            source=_deficit_source(stats, key),
        )
        for key in top_deficit_keys
    ]
    rewrite_cards = _build_rewrite_cards(
        stats,
        coaching,
        prompt_style_signal,
        catalogs,
    )
    prompt_style = PromptCoachPromptStyleView(
        type=prompt_style_signal.prompt_style,
        label=trainer_i18n.get("prompt_style_labels", {}).get(prompt_style_signal.prompt_style, prompt_style_signal.prompt_style),
        evidence=_prompt_style_evidence(prompt_style_signal, stats, catalogs),
        coaching_message=_prompt_style_message(
            prompt_style_signal,
            top_deficits,
            catalogs,
        ),
        suggested_next_prompt=_suggested_next_prompt(rewrite_cards),
        trigger_maturity=_trigger_maturity_lines(trigger_maturity, catalogs),
    )
    closure_guidance = PromptCoachClosureGuidanceView(
        id=f"closure:{closure_signal.task_type}",
        task_type=closure_signal.task_type,
        mode=closure_signal.mode,
        label=trainer_i18n.get("task_type_labels", {}).get(closure_signal.task_type, closure_signal.task_type),
        expected_closure_methods=[
            trainer_i18n.get("closure_methods", {}).get(item, item)
            for item in closure_signal.expected_closure_methods
        ],
        missing_closure_methods=[
            trainer_i18n.get("closure_methods", {}).get(item, item)
            for item in closure_signal.missing_closure_methods
        ],
        coaching_message=_closure_message(closure_signal, catalogs),
    )
    source_note = _source_note(stats, session_read_mode, catalogs)
    weak_dimensions = [item.label for item in dimension_scores[:2]]
    deficits = [
        f"{item.label} · {item.confidence}"
        for item in top_deficits
    ]
    weakest_label = weak_dimensions[0] if weak_dimensions else (_deficit_label(top_deficit_keys[0], catalogs) if top_deficit_keys else "")
    strongest_label = dimension_scores[-1].label if dimension_scores else ""
    if stats.pq_avg_dimensions:
        weakest_dimension_key = min(stats.pq_avg_dimensions, key=stats.pq_avg_dimensions.get)
        weakest_label = dim_labels.get(weakest_dimension_key, weakest_dimension_key)
    headline = _headline(top_deficits, weak_dimensions, catalogs)
    evidence_summary = _evidence_summary(top_deficits, stats, catalogs)
    light_state_note = ""
    if stats.pq_sessions_evaluated <= 0:
        light_state_note = trainer_i18n.get("light_state_note", "")
    elif stats.pq_llm_session_count <= 0:
        light_state_note = trainer_i18n.get("heuristic_state_note", "")

    friction_intents = build_friction_synthesis_intents(
        sessions,
        session_reads,
        prompt_style_signal,
        closure_signal,
        top_deficit_keys,
        stats,
    )
    friction_synthesis = _build_friction_synthesis_views(
        coaching=coaching,
        intents=friction_intents,
        pc_i18n=pc_i18n,
    )

    return PromptCoachView(
        available=True,
        headline=headline,
        strongest_label=strongest_label,
        weakest_label=weakest_label,
        evidence_summary=evidence_summary,
        strength_habit=trainer_i18n.get("strength_habit", "").format(label=strongest_label),
        source_note=source_note,
        weak_dimensions=weak_dimensions,
        deficits=deficits,
        dimension_scores=dimension_scores,
        source_summary=source_summary,
        top_deficits=top_deficits,
        rewrite_cards=rewrite_cards,
        prompt_style=prompt_style,
        closure_guidance=closure_guidance,
        friction_synthesis=friction_synthesis,
        light_state_note=light_state_note,
    )


def _build_friction_synthesis_views(
    *,
    coaching: CoachingContent | None,
    intents: list,
    pc_i18n: dict,
) -> list["PromptCoachFrictionSynthesisView"]:
    from .prompt_coach_views import PromptCoachFrictionSynthesisView

    friction_i18n = pc_i18n.get("friction_synthesis", {})
    if coaching and coaching.friction_synthesis:
        llm_rows: list[PromptCoachFrictionSynthesisView] = []
        for item in coaching.friction_synthesis:
            refs = [ref for ref in item.evidence_refs if ref]
            if not refs:
                continue
            llm_rows.append(
                PromptCoachFrictionSynthesisView(
                    id=item.id or f"friction:llm:{len(llm_rows)}",
                    label=item.label,
                    explanation=item.explanation,
                    next_action=item.next_action,
                    confidence=item.confidence or 70,
                    evidence_refs=refs,
                    generated_by="llm",
                )
            )
        if llm_rows:
            return llm_rows[:2]

    rule_rows: list[PromptCoachFrictionSynthesisView] = []
    for intent in intents:
        copy = friction_i18n.get(intent.pattern_key, {})
        if not copy:
            continue
        evidence_text = " / ".join(intent.evidence_refs[:3])
        rule_rows.append(
            PromptCoachFrictionSynthesisView(
                id=intent.id,
                label=copy.get("label", ""),
                explanation=(copy.get("explanation", "") or "").format(
                    evidence=evidence_text,
                    count=len(intent.evidence_refs),
                ),
                next_action=(copy.get("next_action", "") or "").format(
                    evidence=evidence_text,
                    count=len(intent.evidence_refs),
                ),
                confidence=intent.confidence,
                evidence_refs=list(intent.evidence_refs),
                generated_by="rule",
            )
        )
    return rule_rows[:2]


def _rank_top_deficits(
    stats: GrowthProfile,
    prompt_style: str = "",
) -> list[str]:
    counts = stats.pq_deficit_counts or {}
    ranked = [
        key
        for key in TOP_DEFICIT_ORDER
        if counts.get(key, 0) > 0
    ]
    # indexed_prompt users already have a rule anchor; missing-context / vague-request
    # are expected characteristics of their terse invocations, not true deficits.
    # Demote them so they don't dominate the top list.
    INDEXED_DEMOTED = frozenset({"missing-context", "vague-request"})
    is_indexed = prompt_style in {"indexed_prompt", "mixed_prompt"}

    def sort_key(key: str) -> tuple[int, int, int]:
        demoted = 1 if (is_indexed and key in INDEXED_DEMOTED) else 0
        return (demoted, -counts.get(key, 0), TOP_DEFICIT_ORDER.index(key))

    ranked.sort(key=sort_key)
    return ranked[:3]


def _deficit_label(
    key: str,
    catalogs: ReportLabelCatalogs,
    prompt_style: str = "",
) -> str:
    # When indexed_prompt/mixed_prompt, use reframed labels if available.
    if prompt_style in {"indexed_prompt", "mixed_prompt"}:
        override_labels = (
            catalogs.view_model.get("prompt_coach", {})
            .get("trainer", {})
            .get("indexed_deficit_labels", {})
        )
        overridden = override_labels.get(key, "")
        if overridden:
            return overridden
    labels = catalogs.guidance_labels.get("pq_labels", {}).get("deficit", {})
    return labels.get(key.replace("-", "_"), key)


def _deficit_confidence(stats: GrowthProfile, deficit_key: str) -> str:
    count = int((stats.pq_deficit_counts or {}).get(deficit_key, 0) or 0)
    if stats.pq_llm_session_count >= 3 and count >= 3:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def _deficit_source(stats: GrowthProfile, deficit_key: str) -> str:
    if stats.pq_llm_session_count:
        return "llm"
    if (stats.pq_deficit_counts or {}).get(deficit_key, 0):
        return "heuristic"
    return "light"


def _evidence_refs_for_deficit(
    deficit_key: str,
    session_reads: list[SessionRead],
    stats: GrowthProfile,
) -> list[str]:
    refs: list[str] = []
    expected_dimension = DEFICIT_DIMENSION_MAP.get(deficit_key, "")
    for session_read in session_reads:
        prompt_lens = session_read.prompt_lens
        if prompt_lens is None:
            continue
        for finding in prompt_lens.findings:
            if finding.type != "deficit":
                continue
            if finding.category != expected_dimension:
                continue
            message_ref = finding.message_ref or session_read.session_id
            summary = f"{message_ref}: {finding.description}"
            if summary not in refs:
                refs.append(_trim_text(summary, 140))
            if len(refs) >= 3:
                return refs
        for takeaway in prompt_lens.takeaways:
            if takeaway.type != "improve":
                continue
            if takeaway.category != expected_dimension:
                continue
            source = takeaway.original or takeaway.message_ref or session_read.session_takeaway
            if source and source not in refs:
                refs.append(_trim_text(source, 140))
            if len(refs) >= 3:
                return refs
    if not refs and (stats.pq_deficit_counts or {}).get(deficit_key, 0):
        refs.append(f"{deficit_key}: {stats.pq_deficit_counts.get(deficit_key, 0)}")
    return refs[:3]


def _build_rewrite_cards(
    stats: GrowthProfile,
    coaching: CoachingContent | None,
    prompt_style_signal,
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachRewriteCardView"]:
    from .prompt_coach_views import PromptCoachRewriteCardView

    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    source_notes = trainer_i18n.get("rewrite_source_notes", {})
    cards: list[PromptCoachRewriteCardView] = []
    seen: set[str] = set()
    samples = list(getattr(stats, "pq_top_takeaways", []) or [])
    if coaching is not None:
        samples.extend(
            PromptLensTakeaway(
                type="improve",
                category=getattr(item, "axis_key", "") or "collaboration_framing",
                label=item.label,
                original=item.evidence,
                better_prompt=item.better_prompt,
                why=item.message,
            )
            for item in getattr(coaching, "framing_evidence_takeaways", [])
            if getattr(item, "better_prompt", "")
        )
    for index, item in enumerate(samples, start=1):
        if item.type != "improve" or not item.better_prompt:
            continue
        if _looks_like_placeholder_prompt(item.better_prompt):
            continue
        card_id = f"rewrite:{index}"
        category = item.category or "request_specificity"
        scene = DIMENSION_SCENE_MAP.get(category, "requirements_design")
        original = item.original or ""
        problem = trainer_i18n.get("rewrite_problem_map", {}).get(category, trainer_i18n.get("rewrite_problem_default", ""))
        why = item.why or trainer_i18n.get("rewrite_why_default", "")
        better_prompt = item.better_prompt
        confidence = "high" if original else "medium"
        source_note = source_notes.get("verbatim", "verbatim")
        if _should_reframe_indexed_takeaway(prompt_style_signal, category, original):
            override = _indexed_rewrite_copy(prompt_style_signal, category, catalogs)
            problem = override.get("problem", problem)
            why = override.get("why", why)
            if _looks_like_rule_anchor_text(original):
                original = ""
                confidence = "medium"
                source_note = source_notes.get("indexed_summary", "indexed_summary")
            else:
                source_note = source_notes.get("summary_only", "summary_only")
        elif not original:
            source_note = source_notes.get("summary_only", "summary_only")
        signature = (category, original, item.better_prompt)
        if signature in seen:
            continue
        seen.add(signature)
        cards.append(
            PromptCoachRewriteCardView(
                id=card_id,
                scene=scene,
                original=original,
                problem=problem,
                better_prompt=better_prompt,
                why=why,
                category=category,
                confidence=confidence,
                evidence_refs=[_trim_text(original or item.message_ref or item.label, 140)] if (original or item.message_ref or item.label) else [],
                source_note=source_note,
            )
        )
        if len(cards) >= 4:
            break
    return cards[:4]


def _headline(
    top_deficits: list["PromptCoachDeficitView"],
    weak_dimensions: list[str],
    catalogs: ReportLabelCatalogs,
) -> str:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    if top_deficits:
        return trainer_i18n.get("headline_from_deficit", "").format(label=top_deficits[0].label)
    if weak_dimensions:
        return trainer_i18n.get("headline_from_dimension", "").format(label=weak_dimensions[0])
    return trainer_i18n.get("headline_light", "")


def _evidence_summary(
    top_deficits: list["PromptCoachDeficitView"],
    stats: GrowthProfile,
    catalogs: ReportLabelCatalogs,
) -> str:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    if top_deficits:
        return trainer_i18n.get("evidence_summary", "").format(
            deficit=top_deficits[0].label,
            count=(stats.pq_deficit_counts or {}).get(top_deficits[0].category, 0),
            sessions=stats.pq_sessions_evaluated,
        )
    return trainer_i18n.get("light_evidence_summary", "").format(sessions=stats.pq_sessions_evaluated)


def _source_note(
    stats: GrowthProfile,
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
) -> str:
    pc_i18n = catalogs.view_model.get("prompt_coach", {})
    trainer_i18n = pc_i18n.get("trainer", {})
    if stats.pq_sessions_evaluated <= 0:
        return trainer_i18n.get("source_note_light", "")

    source_truth = pc_i18n.get("source_truth", {})
    parts = [source_truth.get("prefix", "").format(total=stats.pq_sessions_evaluated)]
    status_counts = (
        ("llm_evaluated", stats.pq_llm_evaluated_count),
        ("insufficient", stats.pq_insufficient_count),
        ("llm_failed", stats.pq_llm_failed_count),
        ("llm_unavailable", stats.pq_llm_unavailable_count),
    )
    for key, count in status_counts:
        if count > 0:
            parts.append(source_truth.get(key, "").format(n=count))
    parts.append(source_truth.get("suffix", ""))
    return "".join(part for part in parts if part)


def _prompt_style_evidence(signal, stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> list[str]:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    rows: list[str] = []
    variable_key = "task_variables_yes" if signal.task_variables_present else "task_variables_no"
    variable_line = trainer_i18n.get("prompt_style_evidence", {}).get(variable_key, "")
    if signal.trigger_terms:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("trigger_terms", "触发词：{terms}").format(
                terms=" / ".join(signal.trigger_terms)
            )
        )
    if signal.task_variables_present and variable_line:
        rows.append(variable_line)
    if signal.rule_refs:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("rule_refs", "规则引用：{refs}").format(
                refs=" / ".join(signal.rule_refs)
            )
        )
    if signal.skill_refs:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("skill_refs", "技能路由：{refs}").format(
                refs=" / ".join(signal.skill_refs)
            )
        )
    if signal.slash_refs:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("slash_refs", "命令入口：{refs}").format(
                refs=" / ".join(signal.slash_refs)
            )
        )
    if signal.framework_refs:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("framework_refs", "框架工作流：{refs}").format(
                refs=" / ".join(signal.framework_refs)
            )
        )
    if getattr(stats, "agent_asset", None) is not None and stats.agent_asset.has_data:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get(
                "asset_anchor",
                "本地方法资产：已检测到规则 / skill / prompt 资产，可作为索引入口锚点。",
            ).format(
                skills=stats.agent_asset.skill_files_count,
                rules=stats.agent_asset.rule_files_count,
                prompts=stats.agent_asset.prompt_files_count,
            )
        )
    if not signal.task_variables_present and variable_line:
        rows.append(variable_line)
    return [item for item in rows if item]


def _prompt_style_message(signal, top_deficits, catalogs: ReportLabelCatalogs) -> str:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    messages = trainer_i18n.get("prompt_style_messages", {})
    focus_messages = trainer_i18n.get("prompt_style_focus_messages", {})
    if top_deficits:
        focus_text = (
            focus_messages.get(signal.prompt_style, {})
            .get(top_deficits[0].category, "")
        )
        if focus_text:
            return focus_text
    return messages.get(signal.prompt_style, "")


def _suggested_next_prompt(rewrite_cards) -> str:
    for item in rewrite_cards:
        prompt = (item.better_prompt or "").strip()
        if prompt and not _looks_like_placeholder_prompt(prompt):
            return prompt
    return ""


def _looks_like_placeholder_prompt(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    placeholder_markers = (
        "[问题]",
        "[路径]",
        "[不可改范围]",
        "[验证方式]",
        "[issue]",
        "[paths]",
        "[must not change]",
        "[verification]",
        "<你要完成什么>",
        "<现状/报错/背景>",
        "<路径1, 路径2>",
        "<不允许改什么>",
        "<如何算完成>",
        "<trigger>",
        "<paths>",
    )
    if any(marker in value for marker in placeholder_markers):
        return True
    # Template-like ellipses are allowed in checklist/template assets, but not
    # as personalized rewrite cards or "next prompt" advice.
    if "..." in value or "…" in value:
        return True
    if "：" in value and "<" in value and ">" in value:
        return True
    return False


def _trigger_maturity_lines(signal, catalogs: ReportLabelCatalogs) -> list[str]:
    maturity_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("trigger_maturity", {})
    rows = [
        maturity_i18n.get("stability", "").format(
            value=maturity_i18n.get("stability_values", {}).get(signal.stability, signal.stability)
        ),
        maturity_i18n.get("rule_support", "").format(
            value=maturity_i18n.get("rule_support_values", {}).get(signal.rule_support, signal.rule_support)
        ),
        maturity_i18n.get("retrievability", "").format(
            value=maturity_i18n.get("retrievability_values", {}).get(signal.retrievability, signal.retrievability)
        ),
        maturity_i18n.get("variable_completion", "").format(
            value=maturity_i18n.get("variable_completion_values", {}).get(signal.variable_completion, signal.variable_completion)
        ),
        maturity_i18n.get("assetization", "").format(
            value=maturity_i18n.get("assetization_values", {}).get(signal.assetization, signal.assetization)
        ),
    ]
    return [item for item in rows if item]


def _closure_message(signal, catalogs: ReportLabelCatalogs) -> str:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    task_label = trainer_i18n.get("task_type_labels", {}).get(signal.task_type, signal.task_type)
    expected = " / ".join(
        trainer_i18n.get("closure_methods", {}).get(item, item)
        for item in signal.expected_closure_methods
    )
    missing = " / ".join(
        trainer_i18n.get("closure_methods", {}).get(item, item)
        for item in signal.missing_closure_methods
    )
    key = "closure_message_with_gap" if signal.missing_closure_methods else "closure_message_complete"
    return trainer_i18n.get(key, "").format(
        task_type=task_label,
        expected=expected,
        missing=missing,
    )


def _deficit_copy(
    key: str,
    prompt_style_signal,
    catalogs: ReportLabelCatalogs,
) -> dict[str, str]:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    defaults = trainer_i18n.get("deficits", {}).get(key, {})
    if prompt_style_signal.prompt_style in {"indexed_prompt", "mixed_prompt"} and prompt_style_signal.has_rule_anchor:
        override = trainer_i18n.get("indexed_deficit_overrides", {}).get(key, {})
        if override:
            return {
                "description": override.get("description", defaults.get("description", "")),
                "impact": override.get("impact", defaults.get("impact", "")),
            }
    return {
        "description": defaults.get("description", ""),
        "impact": defaults.get("impact", ""),
    }


def _indexed_rewrite_copy(
    prompt_style_signal,
    category: str,
    catalogs: ReportLabelCatalogs,
) -> dict[str, str]:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    style_key = (
        prompt_style_signal.prompt_style
        if prompt_style_signal.prompt_style in {"indexed_prompt", "mixed_prompt"}
        else "indexed_prompt"
    )
    scoped = trainer_i18n.get("indexed_rewrite_overrides", {}).get(style_key, {})
    return {
        "problem": scoped.get("problem_map", {}).get(category, scoped.get("problem", "")),
        "why": scoped.get("why", trainer_i18n.get("rewrite_why_default", "")),
    }


def _should_reframe_indexed_takeaway(prompt_style_signal, category: str, original: str) -> bool:
    if prompt_style_signal.prompt_style not in {"indexed_prompt", "mixed_prompt"}:
        return False
    if not prompt_style_signal.has_rule_anchor:
        return False
    return _looks_like_rule_anchor_text(original) or category in {"context_provision", "request_specificity"}


def _looks_like_rule_anchor_text(text: str) -> bool:
    lower = (text or "").lower()
    if not lower:
        return False
    anchor_hits = sum(
        1
        for token in (
            "agents.md",
            "claude.md",
            "project_rules.md",
            "cursor rules",
            ".cursor/rules",
            "instructions",
            "<instructions>",
            "workflow",
            "skill",
        )
        if token in lower
    )
    return anchor_hits >= 2 or lower.startswith("# agents.md instructions") or "<instructions>" in lower


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def empty_prompt_coach_view() -> PromptCoachView:
    from .prompt_coach_views import PromptCoachView

    return PromptCoachView(
        available=False,
        headline="",
        strongest_label="",
        weakest_label="",
        evidence_summary="",
        strength_habit="",
    )


def build_prompt_coach_view_from_payload(payload: dict | None) -> PromptCoachView:
    from .prompt_coach_views import (
        PromptCoachFrictionSynthesisView,
        PromptCoachRewriteCardView,
        PromptCoachSourceSummaryView,
        PromptCoachView,
    )

    if not isinstance(payload, dict) or not payload:
        return empty_prompt_coach_view()
    source_summary_payload = payload.get("source_summary") or {}
    source_summary = PromptCoachSourceSummaryView(
        llm_session_count=int(source_summary_payload.get("llm_session_count", 0) or 0),
        heuristic_session_count=int(source_summary_payload.get("heuristic_session_count", 0) or 0),
        light_session_count=int(source_summary_payload.get("light_session_count", 0) or 0),
        evaluated_user_messages=int(source_summary_payload.get("evaluated_user_messages", 0) or 0),
        run_mode=str(source_summary_payload.get("run_mode", "llm") or "llm"),
        llm_evaluated_count=int(source_summary_payload.get("llm_evaluated_count", 0) or 0),
        insufficient_count=int(source_summary_payload.get("insufficient_count", 0) or 0),
        llm_failed_count=int(source_summary_payload.get("llm_failed_count", 0) or 0),
        llm_unavailable_count=int(source_summary_payload.get("llm_unavailable_count", 0) or 0),
    )
    rewrite_cards = [
        PromptCoachRewriteCardView(
            id=str(item.get("id", "")),
            scene=str(item.get("scene", "")),
            original=str(item.get("original", "")),
            problem=str(item.get("problem", "")),
            better_prompt=str(item.get("better_prompt", "")),
            why=str(item.get("why", "")),
            category=str(item.get("category", "")),
            confidence=str(item.get("confidence", "")),
            evidence_refs=[str(ref) for ref in item.get("evidence_refs", []) if ref],
            source_note=str(item.get("source_note", "")),
        )
        for item in payload.get("rewrite_cards", [])
        if isinstance(item, dict)
    ]
    friction_synthesis = [
        PromptCoachFrictionSynthesisView(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            explanation=str(item.get("explanation", "")),
            next_action=str(item.get("next_action", "")),
            confidence=int(item.get("confidence", 0) or 0),
            evidence_refs=[str(ref) for ref in item.get("evidence_refs", []) if ref],
            generated_by=str(item.get("generated_by", "rule") or "rule"),
        )
        for item in payload.get("friction_synthesis", [])
        if isinstance(item, dict)
    ]
    return PromptCoachView(
        available=bool(payload.get("headline") or rewrite_cards or friction_synthesis),
        headline=str(payload.get("headline", "")),
        strongest_label=str(payload.get("strongest_label", "")),
        weakest_label=str(payload.get("weakest_label", "")),
        evidence_summary=str(payload.get("evidence_summary", "")),
        strength_habit=str(payload.get("strength_habit", "")),
        source_note=str(payload.get("source_note", "")),
        light_state_note=str(payload.get("light_state_note", "")),
        source_summary=source_summary,
        weak_dimensions=[str(item) for item in payload.get("weak_dimensions", []) if item],
        deficits=[str(item) for item in payload.get("deficits", []) if item],
        rewrite_cards=rewrite_cards,
        friction_synthesis=friction_synthesis,
    )
