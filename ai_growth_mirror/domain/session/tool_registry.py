"""Domain vocabulary for AI tool selection."""

from __future__ import annotations

TOOL_ALIASES = {
    "claude": "claude_code",
    "codex": "codex",
    "cursor": "cursor",
    "qoder": "qcoder",
    "all": "all",
}

TOOL_CHOICES = ["all", "claude", "codex", "cursor", "trae", "qcoder"]


def resolve_requested_tool_names(
    requested: tuple[str, ...] | list[str],
    available_tool_names: list[str],
) -> list[str]:
    values = list(requested or ["all"])
    if "all" in values:
        return sorted(available_tool_names)

    resolved: list[str] = []
    available = set(available_tool_names)
    for item in values:
        tool_name = TOOL_ALIASES.get(item, item)
        if tool_name in available and tool_name not in resolved:
            resolved.append(tool_name)
    return resolved
