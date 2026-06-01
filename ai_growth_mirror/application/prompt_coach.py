"""Application-owned prompt coach assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.growth.coaching import CoachingContent
from ..domain.growth.model import GrowthProfile
from ..domain.signals.model import PromptLensTakeaway, SessionRead
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from .report_view import (
        PromptCoachChecklistItemView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachRewriteCardView,
        PromptCoachSevenDayView,
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
    session_reads: list[SessionRead],
    session_read_mode: str,
    catalogs: ReportLabelCatalogs,
    coaching: CoachingContent | None = None,
) -> "PromptCoachView":
    from .report_view import (
        PromptCoachChecklistItemView,
        PromptCoachDeficitView,
        PromptCoachDimensionView,
        PromptCoachRewriteCardView,
        PromptCoachSevenDayView,
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
    )
    dimension_scores = [
        PromptCoachDimensionView(label=dim_labels.get(key, key), score=round(float(score), 1))
        for key, score in sorted((stats.pq_avg_dimensions or {}).items(), key=lambda item: item[1])
    ]
    top_deficit_keys = _rank_top_deficits(stats)
    top_deficits = [
        PromptCoachDeficitView(
            id=f"deficit:{key.replace('-', '_')}",
            category=key,
            label=_deficit_label(key, catalogs),
            description=trainer_i18n.get("deficits", {}).get(key, {}).get("description", ""),
            impact=trainer_i18n.get("deficits", {}).get(key, {}).get("impact", ""),
            confidence=_deficit_confidence(stats, key),
            evidence_refs=_evidence_refs_for_deficit(key, session_reads, stats),
            source=_deficit_source(stats, key),
        )
        for key in top_deficit_keys
    ]
    rewrite_cards = _build_rewrite_cards(stats, coaching, catalogs)
    universal_template = _build_universal_template(catalogs)
    scenario_templates = _build_scenario_templates(catalogs)
    checklist = _build_preflight_checklist(top_deficits, catalogs)
    seven_day_training_plan = _build_seven_day_plan(
        top_deficits=top_deficits,
        rewrite_cards=rewrite_cards,
        universal_template=universal_template,
        catalogs=catalogs,
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
        seven_day_training_plan=seven_day_training_plan,
        light_state_note=light_state_note,
    )


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
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachRewriteCardView"]:
    from .report_view import PromptCoachRewriteCardView

    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    actions_i18n = trainer_i18n.get("rewrite_fallbacks", {})
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
        confidence = "high" if original else "medium"
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
                better_prompt=item.better_prompt,
                why=item.why or trainer_i18n.get("rewrite_why_default", ""),
                category=category,
                confidence=confidence,
                evidence_refs=[_trim_text(original or item.message_ref or item.label, 140)] if (original or item.message_ref or item.label) else [],
                source_note="verbatim" if original else "summary_only",
            )
        )
        if len(cards) >= 4:
            break
    if cards:
        return cards[:4]

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
                source_note="light_template",
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


def _build_seven_day_plan(
    *,
    top_deficits: list["PromptCoachDeficitView"],
    rewrite_cards: list["PromptCoachRewriteCardView"],
    universal_template: "PromptCoachTemplateView",
    catalogs: ReportLabelCatalogs,
) -> list["PromptCoachSevenDayView"]:
    from .report_view import PromptCoachSevenDayView

    trainer_i18n = catalogs.view_model.get("prompt_coach", {}).get("trainer", {})
    daily_templates = trainer_i18n.get("seven_day_plan", [])
    primary_deficit = top_deficits[0] if top_deficits else None
    primary_card = rewrite_cards[0] if rewrite_cards else None
    rows: list[PromptCoachSevenDayView] = []
    for idx, row in enumerate(daily_templates, start=1):
        practice_prompt = primary_card.better_prompt if primary_card and idx in (3, 5, 7) else universal_template.template
        rows.append(
            PromptCoachSevenDayView(
                day=int(row.get("day", idx)),
                theme=str(row.get("theme", "")).format(
                    deficit=primary_deficit.label if primary_deficit else "",
                ),
                action=str(row.get("action", "")).format(
                    deficit=primary_deficit.label if primary_deficit else "",
                ),
                practice_prompt=practice_prompt,
            )
        )
    return rows


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
    if stats.pq_llm_session_count and stats.pq_heuristic_session_count:
        base = trainer_i18n.get("source_note_mixed", "")
    elif stats.pq_llm_session_count:
        base = trainer_i18n.get("source_note_llm", "")
    elif stats.pq_sessions_evaluated:
        base = trainer_i18n.get("source_note_heuristic", "")
    else:
        base = trainer_i18n.get("source_note_light", "")
    breakdown = pc_i18n.get("source_breakdown", {})
    template = (
        breakdown.get("mixed")
        if stats.pq_llm_session_count and stats.pq_heuristic_session_count
        else breakdown.get("llm_only")
        if stats.pq_llm_session_count
        else breakdown.get("heuristic_only")
    )
    if not template:
        return base
    detail = template.format(
        total=stats.pq_sessions_evaluated,
        llm=stats.pq_llm_session_count,
        heuristic=stats.pq_heuristic_session_count,
        light=stats.pq_light_session_count,
    )
    if session_read_mode == "heuristic" and not stats.pq_llm_session_count:
        return f"{base} {detail}".strip()
    return f"{base} {detail}".strip()


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
