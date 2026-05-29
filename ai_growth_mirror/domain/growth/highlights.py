"""Highlight mining for AI Growth Mirror — surface high-signal growth moments.

Identifies, scores, and groups sessions that demonstrate effective AI collaboration
patterns. No LLM calls; deterministic output based on adapter-extracted signals.

Scoring philosophy: reward operator craft (prompt precision, closed-loop verification,
sustained engagement) over raw tool output volume.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..session.model import SessionRecord
from ..signals.model import SessionRead


# ── Patterns ────────────────────────────────────────────────────────────────

PATTERN_DEEP_DELEGATOR = "deep_delegator"
PATTERN_TOOLKIT_ORCHESTRATOR = "toolkit_orchestrator"
PATTERN_VERIFY_FIRST = "verify_first"
PATTERN_PRECISION_SEEKER = "precision_seeker"
PATTERN_STRUCTURED_EXECUTOR = "structured_executor"
PATTERN_FOCUSED_DELIVERY = "focused_delivery"
PATTERN_GENERAL = "general"

ALL_PATTERNS: tuple[str, ...] = (
    PATTERN_DEEP_DELEGATOR,
    PATTERN_TOOLKIT_ORCHESTRATOR,
    PATTERN_VERIFY_FIRST,
    PATTERN_PRECISION_SEEKER,
    PATTERN_STRUCTURED_EXECUTOR,
    PATTERN_FOCUSED_DELIVERY,
)

def pattern_label(pattern: str, labels: dict[str, str]) -> str:
    """Return human-readable pattern label from a preloaded label table."""
    return labels.get(pattern, pattern)
# ── Hard gates ──────────────────────────────────────────────────────────────

_POSITIVE_OUTCOMES = frozenset({"fully_achieved", "mostly_achieved"})
_POSITIVE_HELPFULNESS = frozenset({"very_helpful", "helpful"})


def _passes_gate(meta: SessionRecord, facets: SessionRead) -> bool:
    """Outcome gate — below this bar a session is never an exemplar."""
    if facets.delivery_outcome not in _POSITIVE_OUTCOMES:
        return False
    if facets.support_value not in _POSITIVE_HELPFULNESS:
        return False
    if facets.confidence == "low":
        return False
    has_output = (
        meta.files_modified > 0
        or meta.git_commits > 0
        or sum(meta.tool_counts.values()) >= 10
    )
    if not has_output:
        return False
    return True


def _passes_authorship_gate(meta: SessionRecord) -> bool:
    """Authorship gate — the user must be demonstrably involved."""
    if meta.entrypoint.startswith("sdk-"):
        return False
    if _is_skill_expanded_prompt(meta.first_prompt):
        is_empty_prompt = not meta.first_prompt or not meta.first_prompt.strip()
        if not is_empty_prompt:
            return False
        if meta.tool_name == "claude_code":
            return False
        if meta.user_message_count < 2:
            return False
    if meta.user_message_count >= 2:
        return True
    if meta.prompt_word_count >= 40 and (
        meta.prompt_has_constraint or meta.prompt_has_code_context
    ):
        return True
    return False


def _is_skill_expanded_prompt(prompt: str) -> bool:
    """Detect prompts injected by the Skill framework, not typed by a human."""
    if not prompt or not prompt.strip():
        return True
    stripped = prompt.lstrip()
    if stripped[:25].lower().startswith("the user just ran /"):
        return True
    if stripped.startswith("# /"):
        return True
    if stripped.startswith("Implement tasks from an OpenSpec"):
        return True
    if stripped.startswith("# Task:") and "## Background" in stripped[:500]:
        return True
    if "上下文（自动收集）" in stripped[:100]:
        return True
    return False


# ── Scoring ─────────────────────────────────────────────────────────────────

def _score(meta: SessionRecord) -> tuple[float, dict[str, float]]:
    """Score a session's growth mirror quality."""
    signals: dict[str, float] = {}

    max_chain = max(meta.autonomous_chain_lengths) if meta.autonomous_chain_lengths else 0
    signals["delegation_reach"] = round(1.4 * math.log1p(max_chain), 3)

    signals["closed_loop"] = 1.6 if meta.has_verification_behavior else 0.0

    signals["ecosystem_use"] = 1.0 if meta.skill_invocation_count > 0 else 0.0

    signals["capability_reach"] = 1.1 if (meta.uses_subagent or meta.uses_mcp) else 0.0

    signals["intent_precision"] = 1.6 if meta.prompt_has_constraint else 0.0
    signals["context_richness"] = 1.4 if meta.prompt_has_code_context else 0.0
    signals["prompt_depth"] = round(min(meta.prompt_word_count / 75.0, 1.2), 3)

    signals["engagement_depth"] = round(
        min(math.log1p(max(meta.user_message_count, 0)) * 0.7, 1.8), 3
    )

    signals["dropout_cost"] = round(-0.4 * meta.user_interruptions, 3)
    total_calls = sum(meta.tool_counts.values())
    signals["error_cost"] = (
        round(-1.8 * (meta.tool_errors / total_calls), 3) if total_calls > 0 else 0.0
    )

    return round(sum(signals.values()), 3), signals


# ── Categorization ──────────────────────────────────────────────────────────

def _categorize(meta: SessionRecord) -> str:
    max_chain = max(meta.autonomous_chain_lengths) if meta.autonomous_chain_lengths else 0
    if meta.uses_subagent:
        return PATTERN_DEEP_DELEGATOR
    if len(meta.unique_skills_used) >= 3:
        return PATTERN_TOOLKIT_ORCHESTRATOR
    if meta.has_verification_behavior and meta.has_test_commands:
        return PATTERN_VERIFY_FIRST
    if meta.prompt_has_code_context and meta.prompt_word_count >= 80:
        return PATTERN_PRECISION_SEEKER
    if meta.prompt_has_constraint and max_chain >= 8:
        return PATTERN_STRUCTURED_EXECUTOR
    if meta.git_commits >= 1 and max_chain <= 4:
        return PATTERN_FOCUSED_DELIVERY
    return PATTERN_GENERAL


# ── Output ──────────────────────────────────────────────────────────────────


@dataclass
class Exemplar:
    session_id: str
    tool_name: str
    pattern: str
    score: float
    signal_weights: dict[str, float]
    meta: SessionRecord
    facets: SessionRead
    highlight: str = ""
    story_hook: str = ""
    technique: str = ""
    narrative_quality: int = 0


def surface_highlights(
    sessions: list[SessionRecord],
    facets: list[SessionRead],
    limit: int = 5,
    pattern_cap: int = 2,
    include_ungrouped: bool = False,
) -> list[Exemplar]:
    """Return top highlights with diversity rerank across collaboration patterns."""
    if not sessions or not facets:
        return []

    facet_by_id = {f.session_id: f for f in facets}

    candidates: list[Exemplar] = []
    for s in sessions:
        f = facet_by_id.get(s.session_id)
        if f is None:
            continue
        if not _passes_gate(s, f):
            continue
        if not _passes_authorship_gate(s):
            continue
        pattern = _categorize(s)
        if not include_ungrouped and pattern == PATTERN_GENERAL:
            continue
        score, signals = _score(s)
        candidates.append(
            Exemplar(
                session_id=s.session_id,
                tool_name=s.tool_name,
                pattern=pattern,
                score=score,
                signal_weights=signals,
                meta=s,
                facets=f,
            )
        )

    candidates.sort(key=lambda e: (-e.score, e.session_id))

    picked: list[Exemplar] = []
    per_pattern: dict[str, int] = {}
    for ex in candidates:
        if len(picked) >= limit:
            break
        if per_pattern.get(ex.pattern, 0) >= pattern_cap:
            continue
        picked.append(ex)
        per_pattern[ex.pattern] = per_pattern.get(ex.pattern, 0) + 1

    if len(picked) < limit:
        chosen = {e.session_id for e in picked}
        for ex in candidates:
            if len(picked) >= limit:
                break
            if ex.session_id in chosen:
                continue
            picked.append(ex)

    return picked


def pattern_label(pattern: str, labels: dict[str, str]) -> str:
    """Return human-readable pattern label from a preloaded label table."""
    return labels.get(pattern, pattern)
