"""Application-owned personal growth plan assembly."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.growth.model import GrowthProfile
from ..domain.growth.planning import select_growth_priority_keys
from .label_catalogs import ReportLabelCatalogs


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


@dataclass
class GrowthPlanView:
    headline: str
    next_focus: str
    priorities: list[GrowthPriorityView] = field(default_factory=list)


def _priority_from_yaml(key: str, data: dict, **fmt: Any) -> GrowthPriorityView:
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
        week_1_actions=data.get("week_1_actions", []),
        week_2_actions=data.get("week_2_actions", []),
        practice_prompt=data.get("practice_prompt", ""),
    )


def build_growth_plan(
    *,
    stats: GrowthProfile,
    capability_scores: dict[str, float],
    catalogs: ReportLabelCatalogs,
) -> GrowthPlanView:
    i18n = catalogs.growth_plan
    priorities_data = i18n.get("priorities", {})
    prompt_dims_data = i18n.get("prompt_dimensions", {})
    priority_aliases = {
        "verification_gap": "delivery_closure",
        "closure_gap": "delivery_closure",
        "debug_recovery_gap": "adaptive_recovery",
        "framing_gap": "intent_clarity",
        "scope_control_gap": "intent_clarity",
        "code_penetration_gap": "implementation_depth",
        "workflow_composition_gap": "execution_driving",
    }

    pq_dims = stats.pq_avg_dimensions or {}
    selected_keys = select_growth_priority_keys(stats, capability_scores, limit=2)
    deduped: list[GrowthPriorityView] = []
    for key in selected_keys:
        if key.startswith("prompt:"):
            weakest_pq_key = key.split(":", 1)[1]
            weakest_pq_val = pq_dims.get(weakest_pq_key, 0.0)
            pq_data = prompt_dims_data.get(
                weakest_pq_key,
                prompt_dims_data.get("request_specificity", {}),
            )
            deduped.append(_priority_from_yaml(key, pq_data, score=weakest_pq_val))
            continue

        canonical_key = priority_aliases.get(key, key)
        payload = priorities_data.get(canonical_key, priorities_data.get("consolidation", {}))
        view = _priority_from_yaml(key, payload)
        if not view.title:
            view.title = canonical_key
        deduped.append(view)

    return GrowthPlanView(
        headline=i18n.get("headline", ""),
        next_focus=deduped[0].title if deduped else i18n.get("next_focus_fallback", ""),
        priorities=deduped,
    )
