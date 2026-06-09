"""Validation-command detection rules for session readers."""

from __future__ import annotations

import re

# Keyword/suffix signals, not an exhaustive command allowlist.
TEST_PATTERNS = frozenset(
    {
        "pytest",
        "jest",
        "cargo test",
        "rspec",
        "vitest",
        "mocha",
        "phpunit",
        "bun test",
        "unittest",
        "build",
        "compile",
        "package",
        "verify",
        "check",
        "lint",
        "tsc",
        "mvn",
        "gradle",
        "cargo",
        "go test",
        "run_test",
        "run_tests",
        "run-test",
        "run-tests",
        "run_all",
        "run-all",
        ".ps1",
        ".bat",
    }
)

_VALIDATION_TOKEN_PATTERN = re.compile(
    r"(?<![a-z0-9])"
    r"(pytest|jest|vitest|mocha|phpunit|rspec|unittest|test|build|compile|package|verify|check|lint|tsc|mvn|gradle|cargo)"
    r"(?![a-z0-9])",
    re.IGNORECASE,
)
_VALIDATION_SCRIPT_SUFFIX_PATTERN = re.compile(r"\.(ps1|bat|cmd)\b", re.IGNORECASE)
_EXCLUDE_PREFIX_PATTERN = re.compile(
    r"^\s*(cat|less|more|tail|head|grep|rg|find|git\s+(diff|status|branch|log|checkout|clone|show|blame|reflog))\b",
    re.IGNORECASE,
)


def is_validation_command(command_text: str) -> bool:
    """Return whether command text looks like a verification step.

    This intentionally uses keyword/token matching instead of an exhaustive
    command allowlist, so project-specific commands keep working without
    growing `TEST_PATTERNS` for every script name.
    """
    if not command_text:
        return False
    normalized = command_text.strip().lower()
    if _EXCLUDE_PREFIX_PATTERN.search(normalized):
        return False
    if _VALIDATION_SCRIPT_SUFFIX_PATTERN.search(normalized):
        return True
    return bool(_VALIDATION_TOKEN_PATTERN.search(normalized))
