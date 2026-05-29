"""Canonical taxonomies for AI Growth Mirror session reading.

Closed enumerations the LLM must classify session signals against.
Keep this module dependency-free so prompt templates can quote it
via Jinja includes without circular imports.
"""
from __future__ import annotations

import re
from enum import StrEnum


# ── Resistance signals (9 kinds) ─────────────────────────────────────────────

class ResistanceKind(StrEnum):
    """A moment where user-AI collaboration lost ground."""
    OFF_TRACK         = "off-track"
    BLIND_SPOT        = "blind-spot"
    OUTDATED_CONTEXT  = "outdated-context"
    FUZZY_INTENT      = "fuzzy-intent"
    CONTEXT_GAP       = "context-gap"
    GOAL_DRIFT        = "goal-drift"
    RECURRING_PATTERN = "recurring-pattern"
    REFERENCE_GAP     = "reference-gap"
    TOOL_CEILING      = "tool-ceiling"


CANONICAL_RESISTANCE_CATEGORIES: tuple[str, ...] = tuple(ResistanceKind)


# ── Momentum signals (8 kinds) ───────────────────────────────────────────────

class MomentumKind(StrEnum):
    """A behavior that contributed to productive forward motion."""
    PLANNED_APPROACH  = "planned-approach"
    STEP_BY_STEP      = "step-by-step"
    VERIFY_LOOP       = "verify-loop"
    METHODICAL_DEBUG  = "methodical-debug"
    COURSE_CORRECTION = "course-correction"
    CONTEXT_BUILDING  = "context-building"
    KNOWLEDGE_LEVERAGE = "knowledge-leverage"
    SMART_TOOLING     = "smart-tooling"


CANONICAL_MOMENTUM_CATEGORIES: tuple[str, ...] = tuple(MomentumKind)


# ── Attribution & driver values ──────────────────────────────────────────────

class ResistanceAttribution(StrEnum):
    USER_ACTIONABLE = "user-actionable"
    AI_CAPABILITY   = "ai-capability"
    ENVIRONMENTAL   = "environmental"

class MomentumDriver(StrEnum):
    USER_DRIVEN  = "user-driven"
    AI_DRIVEN    = "ai-driven"
    COLLABORATIVE = "collaborative"

class ResistanceSeverity(StrEnum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


RESISTANCE_ATTRIBUTIONS: tuple[str, ...] = tuple(ResistanceAttribution)
MOMENTUM_DRIVERS: tuple[str, ...] = tuple(MomentumDriver)
RESISTANCE_SEVERITIES: tuple[str, ...] = tuple(ResistanceSeverity)


# ── Prompt Quality categories (10, closed) ──────────────────────────────────

class PQDeficitKind(StrEnum):
    VAGUE_REQUEST              = "vague-request"
    MISSING_CONTEXT            = "missing-context"
    LATE_CONSTRAINT            = "late-constraint"
    UNCLEAR_CORRECTION         = "unclear-correction"
    SCOPE_DRIFT                = "scope-drift"
    MISSING_ACCEPTANCE_CRITERIA = "missing-acceptance-criteria"
    ASSUMPTION_NOT_SURFACED    = "assumption-not-surfaced"

class PQStrengthKind(StrEnum):
    PRECISE_REQUEST      = "precise-request"
    EFFECTIVE_CONTEXT    = "effective-context"
    PRODUCTIVE_CORRECTION = "productive-correction"

class PQFindingType(StrEnum):
    DEFICIT  = "deficit"
    STRENGTH = "strength"

class PQTakeawayType(StrEnum):
    IMPROVE   = "improve"
    REINFORCE = "reinforce"

class PQImpact(StrEnum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


CANONICAL_PQ_DEFICIT_CATEGORIES: tuple[str, ...] = tuple(PQDeficitKind)
CANONICAL_PQ_STRENGTH_CATEGORIES: tuple[str, ...] = tuple(PQStrengthKind)
CANONICAL_PQ_CATEGORIES: tuple[str, ...] = (
    *CANONICAL_PQ_DEFICIT_CATEGORIES,
    *CANONICAL_PQ_STRENGTH_CATEGORIES,
)
PQ_FINDING_TYPES: tuple[str, ...] = tuple(PQFindingType)
PQ_TAKEAWAY_TYPES: tuple[str, ...] = tuple(PQTakeawayType)
PQ_IMPACTS: tuple[str, ...] = tuple(PQImpact)

PQ_DIMENSIONS: tuple[str, ...] = (
    "context_provision",
    "request_specificity",
    "scope_management",
    "information_timing",
    "correction_quality",
)


# ── Decision trees (quoted verbatim into LLM prompts) ────────────────────────

# Decision tree texts now live in prompt bundles.


# ── Fuzzy normalization ──────────────────────────────────────────────────────

_NORMALIZE_RE = re.compile(r"[\s_]+")

_RESISTANCE_ALIASES: dict[str, str] = {
    # off-track
    "wrong-approach":       ResistanceKind.OFF_TRACK,
    "wrong-direction":      ResistanceKind.OFF_TRACK,
    "wrong-strategy":       ResistanceKind.OFF_TRACK,
    "bad-approach":         ResistanceKind.OFF_TRACK,
    "suboptimal-approach":  ResistanceKind.OFF_TRACK,
    # blind-spot
    "knowledge-gap":        ResistanceKind.BLIND_SPOT,
    "knowledge-error":      ResistanceKind.BLIND_SPOT,
    "wrong-api":            ResistanceKind.BLIND_SPOT,
    "incorrect-api-usage":  ResistanceKind.BLIND_SPOT,
    # outdated-context
    "stale-assumptions":    ResistanceKind.OUTDATED_CONTEXT,
    "stale-context":        ResistanceKind.OUTDATED_CONTEXT,
    "outdated-assumption":  ResistanceKind.OUTDATED_CONTEXT,
    "wrong-assumption":     ResistanceKind.OUTDATED_CONTEXT,
    # fuzzy-intent
    "incomplete-requirements": ResistanceKind.FUZZY_INTENT,
    "missing-requirements": ResistanceKind.FUZZY_INTENT,
    "vague-prompt":         ResistanceKind.FUZZY_INTENT,
    "ambiguous-prompt":     ResistanceKind.FUZZY_INTENT,
    "ambiguous-request":    ResistanceKind.FUZZY_INTENT,
    "misunderstood-request": ResistanceKind.FUZZY_INTENT,
    # context-gap
    "context-loss":         ResistanceKind.CONTEXT_GAP,
    "forgot-context":       ResistanceKind.CONTEXT_GAP,
    "lost-context":         ResistanceKind.CONTEXT_GAP,
    "context-drift":        ResistanceKind.CONTEXT_GAP,
    # goal-drift
    "scope-creep":          ResistanceKind.GOAL_DRIFT,
    "scope-drift":          ResistanceKind.GOAL_DRIFT,
    "expanded-scope":       ResistanceKind.GOAL_DRIFT,
    # recurring-pattern
    "repeated-mistakes":    ResistanceKind.RECURRING_PATTERN,
    "repeat-mistake":       ResistanceKind.RECURRING_PATTERN,
    "same-error-twice":     ResistanceKind.RECURRING_PATTERN,
    # reference-gap
    "documentation-gap":    ResistanceKind.REFERENCE_GAP,
    "missing-docs":         ResistanceKind.REFERENCE_GAP,
    "no-docs":              ResistanceKind.REFERENCE_GAP,
    # tool-ceiling
    "tooling-limitation":   ResistanceKind.TOOL_CEILING,
    "tool-limitation":      ResistanceKind.TOOL_CEILING,
    "tool-error":           ResistanceKind.TOOL_CEILING,
    "tool-failure":         ResistanceKind.TOOL_CEILING,
    # historical aliases
    "buggy-code":           ResistanceKind.BLIND_SPOT,
    "user-rejected-action": ResistanceKind.OFF_TRACK,
    "session-abandoned":    ResistanceKind.OFF_TRACK,
}

_MOMENTUM_ALIASES: dict[str, str] = {
    "structured-planning":        MomentumKind.PLANNED_APPROACH,
    "planning":                   MomentumKind.PLANNED_APPROACH,
    "task-decomposition":         MomentumKind.PLANNED_APPROACH,
    "incremental-implementation": MomentumKind.STEP_BY_STEP,
    "incremental":                MomentumKind.STEP_BY_STEP,
    "small-steps":                MomentumKind.STEP_BY_STEP,
    "verification-workflow":      MomentumKind.VERIFY_LOOP,
    "verification":               MomentumKind.VERIFY_LOOP,
    "test-first":                 MomentumKind.VERIFY_LOOP,
    "systematic-debugging":       MomentumKind.METHODICAL_DEBUG,
    "debugging":                  MomentumKind.METHODICAL_DEBUG,
    "binary-search":              MomentumKind.METHODICAL_DEBUG,
    "self-correction":            MomentumKind.COURSE_CORRECTION,
    "self-correct":               MomentumKind.COURSE_CORRECTION,
    "context-gathering":          MomentumKind.CONTEXT_BUILDING,
    "investigation":              MomentumKind.CONTEXT_BUILDING,
    "code-reading":               MomentumKind.CONTEXT_BUILDING,
    "thorough-investigation":     MomentumKind.CONTEXT_BUILDING,
    "domain-expertise":           MomentumKind.KNOWLEDGE_LEVERAGE,
    "expertise":                  MomentumKind.KNOWLEDGE_LEVERAGE,
    "framework-knowledge":        MomentumKind.KNOWLEDGE_LEVERAGE,
    "effective-tooling":          MomentumKind.SMART_TOOLING,
    "agent-delegation":           MomentumKind.SMART_TOOLING,
    "parallel-tools":             MomentumKind.SMART_TOOLING,
    "tool-use":                   MomentumKind.SMART_TOOLING,
}


def _slugify(label: str) -> str:
    return _NORMALIZE_RE.sub("-", label.strip().lower()).strip("-")


def canonicalize_resistance(label: str) -> str:
    """Return the canonical resistance value for a noisy label."""
    if not label:
        return ""
    slug = _slugify(label)
    if slug in CANONICAL_RESISTANCE_CATEGORIES:
        return slug
    return _RESISTANCE_ALIASES.get(slug, slug)


def canonicalize_momentum(label: str) -> str:
    """Return the canonical momentum value for a noisy label."""
    if not label:
        return ""
    slug = _slugify(label)
    if slug in CANONICAL_MOMENTUM_CATEGORIES:
        return slug
    return _MOMENTUM_ALIASES.get(slug, slug)


def is_canonical_resistance(label: str) -> bool:
    return label in CANONICAL_RESISTANCE_CATEGORIES


def is_canonical_momentum(label: str) -> bool:
    return label in CANONICAL_MOMENTUM_CATEGORIES

from enum import IntEnum as _IntEnum


class InteractionKind(_IntEnum):
    """Operational category of a single tool invocation (pure domain value object).

    Defined in domain/ so that domain-layer modules can reference tool interaction
    kinds without depending on infra/. Tool-name mapping lives in domain/signals/tooling.py.
    """

    INSPECT = READ = 1
    MODIFY = WRITE = 2
    EXECUTE = BASH = 3
    EXTERNAL = MCP_TOOL = 4
    BROWSE = WEB = 5
    WORKFLOW = SKILL = 6
    DELEGATE = SUBAGENT = 7
    ORGANIZE = PLAN = 8
    VALIDATE = TEST = 9
    VERSION = GIT_OP = 10
    CONTEXT_CTRL = COMPACT = 11
    MISC = OTHER = 12


class ModelCapabilityTier(_IntEnum):
    """Rough capability band for the LLM powering a session."""

    LIGHTWEIGHT = TIER_0_SCRATCH = 0
    QUICK = TIER_1_QUICK = 1
    CAPABLE = TIER_2_STANDARD = 2
    ADVANCED = TIER_3_PRO = 3

