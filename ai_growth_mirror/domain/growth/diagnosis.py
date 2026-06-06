"""Three-stage LLM diagnosis layer.

Stage 1 – Rule layer: produces ranked DiagnosisCandidate list from signals.
Stage 2 – LLM grounded synthesis: receives structured evidence packet, emits
           DiagnosisResult with evidence_refs + confidence + why_not_other.
Stage 3 – Rule layer ordering: re-ranks LLM output by actionability and impact.

Domain contracts only — no I/O, no LLM calls, no application imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import GrowthProfile
    from .planning import RankedPriority


# ---------------------------------------------------------------------------
# Stage-1 contracts: Rule layer candidate packet
# ---------------------------------------------------------------------------

KNOWN_DIAGNOSIS_CODES = frozenset(
    {
        "acceptance_criteria_late",
        "private_framework_under_recognized",
        "schema_mismatch",
        "workflow_used_but_not_routed",
        "human_policy_added_after_first_output",
        "missing_context_pattern",
        "vague_request_pattern",
        "scope_drift_pattern",
        "correction_quality_deficit",
        "agentic_system_gap",
        "trend_stall",
        "latest_regression",
        "delivery_closure_gap",
        "implementation_depth_gap",
        "intent_clarity_gap",
        "execution_driving_gap",
        "adaptive_recovery_gap",
        "human_cost_high",
    }
)


@dataclass
class DiagnosisCandidate:
    """A single rule-layer candidate diagnosis with structured evidence."""

    code: str
    urgency: float
    reason_codes: tuple[str, ...] = ()
    axis_key: str = ""
    current_score: float = 0.0
    threshold_score: float = 0.0
    evidence_snippets: list[str] = field(default_factory=list)

    @property
    def gap(self) -> float:
        return max(0.0, self.threshold_score - self.current_score)


@dataclass
class DiagnosisCandidatePacket:
    """Structured input packet for Stage-2 LLM synthesis.

    Contains the top-N rule candidates with full evidence, plus cross-cutting
    signals that help the LLM choose the primary diagnosis and explain why it
    rejected the alternatives.
    """

    candidates: list[DiagnosisCandidate] = field(default_factory=list)
    # Cross-cutting signals
    human_intervention_rate: float = 0.0
    agentic_system_score: float = 0.0
    top_deficit_counts: dict[str, int] = field(default_factory=dict)
    trend_info: str = ""
    schema_mismatch: bool = False
    session_count: int = 0
    # Free-text snippets from real session evidence
    recent_friction_snippets: list[str] = field(default_factory=list)
    recent_takeaway_snippets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage-2 contracts: LLM grounded synthesis result
# ---------------------------------------------------------------------------


@dataclass
class GroundedDiagnosis:
    """One diagnosis item returned by the LLM, with mandatory evidence."""

    code: str
    label: str
    explanation: str
    confidence: int  # 0-100
    evidence_refs: list[str] = field(default_factory=list)
    why_not_other_diagnosis: str = ""
    next_action: str = ""


@dataclass
class DiagnosisResult:
    """Full Stage-2 LLM output: primary diagnosis + rejected alternatives."""

    primary: GroundedDiagnosis | None = None
    secondary: list[GroundedDiagnosis] = field(default_factory=list)
    synthesis_confidence: str = "low"  # "high" | "medium" | "low"
    source: str = "llm"  # "llm" | "rule_fallback"


# ---------------------------------------------------------------------------
# Stage-3: Rule-layer re-ordering of LLM output
# ---------------------------------------------------------------------------

_L4_L5_IMPACT_CODES = frozenset(
    {
        "acceptance_criteria_late",
        "agentic_system_gap",
        "workflow_used_but_not_routed",
        "private_framework_under_recognized",
        "human_cost_high",
    }
)

_ACTIONABILITY_ORDER = (
    "acceptance_criteria_late",
    "human_policy_added_after_first_output",
    "missing_context_pattern",
    "vague_request_pattern",
    "delivery_closure_gap",
    "correction_quality_deficit",
    "agentic_system_gap",
    "scope_drift_pattern",
    "workflow_used_but_not_routed",
    "intent_clarity_gap",
    "execution_driving_gap",
    "adaptive_recovery_gap",
    "implementation_depth_gap",
    "human_cost_high",
    "private_framework_under_recognized",
    "schema_mismatch",
    "trend_stall",
    "latest_regression",
)


def rerank_diagnosis_result(
    result: DiagnosisResult,
    packet: DiagnosisCandidatePacket,
) -> DiagnosisResult:
    """Stage-3: re-rank secondary diagnoses by actionability and L4/L5 impact.

    The primary diagnosis is kept as-is (LLM judgment respected).
    Secondary items are re-sorted so the most actionable / highest-impact
    diagnosis surfaces first in the report.
    """
    if not result.secondary:
        return result

    def _sort_key(item: GroundedDiagnosis) -> tuple[int, int, int]:
        l4_l5 = 1 if item.code in _L4_L5_IMPACT_CODES else 0
        try:
            action_rank = _ACTIONABILITY_ORDER.index(item.code)
        except ValueError:
            action_rank = len(_ACTIONABILITY_ORDER)
        confidence_rank = -item.confidence
        return (-l4_l5, action_rank, confidence_rank)

    sorted_secondary = sorted(result.secondary, key=_sort_key)
    return DiagnosisResult(
        primary=result.primary,
        secondary=sorted_secondary,
        synthesis_confidence=result.synthesis_confidence,
        source=result.source,
    )


# ---------------------------------------------------------------------------
# Stage-1 builder: produce DiagnosisCandidatePacket from GrowthProfile
# ---------------------------------------------------------------------------


def build_diagnosis_candidate_packet(
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
    ranked_priorities: "list[RankedPriority]",
    *,
    recent_friction_snippets: list[str] | None = None,
    recent_takeaway_snippets: list[str] | None = None,
    trend_info: str = "",
    schema_mismatch: bool = False,
) -> DiagnosisCandidatePacket:
    """Build the structured evidence packet that drives Stage-2 LLM synthesis."""

    candidates: list[DiagnosisCandidate] = []
    seen_codes: set[str] = set()

    pq_deficit_counts = dict(stats.pq_deficit_counts or {})
    pq_dims = dict(stats.pq_avg_dimensions or {})

    # Map rule priority keys → diagnosis codes
    _priority_to_code: dict[str, str] = {
        "delivery_closure": "delivery_closure_gap",
        "implementation_depth": "implementation_depth_gap",
        "adaptive_recovery": "adaptive_recovery_gap",
        "intent_clarity": "intent_clarity_gap",
        "execution_driving": "execution_driving_gap",
        "friction": "correction_quality_deficit",
        "agentic_system": "agentic_system_gap",
        "prompt:context_provision": "missing_context_pattern",
        "prompt:request_specificity": "vague_request_pattern",
        "prompt:scope_management": "scope_drift_pattern",
        "prompt:correction_quality": "correction_quality_deficit",
        "prompt:information_timing": "acceptance_criteria_late",
    }

    for priority in ranked_priorities[:8]:
        code = _priority_to_code.get(priority.key, priority.key)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        axis_key = priority.key.replace("prompt:", "") if priority.key.startswith("prompt:") else priority.key
        current = _resolve_axis_score(
            axis_key,
            stats=stats,
            capability_scores=capability_scores,
            pq_dims=pq_dims,
        )
        threshold = _default_threshold(priority.key)
        snippets = _evidence_snippets_for(code, stats=stats, pq_deficit_counts=pq_deficit_counts)
        candidates.append(
            DiagnosisCandidate(
                code=code,
                urgency=priority.urgency,
                reason_codes=tuple(priority.reason_codes),
                axis_key=axis_key,
                current_score=current,
                threshold_score=threshold,
                evidence_snippets=snippets[:3],
            )
        )

    # Add human-cost signal if rate is high
    human_rate = float(getattr(stats, "human_intervention_session_rate", 0.0) or 0.0)
    if human_rate >= 0.20 and "human_cost_high" not in seen_codes:
        candidates.append(
            DiagnosisCandidate(
                code="human_cost_high",
                urgency=70.0 + human_rate * 100,
                reason_codes=("human_cost_high",),
                evidence_snippets=[
                    f"{round(human_rate * 100)}% of sessions required ≥2 user corrections"
                ],
            )
        )

    # Private framework under-recognition
    local_rate = float(getattr(stats, "local_method_framework_session_rate", 0.0) or 0.0)
    fingerprint_rate = float(getattr(stats, "workflow_fingerprint_session_rate", 0.0) or 0.0)
    if local_rate > 0.10 and fingerprint_rate < 0.05 and "private_framework_under_recognized" not in seen_codes:
        candidates.append(
            DiagnosisCandidate(
                code="private_framework_under_recognized",
                urgency=65.0,
                reason_codes=("private_method_under_recognized",),
                evidence_snippets=[
                    f"local method frameworks used in {round(local_rate * 100)}% of sessions "
                    f"but public fingerprint rate is only {round(fingerprint_rate * 100)}%"
                ],
            )
        )

    top_deficit_counts = {k: v for k, v in sorted(pq_deficit_counts.items(), key=lambda x: -x[1])[:5]}
    recent_friction = recent_friction_snippets or []
    recent_takeaways = recent_takeaway_snippets or []

    return DiagnosisCandidatePacket(
        candidates=candidates[:8],
        human_intervention_rate=human_rate,
        agentic_system_score=float(getattr(stats, "agentic_system_score", 0.0) or 0.0),
        top_deficit_counts=top_deficit_counts,
        trend_info=trend_info,
        schema_mismatch=schema_mismatch,
        session_count=stats.session_count,
        recent_friction_snippets=recent_friction[:5],
        recent_takeaway_snippets=recent_takeaways[:5],
    )


def _resolve_axis_score(
    axis_key: str,
    *,
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
    pq_dims: dict[str, float],
) -> float:
    """Resolve the real current score for a priority axis.

    capability_scores only carries the five radar axes, so agentic_system and
    friction must be sourced explicitly; otherwise the diagnosis gap is computed
    against 0 and every why_not_other_diagnosis comparison is distorted.
    """
    if axis_key == "agentic_system":
        return float(getattr(stats, "agentic_system_score", 0.0) or 0.0)
    if axis_key == "friction":
        # Friction maps to correction quality / adaptive recovery.
        return float(
            pq_dims.get("correction_quality")
            or capability_scores.get("adaptive_recovery")
            or 0.0
        )
    resolved = capability_scores.get(axis_key)
    if resolved is None:
        resolved = pq_dims.get(axis_key, 0.0)
    return float(resolved or 0.0)


def _default_threshold(priority_key: str) -> float:
    _map = {
        "delivery_closure": 62.0,
        "implementation_depth": 58.0,
        "adaptive_recovery": 56.0,
        "intent_clarity": 60.0,
        "execution_driving": 58.0,
        "prompt:context_provision": 65.0,
        "prompt:request_specificity": 65.0,
        "prompt:scope_management": 65.0,
        "prompt:correction_quality": 65.0,
        "prompt:information_timing": 65.0,
        "agentic_system": 75.0,
    }
    return _map.get(priority_key, 60.0)


def _evidence_snippets_for(
    code: str,
    *,
    stats: "GrowthProfile",
    pq_deficit_counts: dict[str, int],
) -> list[str]:
    snippets: list[str] = []
    if code == "delivery_closure_gap":
        rate = round(getattr(stats, "verification_behavior_rate", 0.0) * 100)
        snippets.append(f"verification_behavior_rate={rate}%")
    elif code == "agentic_system_gap":
        score = round(getattr(stats, "agentic_system_score", 0.0))
        local_rate = round(getattr(stats, "local_method_framework_session_rate", 0.0) * 100)
        snippets.append(f"agentic_system_score={score}")
        snippets.append(f"local_method_framework_rate={local_rate}%")
    elif code == "missing_context_pattern":
        count = pq_deficit_counts.get("missing-context", 0)
        snippets.append(f"missing-context deficit in {count} sessions")
    elif code == "vague_request_pattern":
        count = pq_deficit_counts.get("vague-request", 0)
        snippets.append(f"vague-request deficit in {count} sessions")
    elif code in {"acceptance_criteria_late", "delivery_closure_gap"}:
        count = pq_deficit_counts.get("missing-acceptance-criteria", 0)
        snippets.append(f"missing-acceptance-criteria in {count} sessions")
    return snippets


# ---------------------------------------------------------------------------
# Stage-2 parser: deserialize LLM JSON → DiagnosisResult
# ---------------------------------------------------------------------------


def parse_diagnosis_payload(raw: dict) -> DiagnosisResult:
    """Parse the structured LLM output into a DiagnosisResult."""

    def _parse_one(item: dict) -> GroundedDiagnosis:
        return GroundedDiagnosis(
            code=str(item.get("code", "")),
            label=str(item.get("label", "")),
            explanation=str(item.get("explanation", "")),
            confidence=min(100, max(0, int(item.get("confidence", 50) or 50))),
            evidence_refs=[
                ref for ref in item.get("evidence_refs", []) if isinstance(ref, str) and ref.strip()
            ],
            why_not_other_diagnosis=str(item.get("why_not_other_diagnosis", "")),
            next_action=str(item.get("next_action", "")),
        )

    primary_raw = raw.get("primary_diagnosis")
    primary = _parse_one(primary_raw) if isinstance(primary_raw, dict) else None

    secondary = [
        _parse_one(item)
        for item in raw.get("secondary_diagnoses", [])[:3]
        if isinstance(item, dict)
    ]

    confidence_raw = str(raw.get("synthesis_confidence", "low") or "low")
    if confidence_raw not in {"high", "medium", "low"}:
        confidence_raw = "low"

    return DiagnosisResult(
        primary=primary,
        secondary=secondary,
        synthesis_confidence=confidence_raw,
        source="llm",
    )


def rule_fallback_diagnosis(packet: DiagnosisCandidatePacket) -> DiagnosisResult:
    """Produce a minimal rule-layer DiagnosisResult when LLM is unavailable."""

    if not packet.candidates:
        return DiagnosisResult(source="rule_fallback")

    top = packet.candidates[0]
    primary = GroundedDiagnosis(
        code=top.code,
        label=top.code.replace("_", " ").title(),
        explanation=f"Rule-layer signal: urgency={round(top.urgency)}; gap={round(top.gap)}.",
        confidence=min(85, int(top.urgency)),
        evidence_refs=list(top.evidence_snippets),
        why_not_other_diagnosis="",
        next_action="",
    )
    secondary = [
        GroundedDiagnosis(
            code=cand.code,
            label=cand.code.replace("_", " ").title(),
            explanation=f"Urgency={round(cand.urgency)}.",
            confidence=min(70, int(cand.urgency)),
            evidence_refs=list(cand.evidence_snippets),
        )
        for cand in packet.candidates[1:4]
    ]
    return DiagnosisResult(
        primary=primary,
        secondary=secondary,
        synthesis_confidence="low",
        source="rule_fallback",
    )
