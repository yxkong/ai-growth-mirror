"""Prompt coach view entities for report surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptCoachDimensionView:
    label: str
    score: float


@dataclass
class PromptCoachSourceSummaryView:
    llm_session_count: int = 0
    heuristic_session_count: int = 0
    light_session_count: int = 0
    evaluated_user_messages: int = 0
    run_mode: str = "llm"
    llm_evaluated_count: int = 0
    insufficient_count: int = 0
    llm_failed_count: int = 0
    llm_unavailable_count: int = 0


@dataclass
class PromptCoachDeficitView:
    id: str
    category: str
    label: str
    description: str
    impact: str
    confidence: str
    evidence_refs: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class PromptCoachRewriteCardView:
    id: str
    scene: str
    original: str
    problem: str
    better_prompt: str
    why: str
    category: str
    confidence: str
    evidence_refs: list[str] = field(default_factory=list)
    source_note: str = ""


@dataclass
class PromptCoachPromptStyleView:
    type: str
    label: str
    evidence: list[str] = field(default_factory=list)
    coaching_message: str = ""
    suggested_next_prompt: str = ""
    trigger_maturity: list[str] = field(default_factory=list)


@dataclass
class PromptCoachClosureGuidanceView:
    id: str
    task_type: str
    label: str
    mode: str = "engineered"
    expected_closure_methods: list[str] = field(default_factory=list)
    missing_closure_methods: list[str] = field(default_factory=list)
    coaching_message: str = ""


@dataclass
class PromptCoachFrictionSynthesisView:
    id: str
    label: str
    explanation: str
    next_action: str
    confidence: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    generated_by: str = "rule"


@dataclass
class PromptCoachView:
    available: bool
    headline: str
    strongest_label: str
    weakest_label: str
    evidence_summary: str
    strength_habit: str
    source_note: str = ""
    weak_dimensions: list[str] = field(default_factory=list)
    deficits: list[str] = field(default_factory=list)
    dimension_scores: list[PromptCoachDimensionView] = field(default_factory=list)
    source_summary: PromptCoachSourceSummaryView = field(default_factory=PromptCoachSourceSummaryView)
    top_deficits: list[PromptCoachDeficitView] = field(default_factory=list)
    rewrite_cards: list[PromptCoachRewriteCardView] = field(default_factory=list)
    prompt_style: Optional[PromptCoachPromptStyleView] = None
    closure_guidance: Optional[PromptCoachClosureGuidanceView] = None
    friction_synthesis: list[PromptCoachFrictionSynthesisView] = field(default_factory=list)
    light_state_note: str = ""
