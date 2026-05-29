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
