"""Public registry of structured-workflow frameworks (SDD / TDD / plan-execute).

The registry recognises *publicly known* coding-agent frameworks by their
externally observable fingerprints — the slash-command names a user types
and the ``Skill`` tool ``input.command`` values an agent invokes.

Scope and intentional limits
----------------------------
- File-path detection is **out of scope**: even though Edit/Write tool inputs
  carry file paths, mixing path heuristics with name heuristics broadens the
  detector's failure modes without obvious precision gain in our validation
  data.  Path-based detection may be added later in a separate signal layer.
- Project-directory scanning (reading ``.claude/skills/**/SKILL.md`` or
  similar) is **deliberately excluded** to keep data collection scope to the
  session JSONL files we already parse.
- In-house / non-public workflow frameworks **cannot** be reliably
  distinguished from in-house domain-utility commands by name alone, so
  there is no "recurring-custom-command" floor here.  The LLM session-style
  classifier handles structured behaviour that lacks a public fingerprint.

The registry is intentionally small and curated; adding a framework should
be one PR per framework, with the upstream source URL in the comment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.model import SessionRecord


# Family targets aligned with SESSION_WORKFLOW_STYLES in the session signal taxonomy.
# A framework whose sub-commands span multiple disciplines (e.g. superpowers
# bundles plan + tdd + debug skills) maps to "mixed" so the LLM can still
# disambiguate per-session.
WORKFLOW_FAMILIES = ("plan_driven", "spec_driven", "tdd", "adaptive")


@dataclass(frozen=True)
class WorkflowFramework:
    """One public workflow framework fingerprint.

    Matching is case-insensitive.  A session matches when ANY of:
    - a slash command (with leading ``/`` stripped) equals one of
      ``slash_exact`` or starts with one of ``slash_prefixes``.
    - a skill name (the ``input.command`` of a Skill tool call) equals one of
      ``skill_exact`` or starts with one of ``skill_prefixes``.
    """

    name: str
    family: str
    slash_prefixes: tuple[str, ...] = field(default_factory=tuple)
    slash_exact: tuple[str, ...] = field(default_factory=tuple)
    skill_prefixes: tuple[str, ...] = field(default_factory=tuple)
    skill_exact: tuple[str, ...] = field(default_factory=tuple)
    # Human-friendly label for UI surfaces (chip / sidecar).  Defaults to a
    # title-cased fallback when omitted — set explicitly when capitalisation
    # matters (e.g. "OpenSpec" instead of "Openspec").
    display_name: str = ""

    def matches_slash(self, slash_name: str) -> bool:
        n = slash_name.lstrip("/").lower()
        if n in self.slash_exact:
            return True
        return any(n.startswith(p) for p in self.slash_prefixes)

    def matches_skill(self, skill_name: str) -> bool:
        n = skill_name.lower()
        if n in self.skill_exact:
            return True
        return any(n.startswith(p) for p in self.skill_prefixes)


# ── Registry ─────────────────────────────────────────────────────────────────
# Each entry cites its upstream source.  Slash / skill names are stored
# lowercase.  Generic-sounding command names (``plan``, ``tasks``,
# ``implement``) are excluded unless paired with a unique prefix — otherwise
# they'd false-positive against Claude Code's built-in plan-mode toggles.

_FRAMEWORKS: tuple[WorkflowFramework, ...] = (
    # GitHub Spec Kit — https://github.com/github/spec-kit
    WorkflowFramework(
        name="spec_kit",
        display_name="Spec Kit",
        family="spec_driven",
        slash_prefixes=("speckit.",),
    ),
    # OpenSpec — https://github.com/Fission-AI/OpenSpec
    WorkflowFramework(
        name="openspec",
        display_name="OpenSpec",
        family="spec_driven",
        slash_prefixes=("opsx:",),
        skill_prefixes=("opsx:", "openspec-"),
    ),
    # BMAD-METHOD — https://github.com/bmad-code-org/BMAD-METHOD
    WorkflowFramework(
        name="bmad",
        display_name="BMAD",
        family="spec_driven",
        slash_prefixes=("bmad:",),
        skill_prefixes=("bmad:",),
    ),
    # Kiro & cc-sdd — https://kiro.dev / https://github.com/gotalab/cc-sdd
    WorkflowFramework(
        name="kiro",
        display_name="Kiro",
        family="spec_driven",
        slash_prefixes=("kiro:",),
    ),
    # ccsdd — https://github.com/ShortArrow/ccsdd
    WorkflowFramework(
        name="ccsdd",
        display_name="ccsdd",
        family="spec_driven",
        slash_prefixes=("sdd-", "sdd:"),
    ),
    # claude-code-spec-workflow — https://github.com/Pimzino/claude-code-spec-workflow
    WorkflowFramework(
        name="cc_spec_workflow",
        display_name="cc-spec-workflow",
        family="spec_driven",
        slash_exact=(
            "spec-create", "spec-design", "spec-tasks", "spec-execute",
            "bug-create", "bug-analyze", "bug-fix", "bug-verify",
        ),
    ),
    # Agent OS — https://github.com/buildermethods/agent-os
    WorkflowFramework(
        name="agent_os",
        display_name="Agent OS",
        family="spec_driven",
        slash_exact=(
            "plan-product", "shape-specs", "create-spec",
            "execute-tasks", "analyze-product",
        ),
    ),
    # PRPs-agentic-eng + context-engineering-intro — same workflow shape
    # https://github.com/Wirasm/PRPs-agentic-eng
    # https://github.com/coleam00/context-engineering-intro
    WorkflowFramework(
        name="prps",
        display_name="PRPs",
        family="spec_driven",
        slash_exact=(
            "create-base-prp", "execute-base-prp",
            "prp-base-create", "prp-base-execute",
            "generate-prp", "execute-prp",
        ),
    ),
    # ai-dev-tasks — https://github.com/snarktank/ai-dev-tasks
    WorkflowFramework(
        name="ai_dev_tasks",
        display_name="ai-dev-tasks",
        family="plan_driven",
        slash_exact=("create-prd", "generate-tasks", "process-task-list"),
    ),
    # Spec-Flow — https://github.com/marcusgoll/Spec-Flow
    WorkflowFramework(
        name="spec_flow",
        display_name="Spec-Flow",
        family="spec_driven",
        slash_prefixes=("spec-flow:", "flow:"),
    ),
    # CCPM — https://github.com/automazeio/ccpm
    WorkflowFramework(
        name="ccpm",
        display_name="CCPM",
        family="plan_driven",
        slash_prefixes=("pm:",),
    ),
    # SuperClaude Framework — https://github.com/SuperClaude-Org/SuperClaude_Framework
    WorkflowFramework(
        name="super_claude",
        display_name="SuperClaude",
        family="adaptive",
        slash_prefixes=("sc:",),
    ),
    # claude-flow / SPARC — https://github.com/ruvnet/claude-flow
    WorkflowFramework(
        name="claude_flow",
        display_name="claude-flow / SPARC",
        family="plan_driven",
        slash_prefixes=("sparc:",),
    ),
    # claude-task-master — https://github.com/eyaltoledano/claude-task-master
    WorkflowFramework(
        name="task_master",
        display_name="claude-task-master",
        family="plan_driven",
        slash_prefixes=("taskmaster:",),
    ),
    # GSD (Get Shit Done) — https://github.com/gsd-build/get-shit-done
    WorkflowFramework(
        name="gsd",
        display_name="GSD",
        family="spec_driven",
        slash_prefixes=("gsd-", "gsd:"),
    ),
    # superpowers — https://github.com/obra/superpowers
    # Mixed because its skill set spans plan-execute, brainstorm, TDD, debug.
    WorkflowFramework(
        name="superpowers",
        display_name="superpowers",
        family="adaptive",
        slash_prefixes=("superpowers:",),
        skill_prefixes=("superpowers:",),
        skill_exact=(
            "using-superpowers", "writing-plans", "executing-plans",
            "brainstorming", "test-driven-development",
            "systematic-debugging", "subagent-driven-development",
        ),
    ),
)


@dataclass(frozen=True)
class FrameworkMatch:
    """One framework detection result with the user-driven strength level."""

    framework: WorkflowFramework
    # "S" = user-typed slash command match (strongest — slash commands come
    # from <command-name> injections, which only fire on explicit user input).
    # "A" = Skill tool invocation match without a corresponding slash match
    # (auto-routing possible — still user-prompt-driven but weaker).
    level: str  # "S" | "A"
    slash_hits: tuple[str, ...] = field(default_factory=tuple)
    skill_hits: tuple[str, ...] = field(default_factory=tuple)


def framework_display_name(name: str) -> str:
    """Return the human-friendly label for a framework registry ``name``.

    Falls back to the raw name when not found, so unknown values don't crash
    UI surfaces.  Used by report template + sidecar to render chips.
    """
    for fw in _FRAMEWORKS:
        if fw.name == name:
            return fw.display_name or fw.name
    return name


def detect_frameworks(meta: "SessionRecord") -> list[FrameworkMatch]:
    """Return all public-registry frameworks fingerprinted in one session.

    Pure function — reads only the slash-command and skill-name lists already
    captured in ``SessionRecord``.  No file-path inspection, no LLM
    calls, no I/O.

    Multiple matches per session are possible (e.g. a user invokes both
    openspec and superpowers).  Caller decides how to consolidate; see
    ``aggregate_family`` below for the default rule.
    """
    slashes = [s.lstrip("/").lower() for s in (meta.slash_commands or [])]
    slashes_set = set(slashes)
    skills = [s.lower() for s in (meta.unique_skills_used or [])]

    matches: list[FrameworkMatch] = []
    for fw in _FRAMEWORKS:
        slash_hits = tuple(s for s in slashes if fw.matches_slash(s))
        skill_hits = tuple(s for s in skills if fw.matches_skill(s))
        if not slash_hits and not skill_hits:
            continue
        # Upgrade to "S" when at least one skill hit was also typed as a
        # slash command (the strongest user-intent signal).
        user_typed = bool(slash_hits) or any(sh in slashes_set for sh in skill_hits)
        matches.append(
            FrameworkMatch(
                framework=fw,
                level="S" if user_typed else "A",
                slash_hits=slash_hits,
                skill_hits=skill_hits,
            )
        )
    return matches


def aggregate_family(matches: list[FrameworkMatch]) -> str | None:
    """Reduce multiple matches to a single ``collab_pattern`` value.

    Rules:
    - No matches → ``None`` (no floor opinion; LLM verdict stands).
    - All matches share one family → that family.
    - Otherwise (e.g. superpowers + openspec in one session) → ``"adaptive"``.

    "adaptive" is the closed-enum value reserved for sessions where multiple
    disciplined approaches coexist, which is exactly what multi-framework
    sessions look like.
    """
    if not matches:
        return None
    families = {m.framework.family for m in matches}
    if len(families) == 1:
        return families.pop()
    return "adaptive"


def summarise_for_hint(matches: list[FrameworkMatch]) -> str:
    """Render a compact one-line summary suitable for inclusion in an LLM
    prompt as a workflow-style hint.  Empty string when there are no matches.
    """
    if not matches:
        return ""
    parts: list[str] = []
    for m in matches:
        slash_n = len(m.slash_hits)
        skill_n = len(m.skill_hits)
        bits: list[str] = []
        if slash_n:
            bits.append(f"{slash_n} slash")
        if skill_n:
            bits.append(f"{skill_n} skill")
        evidence = "+".join(bits)
        parts.append(
            f"{m.framework.name} [{m.framework.family}, {evidence}, level {m.level}]"
        )
    return "framework fingerprints: " + "; ".join(parts)
