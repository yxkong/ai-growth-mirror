"""Converters from LLM JSON payloads to growth mirror models."""

from __future__ import annotations

from .model import (
    CAPABILITY_DEPTH_LEVELS,
    CAPABILITY_FOCUS_AREAS,
    WORK_STYLE_VALUES,
    MomentumSignal,
    PromptLensFinding,
    PromptLensScores,
    PromptLensTakeaway,
    ResistanceSignal,
    SessionRead,
)


def clamp_taxonomy(value: str | None, allowed: tuple[str, ...], default: str) -> str:
    if value in allowed:
        return str(value)
    return default


def parse_resistance_signals(items: object) -> list[ResistanceSignal]:
    if not isinstance(items, list):
        return []
    return [
        ResistanceSignal(
            category=item.get("category", ""),
            attribution=item.get("attribution", "user-actionable"),
            description=item.get("description", ""),
            severity=item.get("severity", "medium"),
            confidence=int(item.get("confidence", 70) or 70),
        )
        for item in items
        if isinstance(item, dict)
    ]


def parse_momentum_signals(items: object) -> list[MomentumSignal]:
    if not isinstance(items, list):
        return []
    return [
        MomentumSignal(
            category=item.get("category", ""),
            driver=item.get("driver", "collaborative"),
            label=item.get("label", ""),
            description=item.get("description", ""),
            confidence=int(item.get("confidence", 70) or 70),
        )
        for item in items
        if isinstance(item, dict)
    ]


def parse_prompt_lens_payload(raw: dict) -> PromptLensScores:
    dimension_scores = raw.get("dimension_scores", {})
    findings = [
        PromptLensFinding(
            category=item.get("category", ""),
            type=item.get("type", "deficit"),
            description=item.get("description", ""),
            message_ref=item.get("message_ref", ""),
            impact=item.get("impact", "low"),
            confidence=int(item.get("confidence", 70) or 70),
            suggested_improvement=item.get("suggested_improvement", ""),
        )
        for item in raw.get("findings", [])[:8]
        if isinstance(item, dict)
    ]
    takeaways = [
        PromptLensTakeaway(
            type=item.get("type", "improve"),
            category=item.get("category", ""),
            label=item.get("label", ""),
            message_ref=item.get("message_ref", ""),
            original=item.get("original", ""),
            better_prompt=item.get("better_prompt", ""),
            why=item.get("why", ""),
            what_worked=item.get("what_worked", ""),
            why_effective=item.get("why_effective", ""),
        )
        for item in raw.get("takeaways", [])[:4]
        if isinstance(item, dict)
    ]
    return PromptLensScores(
        source=str(raw.get("source", "llm") or "llm"),
        coverage=str(raw.get("coverage", "full") or "full"),
        evaluated_user_messages=int(raw.get("evaluated_user_messages", 0) or 0),
        context_provision=int(dimension_scores.get("context_provision", 50) or 50),
        request_specificity=int(dimension_scores.get("request_specificity", 50) or 50),
        scope_management=int(dimension_scores.get("scope_management", 50) or 50),
        information_timing=int(dimension_scores.get("information_timing", 50) or 50),
        correction_quality=int(dimension_scores.get("correction_quality", 50) or 50),
        efficiency_score=int(raw.get("efficiency_score", 50) or 50),
        findings=findings,
        takeaways=takeaways,
    )


def parse_session_read_payload(
    *,
    raw: dict,
    session_id: str,
    tool_name: str,
    confidence: str,
) -> SessionRead:
    return SessionRead(
        session_id=session_id,
        tool_name=tool_name,
        work_summary=raw.get("work_summary", ""),
        work_intent_mix=raw.get("work_intent_mix", {}),
        delivery_outcome=raw.get("delivery_outcome", "unclear"),
        user_readback=raw.get("user_readback", {}),
        support_value=raw.get("support_value", "helpful"),
        collaboration_shape=raw.get("collaboration_shape", "single_task"),
        resistance_signals=parse_resistance_signals(raw.get("resistance_signals")),
        momentum_signals=parse_momentum_signals(raw.get("momentum_signals")),
        resistance_summary=raw.get("resistance_summary", ""),
        key_gain=raw.get("key_gain", ""),
        session_takeaway=raw.get("session_takeaway", ""),
        confidence=confidence,
        capability_focus=clamp_taxonomy(
            raw.get("capability_focus"),
            CAPABILITY_FOCUS_AREAS,
            "none",
        ),
        capability_depth=clamp_taxonomy(
            raw.get("capability_depth"),
            CAPABILITY_DEPTH_LEVELS,
            "incidental",
        ),
        work_style=clamp_taxonomy(
            raw.get("work_style"),
            WORK_STYLE_VALUES,
            "freeform",
        ),
    )


