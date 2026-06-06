"""Growth mirror session-reading models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum

from ..cache_schema import SESSION_READ_SCHEMA_VERSION

@dataclass
class ResistanceSignal:
    """A single resistance signal observed in a session."""
    category: str = ""              # canonical or kebab-case novel
    attribution: str = ""           # user-actionable | ai-capability | environmental
    description: str = ""           # neutral one-sentence gap description
    severity: str = "medium"        # low | medium | high
    confidence: int = 70            # 0-100


@dataclass
class MomentumSignal:
    """A productive signal worth amplifying."""
    category: str = ""              # canonical or kebab-case novel
    driver: str = ""                # user-driven | ai-driven | collaborative
    label: str = ""                 # short title shown in UI
    description: str = ""
    confidence: int = 70


@dataclass
class PromptLensFinding:
    """A specific prompt moment that helped or hurt execution quality."""
    category: str = ""              # one of 10 PQ categories
    type: str = "deficit"           # deficit | strength
    description: str = ""           # neutral sentence: what happened
    message_ref: str = ""           # e.g. "User#5"; "" if multi-message
    impact: str = "low"             # low | medium | high
    confidence: int = 70
    suggested_improvement: str = ""  # only meaningful for deficits


@dataclass
class PromptLensTakeaway:
    """A concrete lesson extracted from prompt behavior."""
    type: str = "improve"           # improve | reinforce
    category: str = ""              # one of 10 PQ categories
    label: str = ""                 # short title shown in UI
    message_ref: str = ""           # e.g. "User#3"
    # improve fields:
    original: str = ""              # user's actual message (verbatim)
    better_prompt: str = ""         # concrete rewrite incorporating fix
    why: str = ""                   # one-sentence rationale
    # reinforce fields:
    what_worked: str = ""           # what the user did well
    why_effective: str = ""         # why it produced a good outcome


@dataclass
class PromptLensScores:
    """Session-level prompt lens assessment."""
    source: str = "heuristic"        # llm | heuristic
    coverage: str = "full"           # full | light
    evaluation_status: str = "insufficient_input"  # llm_evaluated | insufficient_input | llm_failed | llm_unavailable | not_applicable
    evaluated_user_messages: int = 0
    # 5 dimensions, each 0-100.
    context_provision: int = 50
    request_specificity: int = 50
    scope_management: int = 50
    information_timing: int = 50
    correction_quality: int = 50
    # Single composite 0-100.
    efficiency_score: int = 50
    # Up to 8 findings + 4 takeaways per session (rule enforced by parser).
    findings: list[PromptLensFinding] = field(default_factory=list)
    takeaways: list[PromptLensTakeaway] = field(default_factory=list)


# ── Capability focus taxonomy ────────────────────────────────────────────────

class CapabilityFocus(StrEnum):
    """How the session invested in reusable AI capability work."""
    NONE              = "none"
    WORKFLOW_BUILDER  = "workflow_builder"
    TOOLING_AUTHOR    = "tooling_author"
    AUTOMATION_AUTHOR = "automation_author"
    PRODUCT_BUILDER   = "product_builder"
    PROMPT_CRAFTER    = "prompt_crafter"

CAPABILITY_FOCUS_AREAS = tuple(CapabilityFocus)


class CapabilityDepth(StrEnum):
    INCIDENTAL  = "incidental"
    MODERATE    = "moderate"
    SUBSTANTIAL = "substantial"

CAPABILITY_DEPTH_LEVELS = tuple(CapabilityDepth)

class WorkStyle(StrEnum):
    """How the work progressed through the session."""
    FREEFORM      = "freeform"
    EXPLORATORY   = "exploratory"
    PLAN_DRIVEN   = "plan_driven"
    SPEC_DRIVEN   = "spec_driven"
    TDD           = "tdd"
    ADAPTIVE      = "adaptive"
    METHOD_GUIDED = "method_guided"

WORK_STYLE_VALUES = tuple(WorkStyle)


@dataclass
class SessionRead:
    """Structured semantic reading for one collaboration session."""
    SCHEMA_VERSION: str = field(default=SESSION_READ_SCHEMA_VERSION, init=False, repr=False)

    session_id: str = ""
    tool_name: str = ""

    # Content revision stamp when the session read was extracted (see
    # SessionRef.source_mtime). Cache invalidates only when the session's stamp
    # advances; there is no time-based TTL. 0.0 = unstamped entry (still valid
    # until rewritten or schema bump).
    _source_mtime: float = 0.0
    # Locale stamped on new extractions ("zh" | "en"). Empty = unstamped locale.
    _report_language: str = ""

    work_summary: str = ""
    work_intent_mix: dict[str, int] = field(default_factory=dict)
    delivery_outcome: str = "unclear"      # fully_achieved | mostly_achieved | partially_achieved | ongoing | unclear
    user_readback: dict[str, int] = field(default_factory=dict)
    support_value: str = "helpful"  # very_helpful | helpful | mixed | unhelpful
    collaboration_shape: str = "single_task"
    resistance_signals: list[ResistanceSignal] = field(default_factory=list)
    momentum_signals: list[MomentumSignal] = field(default_factory=list)
    resistance_summary: str = ""
    key_gain: str = ""
    session_takeaway: str = ""
    confidence: str = "high"      # high | medium | low (low for Gemini w/o tool data)
    prompt_lens: PromptLensScores | None = None
    capability_focus: str = "none"          # one of CAPABILITY_FOCUS_AREAS
    capability_depth: str = "incidental"    # one of CAPABILITY_DEPTH_LEVELS
    work_style: str = "freeform"            # one of WORK_STYLE_VALUES
    active_clarification: bool = False

    # When LLM extraction failed (rate-limit retry exhausted, JSON parse failed,
    # …) we return a stub read so the run doesn't abort, but ALL its fields are
    # dataclass defaults — they don't represent the session's real completion /
    # asset-creation / collaboration pattern. Aggregator must exclude these from
    # scoring statistics so a 429 storm doesn't drag the user's score to 0. Not
    # persisted (failed extractions don't cache), so this stays runtime-only.
    extraction_failed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["SCHEMA_VERSION"] = self.SCHEMA_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRead":
        d = {k: v for k, v in d.items() if k != "SCHEMA_VERSION"}
        d["resistance_signals"] = [
            ResistanceSignal(**fp) if isinstance(fp, dict) else fp
            for fp in d.get("resistance_signals", [])
        ]
        d["momentum_signals"] = [
            MomentumSignal(**ep) if isinstance(ep, dict) else ep
            for ep in d.get("momentum_signals", [])
        ]
        pq = d.get("prompt_lens")
        if isinstance(pq, dict):
            lens_findings = [
                PromptLensFinding(**f) if isinstance(f, dict) else f
                for f in pq.get("findings", [])
            ]
            lens_takeaways = [
                PromptLensTakeaway(**t) if isinstance(t, dict) else t
                for t in pq.get("takeaways", [])
            ]
            pq_kwargs = {k: v for k, v in pq.items() if k not in {"findings", "takeaways"}}
            d["prompt_lens"] = PromptLensScores(
                findings=lens_findings, takeaways=lens_takeaways, **pq_kwargs
            )
        if d.get("capability_focus") not in CAPABILITY_FOCUS_AREAS:
            d["capability_focus"] = "none"
        if d.get("capability_depth") not in CAPABILITY_DEPTH_LEVELS:
            d["capability_depth"] = "incidental"
        if d.get("work_style") not in WORK_STYLE_VALUES:
            d["work_style"] = "freeform"
        if "active_clarification" not in d:
            d["active_clarification"] = False
        return cls(**d)


