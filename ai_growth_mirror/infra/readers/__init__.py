from __future__ import annotations



from ai_growth_mirror.domain.session.model import SessionRef, SessionRecord

from ai_growth_mirror.domain.signals.model import SessionRead

from ai_growth_mirror.infra.readers.base import BaseSessionAdapter

from ai_growth_mirror.infra.readers.claude_code import ClaudeCodeSessionAdapter

from ai_growth_mirror.infra.readers.codebuddy import CodeBuddyAdapter

from ai_growth_mirror.infra.readers.codex import CodexAdapter

from ai_growth_mirror.infra.readers.cursor import CursorAdapter

from ai_growth_mirror.infra.readers.gemini import GeminiAdapter

from ai_growth_mirror.infra.readers.json_reader import JsonSessionAdapter

from ai_growth_mirror.infra.readers.qoder import QCoderAdapter

from ai_growth_mirror.infra.readers.trae import TraeAdapter



ADAPTER_BY_NAME: dict[str, type[BaseSessionAdapter]] = {

    ClaudeCodeSessionAdapter.tool_name: ClaudeCodeSessionAdapter,

    CodeBuddyAdapter.tool_name: CodeBuddyAdapter,

    CodexAdapter.tool_name: CodexAdapter,

    CursorAdapter.tool_name: CursorAdapter,

    GeminiAdapter.tool_name: GeminiAdapter,

    QCoderAdapter.tool_name: QCoderAdapter,

    TraeAdapter.tool_name: TraeAdapter,

}



__all__ = [

    "ADAPTER_BY_NAME",

    "BaseSessionAdapter",

    "ClaudeCodeSessionAdapter",

    "CodeBuddyAdapter",

    "CodexAdapter",

    "CursorAdapter",

    "GeminiAdapter",

    "JsonSessionAdapter",

    "QCoderAdapter",

    "SessionRef",

    "SessionRead",

    "SessionRecord",

    "TraeAdapter",

]
