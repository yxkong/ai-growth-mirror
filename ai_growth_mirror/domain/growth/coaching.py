"""Domain contracts for personalized growth coaching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import GrowthProfile

from .diagnosis import DiagnosisResult
from .planning import select_growth_priority_keys


@dataclass
class AxisDiagnosis:
    axis_key: str = ""
    label: str = ""
    explanation: str = ""
    confidence: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    next_action: str = ""


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
    action_contract: str = ""
    evidence_refs: list[str] = field(default_factory=list)


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
    axis_diagnosis: list[AxisDiagnosis] = field(default_factory=list)
    framing_evidence_headline: str = ""
    framing_evidence_summary: str = ""
    framing_evidence_takeaways: list[CoachingTakeaway] = field(default_factory=list)
    friction_synthesis: list[FrictionSynthesisItem] = field(default_factory=list)
    share_lines: list[str] = field(default_factory=list)
    source: str = "llm"
    # Stage-2 diagnosis result (None when coaching was rule-based only)
    diagnosis: DiagnosisResult | None = None


def priority_keys_for_coaching(
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
) -> list[str]:
    """Select the top personalized coaching tracks from profile evidence."""
    keys = select_growth_priority_keys(stats, capability_scores, limit=3)
    return keys or ["adaptive_recovery"]


def parse_coaching_payload(raw: dict) -> CoachingContent:
    """Convert structured prompt output into the stable coaching contract."""

    training_plan = raw.get("training_plan", {})
    if not isinstance(training_plan, dict):
        training_plan = {}

    framing_evidence = raw.get("framing_evidence", {})
    if not isinstance(framing_evidence, dict):
        framing_evidence = {}

    raw_axis_diagnosis = raw.get("axis_diagnosis", [])
    if not isinstance(raw_axis_diagnosis, list):
        raw_axis_diagnosis = []

    priorities = [
        CoachingPriority(
            key=item.get("key", ""),
            title=item.get("title", ""),
            why=item.get("why", ""),
            success_signal=item.get("success_signal", ""),
            stop_doing=item.get("stop_doing", ""),
            week_1_actions=[
                action for action in item.get("week_1_actions", []) if isinstance(action, str)
            ],
            week_2_actions=[
                action for action in item.get("week_2_actions", []) if isinstance(action, str)
            ],
            practice_prompt=item.get("practice_prompt", ""),
            action_contract=item.get("action_contract", ""),
            evidence_refs=[
                ref for ref in item.get("evidence_refs", []) if isinstance(ref, str) and ref.strip()
            ],
        )
        for item in training_plan.get("priorities", [])[:3]
        if isinstance(item, dict)
    ]

    axis_diagnosis = [
        AxisDiagnosis(
            axis_key=item.get("axis_key", ""),
            label=item.get("label", ""),
            explanation=item.get("explanation", ""),
            confidence=int(item.get("confidence", 0) or 0),
            evidence_refs=[
                ref for ref in item.get("evidence_refs", []) if isinstance(ref, str) and ref.strip()
            ],
            next_action=item.get("next_action", ""),
        )
        for item in raw_axis_diagnosis
        if isinstance(item, dict)
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
        for item in framing_evidence.get("takeaways", [])[:3]
        if isinstance(item, dict)
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
        for index, item in enumerate(framing_evidence.get("friction_synthesis", [])[:2])
        if isinstance(item, dict)
    ]

    # Stage-2 grounded diagnosis
    from .diagnosis import parse_diagnosis_payload, rerank_diagnosis_result, DiagnosisCandidatePacket

    diagnosis: DiagnosisResult | None = None
    raw_diagnosis = raw.get("diagnosis")
    if isinstance(raw_diagnosis, dict):
        parsed = parse_diagnosis_payload(raw_diagnosis)
        diagnosis = rerank_diagnosis_result(parsed, DiagnosisCandidatePacket())

    return CoachingContent(
        growth_headline=training_plan.get("headline", ""),
        priorities=priorities,
        axis_diagnosis=axis_diagnosis,
        framing_evidence_headline=framing_evidence.get("headline", ""),
        framing_evidence_summary=framing_evidence.get("evidence_summary", ""),
        framing_evidence_takeaways=takeaways,
        friction_synthesis=friction_synthesis,
        share_lines=[
            line for line in raw.get("share_lines", [])[:3] if isinstance(line, str)
        ],
        source="llm",
        diagnosis=diagnosis,
    )
