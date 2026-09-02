"""Public reader package surface derived from the canonical catalog."""

from __future__ import annotations

from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.signals.model import SessionRead

from .base import BaseSessionAdapter, SessionRef, materialize_deferred_session
from .catalog import (
    ADAPTER_BY_NAME,
    TOOL_ALIASES,
    TOOL_CHOICES,
    resolve_requested_tool_names,
)
from .claude_code import ClaudeCodeSessionAdapter
from .cline import ClineAdapter
from .codebuddy import CodeBuddyAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .deepseek_harness import DeepSeekHarnessAdapter
from .gemini import GeminiAdapter
from .json_reader import JsonSessionAdapter
from .kilo import KiloAdapter
from .opencode import OpenCodeAdapter
from .qoder import QCoderAdapter
from .trae import TraeAdapter
from .zcode import ZCodeAdapter

__all__ = [
    "ADAPTER_BY_NAME",
    "TOOL_ALIASES",
    "TOOL_CHOICES",
    "resolve_requested_tool_names",
    "BaseSessionAdapter",
    "ClaudeCodeSessionAdapter",
    "ClineAdapter",
    "CodeBuddyAdapter",
    "CodexAdapter",
    "CursorAdapter",
    "DeepSeekHarnessAdapter",
    "GeminiAdapter",
    "JsonSessionAdapter",
    "KiloAdapter",
    "materialize_deferred_session",
    "OpenCodeAdapter",
    "QCoderAdapter",
    "SessionRef",
    "SessionRead",
    "SessionRecord",
    "TraeAdapter",
    "ZCodeAdapter",
]
