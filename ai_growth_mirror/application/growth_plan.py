"""Application-owned personal growth plan assembly."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..domain.growth.model import GrowthProfile
from ..domain.growth.planning import select_growth_priority_keys
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from .growth_trajectory import GrowthTrajectoryView
    from .report_view import PromptCoachView


_PROMPT_DIMENSION_BY_DEFICIT = {
    "missing-context": "context_provision",
    "vague-request": "request_specificity",
    "late-constraint": "information_timing",
    "scope-drift": "scope_management",
    "unclear-correction": "correction_quality",
    "missing-acceptance-criteria": "request_specificity",
    "assumption-not-surfaced": "context_provision",
}

_DEFICIT_FAMILY_MAP = {
    "collaboration_framing": {"missing-context", "vague-request", "assumption-not-surfaced"},
    "delivery_closure": {"missing-acceptance-criteria"},
    "adaptive_recovery": {"unclear-correction", "scope-drift"},
}

_SCENE_MAP_BY_PROMPT_DIMENSION = {
    "context_provision": {"requirements_design", "bug_triage"},
    "request_specificity": {"code_review", "copy_polish"},
    "scope_management": {"architecture_refactor"},
    "information_timing": {"bug_triage", "chart_analysis"},
    "correction_quality": {"bug_triage"},
}


@dataclass
class GrowthPriorityView:
    key: str
    title: str
    why: str
    success_signal: str = ""
    stop_doing: str = ""
    week_1_actions: list[str] = field(default_factory=list)
    week_2_actions: list[str] = field(default_factory=list)
    practice_prompt: str = ""
    id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    linked_prompt_deficit_ids: list[str] = field(default_factory=list)
    linked_template_ids: list[str] = field(default_factory=list)
    linked_rewrite_card_ids: list[str] = field(default_factory=list)
    linked_growth_trend_refs: list[str] = field(default_factory=list)
    linked_closure_guidance_ids: list[str] = field(default_factory=list)
    linked_friction_synthesis_ids: list[str] = field(default_factory=list)
    action_contract: list[str] = field(default_factory=list)


@dataclass
class GrowthPlanView:
    headline: str
    next_focus: str
    priorities: list[GrowthPriorityView] = field(default_factory=list)


def _priority_from_yaml(key: str, data: dict[str, Any], **fmt: Any) -> GrowthPriorityView:
    def _fmt(text: str) -> str:
        try:
            return text.format(**fmt) if fmt else text
        except (KeyError, ValueError):
            return text

    return GrowthPriorityView(
        key=key,
        title=data.get("title", key),
        why=_fmt(data.get("why", "")),
        success_signal=data.get("success_signal", ""),
        stop_doing=data.get("stop_doing", ""),
        week_1_actions=list(data.get("week_1_actions", [])),
        week_2_actions=list(data.get("week_2_actions", [])),
        practice_prompt=data.get("practice_prompt", ""),
    )


def build_growth_plan(
    *,
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    catalogs: ReportLabelCatalogs,
    prompt_coach: "PromptCoachView | None" = None,
    growth_trajectory: "GrowthTrajectoryView | None" = None,
) -> GrowthPlanView:
    i18n = catalogs.growth_plan
    priorities_data = i18n.get("priorities", {})
    prompt_dims_data = i18n.get("prompt_dimensions", {})
    priority_aliases = {
        "verification_gap": "delivery_closure",
        "closure_gap": "delivery_closure",
        "debug_recovery_gap": "adaptive_recovery",
        "framing_gap": "collaboration_framing",
        "scope_control_gap": "collaboration_framing",
        "code_penetration_gap": "implementation_depth",
        "workflow_composition_gap": "execution_driving",
        "agentic_system": "agentic_system",
        "friction": "adaptive_recovery",
    }
    top_deficit_keys = tuple(
        item.category
        for item in (prompt_coach.top_deficits if prompt_coach else [])
        if item.category
    )
    selected_keys = select_growth_priority_keys(
        stats,
        capability_scores,
        limit=2,
        trend_axis_keys=_trend_axis_keys(growth_trajectory),
        regression_axis_keys=_regression_axis_keys(growth_trajectory),
        weakest_prompt_dimension=_weakest_prompt_dimension(prompt_coach),
        top_deficit_keys=top_deficit_keys,
    )

    priorities = [
        _build_priority_view(
            key=key,
            stats=stats,
            capability_scores=capability_scores,
            prompt_coach=prompt_coach,
            growth_trajectory=growth_trajectory,
            priorities_data=priorities_data,
            prompt_dims_data=prompt_dims_data,
            priority_aliases=priority_aliases,
        )
        for key in selected_keys
    ]
    _dedupe_action_contracts_across_priorities(priorities)
    _dedupe_practice_prompts_across_priorities(priorities)
    _link_friction_synthesis_ids(priorities, prompt_coach)

    headline = i18n.get("headline", "")
    next_focus = priorities[0].title if priorities else ""
    return GrowthPlanView(
        headline=headline,
        next_focus=next_focus,
        priorities=priorities,
    )


def _build_priority_view(
    *,
    key: str,
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    prompt_coach: "PromptCoachView | None",
    growth_trajectory: "GrowthTrajectoryView | None",
    priorities_data: dict[str, Any],
    prompt_dims_data: dict[str, Any],
    priority_aliases: dict[str, str],
) -> GrowthPriorityView:
    if key.startswith("prompt:"):
        prompt_key = key.split(":", 1)[1]
        payload = prompt_dims_data.get(prompt_key, prompt_dims_data.get("request_specificity", {}))
        view = _priority_from_yaml(key, payload, score=(stats.pq_avg_dimensions or {}).get(prompt_key, 0.0))
    else:
        payload = priorities_data.get(priority_aliases.get(key, key), priorities_data.get("consolidation", {}))
        view = _priority_from_yaml(key, payload)

    linked_deficits = _linked_deficits(key, prompt_coach)
    linked_templates = _linked_templates(key, prompt_coach)
    linked_rewrites = _linked_rewrites(key, prompt_coach)
    linked_growth_trends = _linked_growth_trends(key, growth_trajectory)
    linked_closure_ids = _linked_closure_guidance_ids(key, prompt_coach)
    evidence_refs = _priority_evidence_refs(key, prompt_coach, growth_trajectory)
    why = _priority_why(view.why, key, linked_deficits, evidence_refs, prompt_coach)
    practice_prompt = _priority_prompt(view.practice_prompt, linked_rewrites, linked_templates, prompt_coach)
    week_1_actions, week_2_actions = _priority_actions(view, linked_deficits, key, prompt_coach)
    return GrowthPriorityView(
        key=view.key,
        title=_priority_title(view.title, key, linked_deficits),
        why=why,
        success_signal=view.success_signal,
        stop_doing=view.stop_doing,
        week_1_actions=week_1_actions,
        week_2_actions=week_2_actions,
        practice_prompt=practice_prompt,
        id=f"priority:{key.replace(':', '_')}",
        evidence_refs=evidence_refs,
        linked_prompt_deficit_ids=[item.id for item in linked_deficits],
        linked_template_ids=[item.id for item in linked_templates],
        linked_rewrite_card_ids=[item.id for item in linked_rewrites],
        linked_growth_trend_refs=linked_growth_trends,
        linked_closure_guidance_ids=linked_closure_ids,
        action_contract=_priority_action_contract(key, stats, linked_deficits, prompt_coach, capability_scores),
    )


def _deficit_keys_from_refs(refs: list[str]) -> set[str]:
    keys: set[str] = set()
    for ref in refs:
        if ref.startswith("deficit:"):
            keys.add(ref.split(":", 1)[1].replace("_", "-"))
    return keys


def _deficit_keys_from_ids(ids: list[str]) -> set[str]:
    return _deficit_keys_from_refs(ids)


def _dedupe_action_contracts_across_priorities(
    priorities: list[GrowthPriorityView],
) -> None:
    """Drop action-contract lines that already appeared in an earlier priority.

    Shared deficits (e.g. vague-request belongs to both collaboration_framing and
    execution_driving) and the generic synthesis line could otherwise render the
    same contract in multiple training blocks, which reads as "every contract is
    the same" to the user.
    """
    seen: set[str] = set()
    for priority in priorities:
        kept: list[str] = []
        for line in priority.action_contract:
            if line in seen:
                continue
            seen.add(line)
            kept.append(line)
        priority.action_contract = kept


def _dedupe_practice_prompts_across_priorities(
    priorities: list[GrowthPriorityView],
) -> None:
    """Avoid rendering repeated or ungrounded examples in training blocks."""
    seen: set[str] = set()
    for priority in priorities:
        prompt = (priority.practice_prompt or "").strip()
        if not prompt:
            continue
        if _looks_like_placeholder_practice_prompt(prompt):
            priority.practice_prompt = ""
            continue
        if prompt in seen:
            priority.practice_prompt = ""
            continue
        seen.add(prompt)


def _looks_like_placeholder_practice_prompt(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    placeholder_tokens = (
        "<你要完成什么>",
        "<现状/报错/背景>",
        "<路径1, 路径2>",
        "<不允许改什么>",
        "<如何算完成>",
        "[问题]",
        "[路径]",
        "[issue]",
        "[paths]",
    )
    return any(token in stripped for token in placeholder_tokens)


def _link_friction_synthesis_ids(
    priorities: list[GrowthPriorityView],
    prompt_coach: "PromptCoachView | None",
) -> None:
    if not priorities or prompt_coach is None or not prompt_coach.friction_synthesis:
        return
    friction_items = prompt_coach.friction_synthesis
    first_friction_id = friction_items[0].id
    for index, priority in enumerate(priorities):
        priority_keys = _deficit_keys_from_ids(priority.linked_prompt_deficit_ids)
        linked: list[str] = []
        for item in friction_items:
            if priority_keys & _deficit_keys_from_refs(item.evidence_refs):
                linked.append(item.id)
        if linked:
            priority.linked_friction_synthesis_ids = linked[:2]
        elif index == 0:
            priority.linked_friction_synthesis_ids = [first_friction_id]


def _weakest_prompt_dimension(prompt_coach: "PromptCoachView | None") -> str:
    if prompt_coach is None or not prompt_coach.top_deficits:
        return ""
    return _PROMPT_DIMENSION_BY_DEFICIT.get(prompt_coach.top_deficits[0].category, "")


def _trend_axis_keys(growth_trajectory: "GrowthTrajectoryView | None") -> tuple[str, ...]:
    if growth_trajectory is None or growth_trajectory.trend is None:
        return ()
    low_axes = [
        series.key
        for series in growth_trajectory.trend.axis_series
        if series.latest_value <= 60 or series.latest_delta <= -3
    ]
    return tuple(low_axes[:2])


def _regression_axis_keys(growth_trajectory: "GrowthTrajectoryView | None") -> tuple[str, ...]:
    if growth_trajectory is None:
        return ()
    latest = growth_trajectory.data.get("latest_vs_previous", {}) if isinstance(growth_trajectory.data, dict) else {}
    regression = latest.get("largest_regression", {}) if isinstance(latest, dict) else {}
    key = str(regression.get("key", "")).strip()
    return (key,) if key else ()


def _linked_deficits(key: str, prompt_coach: "PromptCoachView | None"):
    if prompt_coach is None:
        return []
    if key.startswith("prompt:"):
        prompt_key = key.split(":", 1)[1]
        return [
            item
            for item in prompt_coach.top_deficits
            if _PROMPT_DIMENSION_BY_DEFICIT.get(item.category, "") == prompt_key
        ][:2]
    expected = _DEFICIT_FAMILY_MAP.get(key, set())
    return [item for item in prompt_coach.top_deficits if item.category in expected][:2]


def _linked_templates(key: str, prompt_coach: "PromptCoachView | None"):
    return []


def _linked_rewrites(key: str, prompt_coach: "PromptCoachView | None"):
    if prompt_coach is None:
        return []
    if key.startswith("prompt:"):
        prompt_key = key.split(":", 1)[1]
        rows = [item for item in prompt_coach.rewrite_cards if item.category == prompt_key]
        if rows:
            return rows[:2]
    return prompt_coach.rewrite_cards[:1]


def _linked_growth_trends(key: str, growth_trajectory: "GrowthTrajectoryView | None") -> list[str]:
    refs: list[str] = []
    if growth_trajectory is None:
        return refs
    trend = growth_trajectory.trend
    if trend is not None and trend.summary_code:
        refs.append(f"trend:summary:{trend.summary_code}")
    latest = growth_trajectory.data.get("latest_vs_previous", {}) if isinstance(growth_trajectory.data, dict) else {}
    regression = latest.get("largest_regression", {}) if isinstance(latest, dict) else {}
    regression_key = str(regression.get("key", "")).strip()
    if regression_key:
        refs.append(f"latest_regression:{regression_key}")
    for axis_key in _trend_axis_keys(growth_trajectory):
        refs.append(f"trend:axis:{axis_key}")
    if key.startswith("prompt:"):
        prompt_key = key.split(":", 1)[1]
        refs.append(f"trend:prompt:{prompt_key}")
    elif key:
        refs.append(f"trend:focus:{key}")
    deduped: list[str] = []
    for item in refs:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def _linked_closure_guidance_ids(key: str, prompt_coach: "PromptCoachView | None") -> list[str]:
    if prompt_coach is None or prompt_coach.closure_guidance is None:
        return []
    if key in {"delivery_closure", "adaptive_recovery"} or key.startswith("prompt:"):
        return [prompt_coach.closure_guidance.id]
    return []


def _priority_evidence_refs(
    key: str,
    prompt_coach: "PromptCoachView | None",
    growth_trajectory: "GrowthTrajectoryView | None",
) -> list[str]:
    refs: list[str] = []
    for deficit in _linked_deficits(key, prompt_coach):
        refs.extend(deficit.evidence_refs[:2])
    if growth_trajectory and isinstance(growth_trajectory.data, dict):
        latest = growth_trajectory.data.get("latest_vs_previous", {}) or {}
        if isinstance(latest, dict):
            refs.extend(list(latest.get("evidence_refs", [])[:2]))
    deduped: list[str] = []
    for item in refs:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:4]


def _priority_why(
    base_why: str,
    key: str,
    linked_deficits,
    evidence_refs: list[str],
    prompt_coach: "PromptCoachView | None",
) -> str:
    if base_why:
        return base_why
    if linked_deficits:
        lead = linked_deficits[0]
        return f"这个训练直接来自你本期的「{lead.label}」问题。先把提需求方式修正，能最快减少 AI 跑偏和返工。"
    if prompt_coach and prompt_coach.prompt_style and key.startswith("prompt:"):
        return f"这项训练会接住你当前的「{prompt_coach.prompt_style.label}」提需求方式，帮助你把方法资产和本次任务变量接稳。"
    if prompt_coach and prompt_coach.closure_guidance and key == "delivery_closure":
        return prompt_coach.closure_guidance.coaching_message
    if evidence_refs:
        return f"这项训练优先级靠前，因为最近的轨迹和本期变化都把问题指向了「{key}」。"
    return f"这项训练用于稳住「{key}」这条能力，避免下一阶段继续波动。"


def _priority_prompt(
    base_prompt: str,
    linked_rewrites,
    linked_templates,
    prompt_coach: "PromptCoachView | None",
) -> str:
    if prompt_coach and prompt_coach.prompt_style and prompt_coach.prompt_style.suggested_next_prompt and (
        prompt_coach.prompt_style.type in {"indexed_prompt", "mixed_prompt"}
    ):
        candidate = prompt_coach.prompt_style.suggested_next_prompt
        return "" if _looks_like_placeholder_practice_prompt(candidate) else candidate
    for item in linked_rewrites:
        if item.better_prompt:
            return "" if _looks_like_placeholder_practice_prompt(item.better_prompt) else item.better_prompt
    return "" if _looks_like_placeholder_practice_prompt(base_prompt) else base_prompt


def _priority_actions(
    view: GrowthPriorityView,
    linked_deficits,
    key: str,
    prompt_coach: "PromptCoachView | None",
) -> tuple[list[str], list[str]]:
    week_1 = list(view.week_1_actions)
    week_2 = list(view.week_2_actions)
    if linked_deficits:
        week_1 = week_1 or [f"这周每次发给 AI 前，先检查「{linked_deficits[0].label}」相关缺口。"]
        week_2 = week_2 or [f"下周开始要求 AI 先复述边界，再执行与「{linked_deficits[0].label}」相关的任务。"]
    elif key == "delivery_closure":
        missing = prompt_coach.closure_guidance.missing_closure_methods if prompt_coach and prompt_coach.closure_guidance else []
        week_1 = week_1 or [f"这周每次结束前，都补 1 个收口动作：{missing[0] if missing else '验收清单'}。"]
        week_2 = week_2 or ["下周开始让 AI 先复述收口方式，再进入执行。"]
    return week_1, week_2


def _priority_action_contract(
    key: str,
    stats: GrowthProfile,
    linked_deficits,
    prompt_coach: "PromptCoachView | None",
    capability_scores: dict[str, float] | None = None,
) -> list[str]:
    from ..domain.growth.action_contracts import (
        generate_action_contracts,
        action_contract_to_lines,
    )

    # Each priority key only shows contracts whose deficits belong to its own domain.
    # This prevents every training item from rendering the same global top-5 deficits.
    # None  → no filtering (show all); set() → no deficit contracts (strength axis).
    _KEY_DEFICIT_SCOPE: dict[str, set[str]] = {
        "delivery_closure": {"missing-acceptance-criteria"},
        "collaboration_framing": {"missing-context", "vague-request", "assumption-not-surfaced", "late-constraint"},
        "adaptive_recovery": {"unclear-correction", "scope-drift"},
        "execution_driving": {"vague-request", "scope-drift"},
        "implementation_depth": set(),  # strength axis — no deficit-driven contracts
        "prompt:context_provision": {"missing-context", "late-constraint"},
        "prompt:request_specificity": {"vague-request", "assumption-not-surfaced"},
        "prompt:scope_management": {"scope-drift"},
        "prompt:correction_quality": {"unclear-correction"},
        "prompt:information_timing": {"late-constraint"},
        "agentic_system": set(),
        "friction": {"unclear-correction", "scope-drift"},
    }
    # Normalize gap-alias / fallback keys to their canonical axis before scope
    # lookup; otherwise an unknown key (e.g. code_penetration_gap, consolidation)
    # returns None and leaks the global deficit contracts into every section.
    _SCOPE_KEY_ALIASES: dict[str, str] = {
        "verification_gap": "delivery_closure",
        "closure_gap": "delivery_closure",
        "debug_recovery_gap": "adaptive_recovery",
        "framing_gap": "collaboration_framing",
        "scope_control_gap": "collaboration_framing",
        "code_penetration_gap": "implementation_depth",
        "workflow_composition_gap": "execution_driving",
        "friction": "friction",
        "consolidation": "implementation_depth",  # fallback: treat as strength → no deficit contracts
    }
    scope_key = _SCOPE_KEY_ALIASES.get(key, key)
    focus_deficit_keys: set[str] | None = _KEY_DEFICIT_SCOPE.get(scope_key, set())

    cap_scores = capability_scores or {}
    contract_report = generate_action_contracts(
        stats,
        cap_scores,
        diagnosis_code=key if key in {"agentic_system", "delivery_closure"} else "",
        focus_deficit_keys=focus_deficit_keys,
        priority_key=key,
        max_items=5,
    )
    lines = action_contract_to_lines(contract_report)

    has_friction_synthesis = bool(prompt_coach and prompt_coach.friction_synthesis)
    high_human_intervention = (getattr(stats, "human_intervention_session_rate", 0.0) or 0.0) >= 0.2
    if (has_friction_synthesis or high_human_intervention) and len(lines) < 6:
        lines.append("纠偏沉淀：把本期最高频的人类补规则点转成下次自动触发的 rule / checklist。")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in lines:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:6]

def _priority_title(title: str, key: str, linked_deficits) -> str:
    if linked_deficits and linked_deficits[0].category == "missing-acceptance-criteria":
        return "把“我要你优化”改成“什么结果算通过”"
    if linked_deficits and linked_deficits[0].category in {"missing-context", "vague-request"}:
        return "协作框定训练"
    return title or key
