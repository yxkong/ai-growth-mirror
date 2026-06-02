"""Domain contracts for personalized growth coaching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import GrowthProfile

from .planning import select_growth_priority_keys


@dataclass
class CoachingPriority:
    key: str
    title: str
    why: str
    success_signal: str = ""
    stop_doing: str = ""
    week_1_actions: list[str] = field(default_factory=list)
    week_2_actions: list[str] = field(default_factory=list)
    practice_prompt: str = ""


@dataclass
class CoachingTakeaway:
    label: str
    kind: str
    evidence: str
    message: str
    action: str
    better_prompt: str = ""


@dataclass
class FrictionSynthesisItem:
    id: str = ""
    label: str = ""
    explanation: str = ""
    next_action: str = ""
    confidence: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    generated_by: str = "llm"


@dataclass
class CoachingContent:
    """Personalized coaching content generated from structured evidence."""

    growth_headline: str = ""
    priorities: list[CoachingPriority] = field(default_factory=list)
    prompt_coach_headline: str = ""
    prompt_coach_evidence: str = ""
    prompt_coach_takeaways: list[CoachingTakeaway] = field(default_factory=list)
    friction_synthesis: list[FrictionSynthesisItem] = field(default_factory=list)
    share_lines: list[str] = field(default_factory=list)
    source: str = "llm"


def priority_keys_for_coaching(
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
) -> list[str]:
    """Select the top personalized coaching tracks from profile evidence."""
    keys = select_growth_priority_keys(stats, capability_scores, limit=3)
    return keys or ["adaptive_recovery"]


def parse_coaching_payload(raw: dict) -> CoachingContent:
    """Convert structured prompt output into the stable coaching contract."""

    growth_plan = raw.get("growth_plan", {})
    prompt_coach = raw.get("prompt_coach", {})

    priorities = [
        CoachingPriority(
            key=item.get("key", ""),
            title=item.get("title", ""),
            why=item.get("why", ""),
            success_signal=item.get("success_signal", ""),
            stop_doing=item.get("stop_doing", ""),
            week_1_actions=item.get("week_1_actions", []),
            week_2_actions=item.get("week_2_actions", []),
            practice_prompt=item.get("practice_prompt", ""),
        )
        for item in growth_plan.get("priorities", [])[:3]
    ]

    takeaways = [
        CoachingTakeaway(
            label=item.get("label", ""),
            kind=item.get("kind", ""),
            evidence=item.get("evidence", ""),
            message=item.get("message", ""),
            action=item.get("action", ""),
            better_prompt=item.get("better_prompt", ""),
        )
        for item in prompt_coach.get("takeaways", [])[:3]
    ]

    friction_synthesis = [
        FrictionSynthesisItem(
            id=f"friction:llm:{index}",
            label=item.get("label", ""),
            explanation=item.get("explanation", ""),
            next_action=item.get("next_action", ""),
            confidence=int(item.get("confidence", 0) or 0),
            evidence_refs=[
                ref
                for ref in item.get("evidence_refs", [])
                if isinstance(ref, str) and ref.strip()
            ],
            generated_by="llm",
        )
        for index, item in enumerate(prompt_coach.get("friction_synthesis", [])[:2])
    ]

    return CoachingContent(
        growth_headline=growth_plan.get("headline", ""),
        priorities=priorities,
        prompt_coach_headline=prompt_coach.get("headline", ""),
        prompt_coach_evidence=prompt_coach.get("evidence_summary", ""),
        prompt_coach_takeaways=takeaways,
        friction_synthesis=friction_synthesis,
        share_lines=raw.get("share_lines", [])[:3],
        source="llm",
    )
