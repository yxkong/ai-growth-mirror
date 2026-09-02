"""Canonical catalog for supported session-reader adapters and CLI aliases."""

from __future__ import annotations

from .base import BaseSessionAdapter
from .claude_code import ClaudeCodeSessionAdapter
from .cline import ClineAdapter
from .codebuddy import CodeBuddyAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .deepseek_harness import DeepSeekHarnessAdapter
from .gemini import GeminiAdapter
from .kilo import KiloAdapter
from .opencode import OpenCodeAdapter
from .qoder import QCoderAdapter
from .trae import TraeAdapter
from .zcode import ZCodeAdapter


ADAPTER_BY_NAME: dict[str, type[BaseSessionAdapter]] = {
    adapter.tool_name: adapter
    for adapter in (
        ClaudeCodeSessionAdapter,
        ClineAdapter,
        CodeBuddyAdapter,
        CodexAdapter,
        CursorAdapter,
        DeepSeekHarnessAdapter,
        GeminiAdapter,
        KiloAdapter,
        OpenCodeAdapter,
        QCoderAdapter,
        TraeAdapter,
        ZCodeAdapter,
    )
}

TOOL_ALIASES: dict[str, str] = {
    "claude": "claude_code",
    "cline": "cline",
    "codebuddy": "codebuddy",
    "codex": "codex",
    "cursor": "cursor",
    "deepseek-harness": "deepseek_harness",
    "gemini": "gemini",
    "kilo": "kilo",
    "opencode": "opencode",
    "qcoder": "qcoder",
    "qoder": "qcoder",
    "trae": "trae",
    "zcode": "zcode",
}

TOOL_CHOICES: tuple[str, ...] = ("all", *TOOL_ALIASES)


def resolve_requested_tool_names(requested: tuple[str, ...] | list[str]) -> list[str]:
    values = list(requested or ["all"])
    if "all" in values:
        return sorted(ADAPTER_BY_NAME)
    resolved: list[str] = []
    for item in values:
        tool_name = TOOL_ALIASES.get(item)
        if tool_name in ADAPTER_BY_NAME and tool_name not in resolved:
            resolved.append(tool_name)
    return resolved
