"""Stable structured summary payloads for personal report consumers."""

from __future__ import annotations

from .report_view import PersonalReportView


def _growth_trajectory_payload(view: PersonalReportView) -> dict[str, object]:
    if not view.growth_trajectory:
        return {"available": False, "window_days": 30, "points": [], "trend_summary": {}, "latest_vs_previous": {}}
    payload = dict(view.growth_trajectory.data or {})
    payload["available"] = bool(view.growth_trajectory.available)
    payload.setdefault("window_days", 30)
    payload.setdefault("points", [])
    payload.setdefault("display_points", [])
    payload.setdefault("trend_summary", {})
    payload.setdefault("latest_vs_previous", {})
    return payload


def _prompt_coach_payload(view: PersonalReportView) -> dict[str, object]:
    coach = view.prompt_coach
    return {
        "headline": coach.headline,
        "strongest_label": coach.strongest_label,
        "weakest_label": coach.weakest_label,
        "evidence_summary": coach.evidence_summary,
        "strength_habit": coach.strength_habit,
        "source_note": coach.source_note,
        "light_state_note": coach.light_state_note,
        "source_summary": {
            "llm_session_count": coach.source_summary.llm_session_count,
            "heuristic_session_count": coach.source_summary.heuristic_session_count,
            "light_session_count": coach.source_summary.light_session_count,
            "evaluated_user_messages": coach.source_summary.evaluated_user_messages,
        },
        "weak_dimensions": list(coach.weak_dimensions),
        "deficits": list(coach.deficits),
        "top_deficits": [
            {
                "id": item.id,
                "category": item.category,
                "label": item.label,
                "description": item.description,
                "impact": item.impact,
                "confidence": item.confidence,
                "evidence_refs": list(item.evidence_refs),
                "source": item.source,
            }
            for item in coach.top_deficits
        ],
        "rewrite_cards": [
            {
                "id": item.id,
                "scene": item.scene,
                "original": item.original,
                "problem": item.problem,
                "better_prompt": item.better_prompt,
                "why": item.why,
                "category": item.category,
                "confidence": item.confidence,
                "evidence_refs": list(item.evidence_refs),
                "source_note": item.source_note,
            }
            for item in coach.rewrite_cards
        ],
        "takeaways": [
            {
                "label": item.label,
                "kind": item.kind,
                "evidence": item.evidence,
                "message": item.message,
                "action": item.action,
                "better_prompt": item.better_prompt,
            }
            for item in coach.takeaways
        ],
        "universal_template": {
            "id": coach.universal_template.id,
            "title": coach.universal_template.title,
            "scene": coach.universal_template.scene,
            "common_gap": coach.universal_template.common_gap,
            "body": coach.universal_template.template,
        }
        if coach.universal_template
        else {},
        "scenario_templates": [
            {
                "id": item.id,
                "title": item.title,
                "scene": item.scene,
                "common_gap": item.common_gap,
                "template": item.template,
            }
            for item in coach.scenario_templates
        ],
        "preflight_checklist": [
            {
                "id": item.id,
                "text": item.text,
                "related_deficit_id": item.related_deficit_id,
            }
            for item in coach.preflight_checklist
        ],
        "seven_day_training_plan": [
            {
                "day": item.day,
                "theme": item.theme,
                "action": item.action,
                "practice_prompt": item.practice_prompt,
            }
            for item in coach.seven_day_training_plan
        ],
    }


def _growth_plan_payload(view: PersonalReportView) -> dict[str, object]:
    return {
        "headline": view.growth_plan.headline,
        "next_focus": view.growth_plan.next_focus,
        "priorities": [
            {
                "id": item.id,
                "key": item.key,
                "title": item.title,
                "why": item.why,
                "evidence_refs": list(item.evidence_refs),
                "week_1_actions": list(item.week_1_actions),
                "week_2_actions": list(item.week_2_actions),
                "practice_prompt": item.practice_prompt,
                "success_signal": item.success_signal,
                "stop_doing": item.stop_doing,
                "linked_prompt_deficit_ids": list(item.linked_prompt_deficit_ids),
                "linked_template_ids": list(item.linked_template_ids),
                "linked_rewrite_card_ids": list(item.linked_rewrite_card_ids),
            }
            for item in view.growth_plan.priorities
        ],
    }


def build_personal_summary_payload(view: PersonalReportView) -> dict[str, object]:
    growth_stage = view.growth_stage
    gap_rankings = [
        {
            "key": item.key,
            "label": item.label,
            "severity": item.severity,
            "rank": item.rank,
            "evidence_summary": item.evidence_summary,
            "why_it_happens": item.why_it_happens,
            "suggested_action": item.suggested_action,
        }
        for item in view.gap_rankings
    ]
    radar_axes = [
        {
            "key": item.key,
            "label": item.label,
            "score": item.score,
            "status": item.status,
            "short_reason": item.short_reason,
            "confidence": item.confidence,
        }
        for item in view.radar_axes
    ]
    return {
        "schema_version": "2.0",
        "report_type": "personal_growth_summary",
        "report_title": view.report_title,
        "tool_display_name": view.tool_display_name,
        "date_range": view.date_range,
        "generated_at": view.generated_at,
        "summary": {
            "headline": view.summary.headline,
            "mirror_score": view.summary.mirror_score,
            "growth_level": view.summary.growth_level,
            "strongest_signal": view.summary.strongest_signal,
            "next_focus": view.summary.next_focus,
            "growth_stage": {
                "level": growth_stage.level if growth_stage else view.summary.growth_level,
                "label": growth_stage.label if growth_stage else "",
                "summary": growth_stage.summary if growth_stage else "",
                "strongest_axis": growth_stage.strongest_axis if growth_stage else "",
                "primary_gap": growth_stage.primary_gap if growth_stage else "",
                "next_breakthrough": growth_stage.next_breakthrough if growth_stage else view.summary.next_focus,
            },
        },
        "share_card": {
            "title": view.summary.share_title,
            "lines": list(view.summary.share_lines),
            "headline": view.summary.headline,
            "stage": view.summary.growth_level,
            "score_display": view.summary.score_display or str(view.summary.mirror_score),
            "strongest_habit": view.summary.strongest_signal,
            "current_breakthrough": view.summary.next_focus,
        },
        "scorecard": {
            "radar_axes": radar_axes,
        },
        "capabilities": [
            {
                "key": item.key,
                "label": item.label,
                "score": item.score,
                "explanation": item.explanation,
                "next_action": item.next_action,
            }
            for item in view.capability.dimensions
        ],
        "level_evidence": {
            "current_level": view.level_evidence.current_level,
            "target_level": view.level_evidence.target_level,
            "target_caption": view.level_evidence.target_caption,
            "verdict": view.level_evidence.verdict,
            "progress_summary": view.level_evidence.progress_summary,
            "blocker_title": view.level_evidence.blocker_title,
            "methodology_title": view.level_evidence.methodology_title,
            "methodology_lines": list(view.level_evidence.methodology_lines),
            "blockers": list(view.level_evidence.blockers),
            "metrics": [
                {
                    "label": item.label,
                    "current_value": item.current_value,
                    "target_value": item.target_value,
                    "status": item.status,
                    "explanation": item.explanation,
                    "raw_signal": item.raw_signal,
                }
                for item in view.level_evidence.metrics
            ],
            "next_step": view.level_evidence.next_step,
        },
        "growth_signals": {
            "gap_rankings": gap_rankings,
        },
        "evidence": {
            "key_patterns": [item.title for item in view.wins.wins[:3]],
            "risk_overview": list(view.level_evidence.blockers[:3]),
        },
        "growth_trajectory": _growth_trajectory_payload(view),
        "next_actions": [
            {
                "key": item.key,
                "title": item.title,
                "why": item.why,
                "action": (item.week_1_actions[0] if item.week_1_actions else item.practice_prompt),
                "success_signal": item.success_signal,
            }
            for item in view.growth_plan.priorities[:2]
        ],
        "collaboration_rhythm": {
            "label": view.collaboration_rhythm.rhythm_label,
            "summary": view.collaboration_rhythm.rhythm_summary,
            "next_action": view.collaboration_rhythm.next_action,
            "stats": [
                {"label": item.label, "value": item.value, "detail": item.detail}
                for item in view.collaboration_rhythm.stats
            ],
        },
        "usage": {
            "headline": view.usage.headline,
            "summary": view.usage.summary,
            "memory_note": view.usage.memory_note,
            "stats": [
                {"label": item.label, "value": item.value, "detail": item.detail}
                for item in view.usage.stats
            ],
        },
        "work_focus": {
            "projects": list(view.work_focus.projects),
            "goal_mix": [
                {"label": item.label, "count": item.count, "detail": item.detail}
                for item in view.work_focus.goal_mix
            ],
            "tools": [
                {"label": item.label, "count": item.count, "detail": item.detail}
                for item in view.work_focus.tools
            ],
            "languages": [
                {"label": item.label, "count": item.count, "detail": item.detail}
                for item in view.work_focus.languages
            ],
        },
        "wins": [
            {
                "title": item.title,
                "evidence": item.evidence,
                "why_it_matters": item.why_it_matters,
                "next_action": item.next_action,
            }
            for item in view.wins.wins
        ],
        "exemplars": [
            {
                "category_label": item.category_label,
                "score": item.score,
                "project_name": item.project_name,
                "summary": item.summary,
                "facts": item.facts,
                "why_keep": item.why_keep,
                "next_reuse": item.technique,
            }
            for item in view.exemplars
        ],
        "prompt_coach": _prompt_coach_payload(view),
        "style_system": {
            "archetype_name": view.style_lens.archetype_name,
            "archetype_tag": view.style_lens.archetype_tag,
            "slogan": view.style_lens.slogan,
            "description": view.style_lens.description,
            "strengths": list(view.style_lens.strengths),
            "growth_areas": list(view.style_lens.growth_areas),
            "dimensions": [
                {
                    "label": item.label,
                    "left_pole": item.left_pole,
                    "right_pole": item.right_pole,
                    "pct": item.pct,
                    "interpretation": item.interpretation,
                }
                for item in view.style_lens.dimensions
            ],
        },
        "growth_plan": _growth_plan_payload(view),
    }
