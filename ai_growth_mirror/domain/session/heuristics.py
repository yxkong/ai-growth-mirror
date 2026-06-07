"""Domain heuristics for session enrichment and reusable asset detection."""

from __future__ import annotations

import re
from pathlib import Path

from .model import SessionRecord

CONSTRAINT_WORDS = (
    "不要",
    "don't ",
    "dont ",
    "avoid ",
    "keep ",
    "maintain ",
    "without ",
    "must not",
    "never ",
    "only if",
    "except ",
    "do not",
    "ensure ",
    "make sure",
)

CODE_CONTEXT_PATTERNS = (
    "```",
    "error:",
    "exception:",
    "traceback",
    "file:",
    "~/",
    "./",
    ".py",
    ".ts",
    ".js",
    ".go",
    ".rs",
    ".java",
    ".json",
    ".yaml",
)

WRITE_TOOL_NAMES = frozenset(
    {
        "write",
        "edit",
        "multiedit",
        "notebookedit",
        "write_bash",
        "apply_patch",
        "apply_diff",
        "write_file",
        "edit_file",
        "create_file",
        "patch",
    }
)

EXEC_TOOL_NAMES = frozenset(
    {
        "bash",
        "shell",
        "terminal",
        "run_command",
        "execute",
        "run",
        "exec",
        "command",
    }
)

TEST_PATTERNS = frozenset(
    {
        "pytest",
        "npm test",
        "npm run test",
        "jest",
        "go test",
        "cargo test",
        "make test",
        "python -m pytest",
        "rspec",
        "vitest",
        "mocha",
        "phpunit",
        "mvn test",
        "gradle test",
        "yarn test",
        "bun test",
    }
)

SUBAGENT_TOOL_NAMES = frozenset(
    {"task", "agent", "subagent", "delegate", "spawn_agent"}
)

_SKILL_FILE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/skills/[^/]+/SKILL\.md$", re.IGNORECASE),
    re.compile(r"/skills/[^/]+/skill\.yaml$", re.IGNORECASE),
    re.compile(r"/\.claude/skills/", re.IGNORECASE),
    re.compile(r"/\.claude/agents/", re.IGNORECASE),
    re.compile(r"/agents/[^/]+\.md$", re.IGNORECASE),
    re.compile(r"/\.opencode/agents?/", re.IGNORECASE),
    re.compile(r"/\.opencode/commands?/", re.IGNORECASE),
    re.compile(r"/skills/share/[^/]+/SKILL\.md$", re.IGNORECASE),
    re.compile(r"/skills/projects/[^/]+/SKILL\.md$", re.IGNORECASE),
    re.compile(r"[/\\]\.cursor[/\\]skills[/\\]", re.IGNORECASE),
    re.compile(r"[/\\]\.agents[/\\]skills[/\\]", re.IGNORECASE),
    re.compile(r"/rules/projects/[^/]+/PROJECT_RULES\.md$", re.IGNORECASE),
    re.compile(r"/prompts/projects/[^/]+/.*\.md$", re.IGNORECASE),
    re.compile(r"/prompts/share/[^/]+/.*\.md$", re.IGNORECASE),
)
_HOOK_CONFIG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/\.claude/settings(\.local)?\.json$", re.IGNORECASE),
)
_MCP_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/mcp[-_]?servers?/", re.IGNORECASE),
    re.compile(r"/\.mcp/", re.IGNORECASE),
    re.compile(r"/\.cursor/mcp\.json$", re.IGNORECASE),
    re.compile(r"/mcp\.json$", re.IGNORECASE),
)


def detect_authorship_path(
    file_path: str,
    extra_roots: tuple[Path, ...] = (),
) -> str | None:
    if not file_path:
        return None
    if extra_roots:
        normalized = file_path.replace("\\", "/")
        for root in extra_roots:
            root_str = str(root).replace("\\", "/").rstrip("/")
            if normalized.startswith(root_str + "/") or normalized == root_str:
                return "skill"
    for pattern in _SKILL_FILE_PATTERNS:
        if pattern.search(file_path):
            return "skill"
    for pattern in _HOOK_CONFIG_PATTERNS:
        if pattern.search(file_path):
            return "hook"
    for pattern in _MCP_PATH_PATTERNS:
        if pattern.search(file_path):
            return "mcp"
    return None


def enrich_prompt_signals(session: SessionRecord) -> None:
    if session.prompt_word_count > 0:
        return
    first_prompt = session.first_prompt
    if not first_prompt:
        return
    session.prompt_word_count = len(first_prompt.split())
    lower = first_prompt.lower()
    session.prompt_has_constraint = any(word in lower for word in CONSTRAINT_WORDS)
    session.prompt_has_code_context = any(
        pattern in lower for pattern in CODE_CONTEXT_PATTERNS
    )


def enrich_agentic_signals(session: SessionRecord) -> None:
    if session.autonomous_chain_lengths or not session.tool_counts:
        return

    total_calls = sum(session.tool_counts.values())
    if total_calls == 0:
        return

    tool_names = set(session.tool_counts.keys())
    n_segments = max(session.user_message_count, 1)
    avg_per_segment = total_calls // n_segments
    remainder = total_calls % n_segments
    if avg_per_segment > 0:
        chains = [avg_per_segment] * n_segments
        for index in range(remainder):
            chains[index] += 1
        session.autonomous_chain_lengths = chains

    has_write = bool(tool_names & WRITE_TOOL_NAMES)
    has_exec = bool(tool_names & EXEC_TOOL_NAMES)
    if has_write and has_exec:
        session.has_verification_behavior = True

    all_names_lower = " ".join(tool_names)
    if any(pattern in all_names_lower for pattern in TEST_PATTERNS):
        session.has_test_commands = True


# Canonical advanced-feature keys. Keep in sync with i18n keys
# `advanced_feature_<key>` in template_labels_*.yaml.
ADVANCED_FEATURE_KEYS: tuple[str, ...] = (
    "plan_mode",
    "ask_mode",
    "subagent_dispatch",
    "skill_invocation",
    "mcp_usage",
    "multi_model",
)

_PLAN_MODE_TOOLS = frozenset({"todowrite", "todo_write"})
_PLAN_MODE_TEXT_PATTERNS = ("plan mode is active", "进入计划模式", "plan mode active")
_ASK_MODE_TEXT_PATTERNS = ("ask mode is active", "ask mode active")


def enrich_advanced_features(session: SessionRecord) -> None:
    """Derive `session.advanced_features` from already-extracted signals.

    Idempotent: callers can safely run this on top of reader-specific extraction.
    Only ADDS to the existing list; never removes signals a reader detected.
    """
    existing = set(session.advanced_features or [])

    if session.uses_subagent or session.subagent_invocation_count > 0:
        existing.add("subagent_dispatch")
    if session.uses_mcp:
        existing.add("mcp_usage")
    if session.skill_invocation_count > 0 or session.unique_skills_used:
        existing.add("skill_invocation")
    if len(session.models_used or []) >= 2:
        existing.add("multi_model")

    tool_names_lower = {name.lower() for name in (session.tool_counts or {}).keys()}
    if tool_names_lower & _PLAN_MODE_TOOLS:
        existing.add("plan_mode")

    haystack: list[str] = []
    if session.first_prompt:
        haystack.append(session.first_prompt.lower())
    haystack.extend(msg.lower() for msg in (session.top_user_messages or []))
    haystack_blob = " \n ".join(haystack)
    if haystack_blob:
        if any(pat in haystack_blob for pat in _PLAN_MODE_TEXT_PATTERNS):
            existing.add("plan_mode")
        if any(pat in haystack_blob for pat in _ASK_MODE_TEXT_PATTERNS):
            existing.add("ask_mode")

    # Preserve canonical ordering for stable rendering / snapshots.
    session.advanced_features = [k for k in ADVANCED_FEATURE_KEYS if k in existing]


_QUALITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def is_indexed_prompt_session(session: SessionRecord) -> bool:
    """A session that anchors on a known skill/slash-command/rule entry.

    Such sessions are *high signal* even when they have only 1 user message —
    the user is leveraging accumulated assets rather than re-typing context.
    """
    return bool(
        session.skill_invocation_count > 0
        or session.unique_skills_used
        or session.slash_commands
    )


def classify_session_quality(session: SessionRecord) -> str:
    """Bucket a session into low/medium/high for the report quality gate.

    Indexed-prompt sessions (skill / slash invocation) are guaranteed at least
    `medium` to honor the design intent: invoking a `/delivery-workflow` once
    and getting a long AI response is *not* a low-engagement session.
    """
    output_signals = (
        session.files_modified > 0
        or session.lines_added > 0
        or session.lines_removed > 0
        or session.git_commits > 0
        or bool(session.tool_counts)
    )
    chain_depth = max(session.autonomous_chain_lengths or [0])
    indexed = is_indexed_prompt_session(session)

    # Bottom rung: nothing happened AND not an indexed call.
    if (
        session.user_message_count <= 1
        and not output_signals
        and chain_depth <= 1
        and not indexed
    ):
        return "low"

    if output_signals and (
        session.has_verification_behavior
        or session.has_test_commands
        or session.git_commits > 0
        or chain_depth >= 3
    ):
        return "high"

    return "medium"


def passes_quality_gate(session: SessionRecord, min_quality: str) -> bool:
    """Tag the session with quality_tag and check it meets the minimum bar."""
    session.quality_tag = classify_session_quality(session)
    return _QUALITY_ORDER.get(session.quality_tag, 1) >= _QUALITY_ORDER.get(
        min_quality, 1
    )


def detect_active_clarification(session: SessionRecord) -> bool:
    """Detect the "active clarification" collaboration pattern (v0.6.0 G-3).

    A session counts as active clarification when the user opens with a task,
    then in a later turn (2nd/3rd user message) adds explicit constraints/scope
    instead of repeating themselves. This is treated as a high-order intent
    signal rather than a first-turn-constraint-missing penalty.

    Shared by both the heuristic and LLM extractors so the signal is computed
    from the same rule regardless of extraction mode.
    """
    if session.user_message_count < 3:
        return False
    follow_up_messages = (session.top_user_messages or [])[1:3]
    for msg in follow_up_messages:
        if not msg:
            continue
        msg_lower = msg.lower()
        if any(word in msg_lower for word in CONSTRAINT_WORDS):
            return True
    return False
