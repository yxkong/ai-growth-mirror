"""Session domain models — SessionRef and SessionRecord."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from ..cache_schema import RECORD_SCHEMA_VERSION

@dataclass
class SessionRef:
    """Lightweight session handle used for lazy loading and date filtering.

    `source_mtime` is a **content revision stamp** (not a calendar TTL): per-file
    ``stat().st_mtime`` for single-session logs, or a per-session timestamp when
    many sessions share one store (e.g. Cursor DB ``updatedAt``).  The cache
    layer invalidates only when this stamp moves forward.  Defaults to 0.0.
    """
    session_id: str
    tool_name: str
    start_time: datetime
    source_paths: list[Path]
    source_mtime: float = 0.0


@dataclass
class SessionRecord:
    """
    Normalized session metadata produced by every adapter.
    Fields unavailable for a given tool are None (never omitted).
    Serialized to `{cache_dir}/records/{tool_name}/{session_id}.json` (default under `.ai-growth-mirror-runtime/cache/`).
    """
    SCHEMA_VERSION: str = field(default=RECORD_SCHEMA_VERSION, init=False, repr=False)

    # Identity
    session_id: str = ""
    tool_name: str = ""           # "claude_code" | "gemini_cli" | "codex" | "opencode" | "copilot"
    tool_version: Optional[str] = None

    # Location
    project_path: str = ""
    git_branch: Optional[str] = None
    git_origin_url: Optional[str] = None

    # Timing
    start_time: str = ""          # ISO 8601
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None

    # Content
    first_prompt: str = ""
    user_message_count: int = 0
    assistant_message_count: int = 0

    # Invocation source — how the session was started.
    # Claude Code: "cli" (interactive terminal), "sdk-cli" / "sdk-ts" / "sdk-py"
    # (scripted / Agent SDK / headless), "" (unknown / older versions).
    # Other tools: "" (not yet populated).
    entrypoint: str = ""

    # Tools (raw counts from source + normalized tier counts)
    tool_counts: dict[str, int] = field(default_factory=dict)
    tool_tier_counts: dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    tool_error_categories: dict[str, int] = field(default_factory=dict)

    # Tokens (None means unavailable for this tool)
    # tokens_estimated=True means the values are heuristic estimates (e.g. Gemini),
    # not real API usage. Such sessions are excluded from token/cost aggregation.
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    tokens_estimated: bool = False

    # Code changes
    lines_added: int = 0
    lines_removed: int = 0
    files_modified: int = 0
    git_commits: int = 0
    git_pushes: int = 0

    # Languages (file extensions touched)
    languages: dict[str, int] = field(default_factory=dict)

    # Behavior
    user_interruptions: int = 0
    user_response_times: list[float] = field(default_factory=list)   # seconds
    message_hours: list[int] = field(default_factory=list)           # 0-23
    user_message_timestamps: list[str] = field(default_factory=list) # ISO 8601

    # Capability flags (None = unknown / not applicable)
    uses_subagent: Optional[bool] = None
    uses_mcp: Optional[bool] = None
    uses_web_search: Optional[bool] = None
    uses_web_fetch: Optional[bool] = None

    # Models
    models_used: list[str] = field(default_factory=list)

    # Rich content: top N user messages (populated by adapters that support it)
    top_user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)

    # Agentic working signals
    autonomous_chain_lengths: list[int] = field(default_factory=list)  # tool calls between human-text msgs
    has_verification_behavior: bool = False   # write/edit followed by any bash in same chain
    has_test_commands: bool = False           # bash with pytest/jest/etc. (informational only)
    prompt_word_count: int = 0               # word count of first user message
    prompt_has_constraint: bool = False      # first prompt contains constraint language (informational only)
    prompt_has_code_context: bool = False    # first prompt contains file paths / code / error snippets

    # Effective Task Contract signals (v1.0.0).
    # These distinguish "the user did not type every requirement" from
    # "a rule/skill/workflow/agent created the task contract before execution".
    task_contract_sources: list[str] = field(default_factory=list)
    pre_execution_contract_present: bool = False
    acceptance_contract_source: str = "unknown"
    boundary_contract_source: str = "unknown"
    validation_contract_source: str = "unknown"
    late_contract_correction: bool = False
    agent_contract_compliance: str = "unknown"  # met | partial | missing | unknown
    pre_write_read_count: int = 0
    pre_write_non_read_tool_count: int = 0

    # Skill / workflow automation signals
    # Detected from Skill tool_use blocks in assistant messages (the only reliable source).
    # Does NOT include /command-style manual triggers that were never routed through the Skill tool.
    skill_invocation_count: int = 0          # total Skill tool calls in the session
    unique_skills_used: list[str] = field(default_factory=list)  # distinct skill names (informational)

    # Workflow signals captured from system-injected user messages.
    # Slash commands are explicit user decisions like /plan, /compact, /model.
    # They reveal "deliberate workflow choices" that aren't visible in tool
    # calls and feed both attribution (user-driven patterns) and PQ scoring.
    slash_commands: list[str] = field(default_factory=list)  # canonical command names, in order
    # Higher-level collaboration features observed in the raw session.
    # Examples: explicit plan mode, skill invocation, subagent dispatch,
    # MCP usage, multi-model switching.
    advanced_features: list[str] = field(default_factory=list)
    # Compact events: /compact is user-initiated; auto-compact is triggered
    # automatically when context is about to overflow. Distinguishing them
    # tells "session pressure" from "user steering".
    compact_count: int = 0
    auto_compact_count: int = 0

    # Quality gate for report inclusion. Filled by extraction/orchestration
    # helpers, not directly by raw adapters.
    quality_tag: str = "medium"

    # Authorship & orchestration signals. Detected from Edit/Write tool calls
    # to specific file paths, NOT from any specific tool brand (so manual editor
    # changes routed through Claude Code's Edit tool count the same as anything else).
    skill_files_authored: int = 0           # # distinct skill files created/edited
    hook_config_modified: bool = False      # touched .claude/settings*.json with "hooks" key
    mcp_server_authored: bool = False       # touched mcp server config or implementation
    # Total count of subagent (task/agent) invocations — distinct from the
    # boolean uses_subagent flag; "5 sequential delegations" looks different
    # from "1 delegation" in our scoring.  Computed during JSONL parsing.
    subagent_invocation_count: int = 0
    turns_until_first_file_write: Optional[int] = None

    # Data provenance — set by BaseSessionAdapter.iter_sessions(); not persisted to cache (always re-derived)
    source_machine: str = "local"            # always local in current product scope

    # v2.3+: max(stat().st_mtime) across source_paths at parse time.  Used by
    # CacheStore.load_*_if_fresh to invalidate cached entries when the source
    # JSONL has grown (session resumed, new turns appended).  0.0 means
    # "unknown / never set" — cache layer treats as always stale.
    _source_mtime: float = 0.0

    # Transient fields for lazy parsing (never cached, never serialized)
    _is_placeholder: bool = field(default=False, init=False, repr=False)
    _raw_ref: Optional[Any] = field(default=None, init=False, repr=False)
    _adapter: Optional[Any] = field(default=None, init=False, repr=False)

    def ensure_parsed(self, cache: Optional[Any] = None) -> None:
        if not self._is_placeholder:
            return
        if self._adapter is None or self._raw_ref is None:
            return
        real_record = self._adapter.parse_session(self._raw_ref)
        for k, v in real_record.__dict__.items():
            if k not in ("_is_placeholder", "_raw_ref", "_adapter"):
                setattr(self, k, v)
        self._is_placeholder = False
        self._adapter._enrich_prompt_signals(self)
        self._adapter._enrich_agentic_signals(self)
        self._adapter._enrich_advanced_features(self)
        self._adapter._enrich_task_contract_signals(self)
        if cache is not None:
            try:
                cache.write_record(self)
            except Exception:
                pass

    def to_dict(self) -> dict:
        d = asdict(self)
        d["SCHEMA_VERSION"] = self.SCHEMA_VERSION
        d.pop("source_machine", None)  # transient — re-derived at runtime, never cached
        d.pop("_is_placeholder", None)
        d.pop("_raw_ref", None)
        d.pop("_adapter", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        d = {k: v for k, v in d.items() if k not in {"SCHEMA_VERSION", "_is_placeholder", "_raw_ref", "_adapter"}}
        return cls(**d)
