"""Agentic Evidence Graph — six-dimension fact graph per session.

Each AgenticEvidenceNode captures observable facts from one session across
six dimensions.  The graph is assembled from SessionRecord + SessionRead
pairs and provides grounded evidence for coaching, diagnosis, and snapshot
comparison.

Domain-only: no I/O, no LLM calls, no application or infra imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.model import SessionRecord
    from ..signals.model import SessionRead


# ---------------------------------------------------------------------------
# Node contracts
# ---------------------------------------------------------------------------


@dataclass
class AgenticEvidenceNode:
    """Verified facts for one session across six agentic dimensions."""

    session_id: str

    # Dim 1: What the user intended to accomplish
    task_intent: str = ""
    # Dim 2: Which methods were actively invoked (skills, slash, frameworks)
    method_used: list[str] = field(default_factory=list)
    # Dim 3: What context was brought in (files, rules, docs references)
    context_used: list[str] = field(default_factory=list)
    # Dim 4: How execution actually flowed (read→edit→test→verify pattern)
    execution_path: str = ""
    # Dim 5: Whether the session reached a defined closure state
    closure_state: str = ""
    # Dim 6: How much human intervention was required
    human_intervention: int = 0

    # Derived quality signals
    has_verification: bool = False
    outcome_code: str = ""  # fully_achieved | partially_achieved | blocked | unclear


@dataclass
class AgenticEvidenceGraphSummary:
    """Period-level aggregations over the full Evidence Graph."""

    node_count: int = 0
    # Dim 2 aggregations
    top_methods: list[tuple[str, int]] = field(default_factory=list)
    unique_method_count: int = 0
    # Dim 3 aggregations
    context_rich_node_count: int = 0
    context_rich_rate: float = 0.0
    # Dim 4 aggregations
    verified_execution_count: int = 0
    verified_execution_rate: float = 0.0
    # Dim 5 aggregations
    fully_closed_count: int = 0
    fully_closed_rate: float = 0.0
    partially_closed_count: int = 0
    unclear_closure_count: int = 0
    # Dim 6 aggregations
    high_intervention_count: int = 0
    high_intervention_rate: float = 0.0
    avg_human_intervention: float = 0.0
    # Cross-dim signals
    method_plus_verification_count: int = 0
    method_plus_closure_count: int = 0


@dataclass
class AgenticEvidenceGraph:
    """Full six-dimension evidence graph for a reporting period."""

    nodes: list[AgenticEvidenceNode] = field(default_factory=list)
    summary: AgenticEvidenceGraphSummary = field(default_factory=AgenticEvidenceGraphSummary)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

_SKILL_METHOD_MARKERS = frozenset({"delivery-workflow", "ai-development-governance", "doc-script-governance"})


def _extract_task_intent(session: "SessionRecord", session_read: "SessionRead | None") -> str:
    """Resolve the dominant task intent from SessionRead or first prompt."""
    if session_read is not None:
        intent_mix = session_read.work_intent_mix or {}
        if intent_mix:
            return max(intent_mix, key=lambda k: intent_mix[k])
    prompt = (session.first_prompt or "").strip()[:60]
    return prompt or "unknown"


def _extract_method_used(session: "SessionRecord") -> list[str]:
    """Collect distinct methods: skill names, slash commands, framework names."""
    methods: list[str] = []
    methods.extend(session.unique_skills_used or [])
    methods.extend(session.slash_commands or [])
    methods.extend(session.advanced_features or [])
    # De-dup while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for m in methods:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result[:12]


def _extract_context_used(session: "SessionRecord") -> list[str]:
    """Infer context sources from prompt content and tool counts."""
    ctx: list[str] = []
    prompt = session.first_prompt or ""
    if ".py" in prompt or ".ts" in prompt or ".go" in prompt or ".rs" in prompt:
        ctx.append("code_file_reference")
    if "AGENTS.md" in prompt or "CLAUDE.md" in prompt or "rules/" in prompt:
        ctx.append("rule_file_reference")
    if "docs/" in prompt or "design/" in prompt:
        ctx.append("docs_reference")
    if "@" in prompt or "#" in prompt:
        ctx.append("inline_anchor")
    read_calls = session.tool_counts.get("Read", 0) + session.tool_counts.get("read_file", 0)
    if read_calls >= 3:
        ctx.append(f"read_calls={read_calls}")
    if not ctx:
        ctx.append("minimal_context")
    return ctx


def _execution_path_label(session: "SessionRecord") -> str:
    """Derive a short execution-path pattern label from tool call patterns."""
    tc = session.tool_counts or {}
    has_read = (tc.get("Read", 0) + tc.get("read_file", 0)) > 0
    has_edit = (tc.get("Edit", 0) + tc.get("Write", 0) + tc.get("str_replace_editor", 0)) > 0
    has_bash = (tc.get("Bash", 0) + tc.get("execute_command", 0) + tc.get("run_terminal_cmd", 0)) > 0
    has_test = session.has_test_commands
    has_verify = session.has_verification_behavior

    if has_read and has_edit and has_bash and has_verify:
        return "read→edit→run→verify"
    if has_read and has_edit and has_bash:
        return "read→edit→run"
    if has_read and has_edit and has_test:
        return "read→edit→test"
    if has_read and has_edit:
        return "read→edit"
    if has_edit:
        return "edit_only"
    if has_read:
        return "read_only"
    return "conversation"


def _closure_state(session: "SessionRecord", session_read: "SessionRead | None") -> str:
    """Map session outcome to a closure state label."""
    if session_read is not None:
        outcome = session_read.delivery_outcome or "unclear"
        if outcome == "fully_achieved":
            return "closed"
        if outcome == "partially_achieved":
            return "partial"
        if outcome in {"blocked", "abandoned"}:
            return "blocked"
        return "unclear"
    if session.has_verification_behavior:
        return "probable_closed"
    return "unknown"


def build_agentic_evidence_graph(
    sessions: "list[SessionRecord]",
    session_reads: "list[SessionRead]",
) -> AgenticEvidenceGraph:
    """Build the six-dimension evidence graph from session + session_read pairs."""
    read_by_id: dict[str, "SessionRead"] = {sr.session_id: sr for sr in session_reads}
    nodes: list[AgenticEvidenceNode] = []

    for session in sessions:
        sr = read_by_id.get(session.session_id)
        node = AgenticEvidenceNode(
            session_id=session.session_id,
            task_intent=_extract_task_intent(session, sr),
            method_used=_extract_method_used(session),
            context_used=_extract_context_used(session),
            execution_path=_execution_path_label(session),
            closure_state=_closure_state(session, sr),
            human_intervention=session.user_interruptions,
            has_verification=session.has_verification_behavior,
            outcome_code=sr.delivery_outcome if sr else "unknown",
        )
        nodes.append(node)

    summary = _build_summary(nodes)
    return AgenticEvidenceGraph(nodes=nodes, summary=summary)


def _build_summary(nodes: list[AgenticEvidenceNode]) -> AgenticEvidenceGraphSummary:
    if not nodes:
        return AgenticEvidenceGraphSummary()

    from collections import Counter

    n = len(nodes)
    method_counter: Counter[str] = Counter()
    context_rich = 0
    verified = 0
    fully_closed = 0
    partially_closed = 0
    unclear_closure = 0
    high_intervention = 0
    total_intervention = 0
    method_and_verify = 0
    method_and_closed = 0

    for node in nodes:
        method_counter.update(node.method_used)
        if "minimal_context" not in node.context_used:
            context_rich += 1
        if node.has_verification:
            verified += 1
        if node.closure_state == "closed":
            fully_closed += 1
        elif node.closure_state == "partial":
            partially_closed += 1
        elif node.closure_state in {"unclear", "unknown"}:
            unclear_closure += 1
        if node.human_intervention >= 2:
            high_intervention += 1
        total_intervention += node.human_intervention
        if node.method_used and node.has_verification:
            method_and_verify += 1
        if node.method_used and node.closure_state == "closed":
            method_and_closed += 1

    top_methods = method_counter.most_common(8)

    return AgenticEvidenceGraphSummary(
        node_count=n,
        top_methods=top_methods,
        unique_method_count=len(method_counter),
        context_rich_node_count=context_rich,
        context_rich_rate=round(context_rich / n, 4),
        verified_execution_count=verified,
        verified_execution_rate=round(verified / n, 4),
        fully_closed_count=fully_closed,
        fully_closed_rate=round(fully_closed / n, 4),
        partially_closed_count=partially_closed,
        unclear_closure_count=unclear_closure,
        high_intervention_count=high_intervention,
        high_intervention_rate=round(high_intervention / n, 4),
        avg_human_intervention=round(total_intervention / n, 2),
        method_plus_verification_count=method_and_verify,
        method_plus_closure_count=method_and_closed,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers (no I/O — used by application layer)
# ---------------------------------------------------------------------------


def evidence_graph_to_dict(graph: AgenticEvidenceGraph) -> dict:
    """Convert to plain dict for JSON serialisation."""
    from dataclasses import asdict
    return asdict(graph)
