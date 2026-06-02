"""Application-owned prompt coach assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.growth.coaching import CoachingContent
from ..domain.growth.model import GrowthProfile
from ..domain.growth.prompting import (
    assess_closure_guidance,
    assess_prompt_style,
    build_friction_synthesis_intents,
    build_recommended_training_inputs,
)
from ..domain.session.model import SessionRecord
from ..domain.signals.model import PromptLensTakeaway, SessionRead
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from .report_view import (
        PromptCoachChecklistItemView,
        PromptCoachClosureGuidanceView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachPromptStyleView,
        PromptCoachRewriteCardView,
        PromptCoachSourceSummaryView,
        PromptCoachTakeawayView,
        PromptCoachTemplateView,
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
    from .report_view import (
        PromptCoachChecklistItemView,
        PromptCoachClosureGuidanceView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachFrictionSynthesisView,
        PromptCoachPromptStyleView,
        PromptCoachRewriteCardView,
        PromptCoachSourceSummaryView,
        PromptCoachTakeawayView,
        PromptCoachTemplateView,
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
    top_deficit_keys = _rank_top_deficits(stats)
    prompt_style_signal, trigger_maturity = assess_prompt_style(sessions, session_reads)
    closure_signal = assess_closure_guidance(sessions, session_reads)
    universal_template = _build_universal_template(catalogs)
    top_deficits = [
        PromptCoachDeficitView(
            id=f"deficit:{key.replace('-', '_')}",
            category=key,
            label=_deficit_label(key, catalogs),
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
        universal_template.template,
        catalogs,
    )
    scenario_templates = _build_scenario_templates(catalogs)
    checklist = _build_preflight_checklist(top_deficits, catalogs)
    prompt_style = PromptCoachPromptStyleView(
        type=prompt_style_signal.prompt_style,
        label=trainer_i18n.get("prompt_style_labels", {}).get(prompt_style_signal.prompt_style, prompt_style_signal.prompt_style),
        evidence=_prompt_style_evidence(prompt_style_signal, stats, catalogs),
        coaching_message=_prompt_style_message(prompt_style_signal, catalogs),
        suggested_next_prompt=_suggested_next_prompt(prompt_style_signal, universal_template.template, catalogs),
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
    recommended_training_inputs = build_recommended_training_inputs(
        prompt_style_signal,
        closure_signal,
        top_deficit_keys,
    )
    source_note = _source_note(stats, session_read_mode, catalogs)
    weak_dimensions = [item.label for item in dimension_scores[:2]]
    deficits = [
        f"{item.label} · {item.confidence}"
        for item in top_deficits
    ]
    takeaways = _legacy_takeaways(stats, rewrite_cards, top_deficits, catalogs)
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
        takeaways=takeaways,
        source_summary=source_summary,
        top_deficits=top_deficits,
        rewrite_cards=rewrite_cards,
        universal_template=universal_template,
        scenario_templates=scenario_templates,
        preflight_checklist=checklist,
        prompt_style=prompt_style,
        closure_guidance=closure_guidance,
        recommended_training_inputs=_recommended_training_inputs(recommended_training_inputs, catalogs),
        friction_synthesis=friction_synthesis,
        light_state_note=light_state_note,
    )


def _build_friction_synthesis_views(
    *,
    coaching: CoachingContent | None,
    intents: list,
    pc_i18n: dict,
) -> list["PromptCoachFrictionSynthesisView"]:
    from .report_view import PromptCoachFrictionSynthesisView

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
        rule_rows.append(
            PromptCoachFrictionSynthesisView(
                id=intent.id,
                label=copy.get("label", ""),
                explanation=copy.get("explanation", ""),
                next_action=copy.get("next_action", ""),
                confidence=intent.confidence,
                evidence_refs=list(intent.evidence_refs),
                generated_by="rule",
            )
        )
    return rule_rows[:2]


def _rank_top_deficits(stats: GrowthProfile) -> list[str]:
    counts = stats.pq_deficit_counts or {}
    ranked = [
        key
        for key in TOP_DEFICIT_ORDER
        if counts.get(key, 0) > 0
    ]
    ranked.sort(key=lambda key: (-counts.get(key, 0), TOP_DEFICIT_ORDER.index(key)))
    return ranked[:3]


def _deficit_label(key: str, catalogs: ReportLabelCatalogs) -> str:
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
    universal_template: str,
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachRewriteCardView"]:
    from .report_view import PromptCoachRewriteCardView

    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    actions_i18n = trainer_i18n.get("rewrite_fallbacks", {})
    source_notes = trainer_i18n.get("rewrite_source_notes", {})
    cards: list[PromptCoachRewriteCardView] = []
    seen: set[str] = set()
    samples = list(getattr(stats, "pq_top_takeaways", []) or [])
    if coaching is not None:
        samples.extend(
            PromptLensTakeaway(
                type="improve",
                category="request_specificity",
                label=item.label,
                original=item.evidence,
                better_prompt=item.better_prompt,
                why=item.message,
            )
            for item in getattr(coaching, "prompt_coach_takeaways", [])
            if getattr(item, "better_prompt", "")
        )
    for index, item in enumerate(samples, start=1):
        if item.type != "improve" or not item.better_prompt:
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
            better_prompt = override.get("better_prompt") or better_prompt or _suggested_next_prompt(prompt_style_signal, universal_template, catalogs)
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
    if cards:
        return cards[:4]

    if prompt_style_signal.prompt_style in {"indexed_prompt", "mixed_prompt"}:
        override = _indexed_rewrite_copy(prompt_style_signal, "context_provision", catalogs)
        cards.append(
            PromptCoachRewriteCardView(
                id="rewrite:indexed:1",
                scene=prompt_style_signal.trigger_terms[0] if prompt_style_signal.trigger_terms else "requirements_design",
                original="",
                problem=override.get("problem", ""),
                better_prompt=override.get("better_prompt") or _suggested_next_prompt(prompt_style_signal, universal_template, catalogs),
                why=override.get("why", ""),
                category="context_provision",
                confidence="medium",
                evidence_refs=[],
                source_note=source_notes.get("indexed_summary", "indexed_summary"),
            )
        )
        if prompt_style_signal.task_variables_present:
            return cards[:1]

    for index, (category, payload) in enumerate(actions_i18n.items(), start=1):
        cards.append(
            PromptCoachRewriteCardView(
                id=f"rewrite:fallback:{index}",
                scene=payload.get("scene", "requirements_design"),
                original="",
                problem=payload.get("problem", ""),
                better_prompt=payload.get("better_prompt", ""),
                why=payload.get("why", ""),
                category=category,
                confidence="low",
                evidence_refs=[],
                source_note=source_notes.get("light_template", "light_template"),
            )
        )
        if len(cards) >= 2:
            break
    return cards


def _build_universal_template(catalogs: ReportLabelCatalogs) -> "PromptCoachTemplateView":
    from .report_view import PromptCoachTemplateView

    payload = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("universal_template", {})
    return PromptCoachTemplateView(
        id="template:universal",
        title=payload.get("title", ""),
        scene="universal",
        common_gap=payload.get("common_gap", ""),
        template=payload.get("body", ""),
    )


def _build_scenario_templates(catalogs: ReportLabelCatalogs) -> list["PromptCoachTemplateView"]:
    from .report_view import PromptCoachTemplateView

    rows = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("scenario_templates", [])
    return [
        PromptCoachTemplateView(
            id=str(row.get("id", "")),
            title=str(row.get("title", "")),
            scene=str(row.get("scene", "")),
            common_gap=str(row.get("common_gap", "")),
            template=str(row.get("template", "")),
        )
        for row in rows
    ]


def _build_preflight_checklist(
    top_deficits: list["PromptCoachDeficitView"],
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachChecklistItemView"]:
    from .report_view import PromptCoachChecklistItemView

    checklist_map = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("checklist_map", {})
    items: list[PromptCoachChecklistItemView] = []
    seen: set[str] = set()
    for deficit in top_deficits:
        for idx, text in enumerate(checklist_map.get(deficit.category, []), start=1):
            if text in seen:
                continue
            seen.add(text)
            items.append(
                PromptCoachChecklistItemView(
                    id=f"check:{deficit.category}:{idx}",
                    text=text,
                    related_deficit_id=deficit.id,
                )
            )
    default_items = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("checklist_default", [])
    for idx, text in enumerate(default_items, start=1):
        if text in seen:
            continue
        items.append(
            PromptCoachChecklistItemView(
                id=f"check:default:{idx}",
                text=text,
                related_deficit_id=top_deficits[0].id if top_deficits else "",
            )
        )
    return items[:6]


def _legacy_takeaways(
    stats: GrowthProfile,
    rewrite_cards: list["PromptCoachRewriteCardView"],
    top_deficits: list["PromptCoachDeficitView"],
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachTakeawayView"]:
    from .report_view import PromptCoachTakeawayView

    actions = catalogs.view_model.get("prompt_coach", {}).get("takeaway_actions", {})
    rows: list[PromptCoachTakeawayView] = []
    for item in list(getattr(stats, "pq_top_takeaways", []) or [])[:2]:
        rows.append(
            PromptCoachTakeawayView(
                label=item.label or item.category or "",
                kind=actions.get("kind_example", "Example"),
                evidence=item.original or item.message_ref or "",
                message=item.why or "",
                action=actions.get("improve", ""),
                better_prompt=item.better_prompt,
            )
        )
    if not rows:
        for card in rewrite_cards[:2]:
            rows.append(
                PromptCoachTakeawayView(
                    label=card.scene,
                    kind=actions.get("kind_example", "Example"),
                    evidence=card.original or card.source_note,
                    message=card.problem,
                    action=actions.get("improve", ""),
                    better_prompt=card.better_prompt,
                )
            )
    if top_deficits:
        deficit = top_deficits[0]
        rows.append(
            PromptCoachTakeawayView(
                label=deficit.label,
                kind=actions.get("kind_reinforce", "Gap"),
                evidence=" / ".join(deficit.evidence_refs[:2]),
                message=deficit.description,
                action=deficit.impact,
                better_prompt="",
            )
        )
    elif rows:
        rows.append(
            PromptCoachTakeawayView(
                label=rows[0].label,
                kind=actions.get("kind_reinforce", "Keep"),
                evidence=rows[0].evidence,
                message=catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("strength_habit", "").format(label=rows[0].label),
                action=actions.get("reinforce", actions.get("improve", "")),
                better_prompt="",
            )
        )
    return rows[:3]


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
    if signal.trigger_terms:
        rows.append(
            trainer_i18n.get("prompt_style_evidence", {}).get("trigger_terms", "触发词：{terms}").format(
                terms=" / ".join(signal.trigger_terms)
            )
        )
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
    variable_key = "task_variables_yes" if signal.task_variables_present else "task_variables_no"
    rows.append(
        trainer_i18n.get("prompt_style_evidence", {}).get(variable_key, "")
    )
    return [item for item in rows if item]


def _prompt_style_message(signal, catalogs: ReportLabelCatalogs) -> str:
    messages = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("prompt_style_messages", {})
    return messages.get(signal.prompt_style, "")


def _suggested_next_prompt(signal, universal_template: str, catalogs: ReportLabelCatalogs) -> str:
    templates = catalogs.view_model.get("prompt_coach", {}).get("trainer", {}).get("prompt_style_next_prompt", {})
    prompt = templates.get(signal.prompt_style, "")
    if prompt:
        return prompt
    return universal_template


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


def _recommended_training_inputs(codes: list[str], catalogs: ReportLabelCatalogs) -> list[str]:
    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    closure_labels = trainer_i18n.get("closure_methods", {})
    templates = trainer_i18n.get("recommended_training_inputs", {})
    rows: list[str] = []
    for code in codes:
        if code.startswith("style:"):
            key = code.split(":", 1)[1]
            text = templates.get(code) or templates.get(f"style:{key}", "")
        elif code.startswith("deficit:"):
            key = code.split(":", 1)[1]
            text = templates.get(code) or templates.get(f"deficit:{key}", "")
        elif code.startswith("closure:"):
            key = code.split(":", 1)[1]
            text = (templates.get("closure") or "").format(method=closure_labels.get(key, key))
        else:
            text = ""
        if text:
            rows.append(text)
    return rows[:4]


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
    prompt = _suggested_next_prompt(prompt_style_signal, "", catalogs)
    style_key = (
        prompt_style_signal.prompt_style
        if prompt_style_signal.prompt_style in {"indexed_prompt", "mixed_prompt"}
        else "indexed_prompt"
    )
    scoped = trainer_i18n.get("indexed_rewrite_overrides", {}).get(style_key, {})
    return {
        "problem": scoped.get("problem_map", {}).get(category, scoped.get("problem", "")),
        "why": scoped.get("why", trainer_i18n.get("rewrite_why_default", "")),
        "better_prompt": scoped.get("better_prompt", prompt) or prompt,
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
