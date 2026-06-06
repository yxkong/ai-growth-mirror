"""Growth domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

@dataclass
class AgentAssetStats:
    """Snapshot of the user's AI asset library within the requested time window."""

    skill_files_count: int = 0
    prompt_files_count: int = 0
    rule_files_count: int = 0
    # Relative asset paths modified within the analysis window (capped at 20)
    recently_modified_assets: list[str] = field(default_factory=list)
    # Sub-project keys found under skills/projects/ or prompts/projects/ dirs
    hub_project_keys: list[str] = field(default_factory=list)
    # Total asset files across all roots
    total_asset_files: int = 0
    # Number of roots that were scanned successfully
    roots_scanned: int = 0
    # Local/private method framework names discovered from configured hub roots
    # or supplied directly via report.local_method_frameworks. Inventory alone is
    # not evidence; these names only affect scoring when matched in sessions.
    local_method_frameworks: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.total_asset_files > 0 or self.roots_scanned > 0 or bool(self.local_method_frameworks)


@dataclass
class RadarAxis:
    key: str
    label: str
    score: float
    status: str
    short_reason: str = ""
    confidence: float = 0.0
    has_data: bool = True


@dataclass
class GrowthGap:
    key: str
    label: str
    severity: float
    rank: int
    evidence_summary: str = ""
    why_it_happens: str = ""
    suggested_action: str = ""


@dataclass
class GrowthStage:
    level: str
    label: str
    summary: str
    strongest_axis: str = ""
    primary_gap: str = ""
    next_breakthrough: str = ""


@dataclass
class GrowthProfile:
    tool_name: str           # "all" for multi-tool, or specific tool name
    session_count: int = 0
    total_messages: int = 0
    total_user_messages: int = 0
    total_files_modified: int = 0
    active_days: int = 0

    # Tool usage
    top_tools: list[tuple[str, int]] = field(default_factory=list)

    # Languages
    top_languages: list[tuple[str, int]] = field(default_factory=list)

    # Projects (derived from project_path last segment)
    top_projects: list[tuple[str, int]] = field(default_factory=list)

    # Goal categories
    goal_category_counts: dict[str, int] = field(default_factory=dict)

    # Outcomes
    outcome_counts: dict[str, int] = field(default_factory=dict)
    # Weighted outcome score rate: fully(1.0) + mostly(0.7) + partially(0.3).
    # Computed from session reads in aggregate(); stored here so view layer can display
    # without re-computing. Value is 0.0 when no analyzed reads exist.
    fully_achieved_rate: float = 0.0

    # Friction (derived from SessionRead.resistance_signals).
    # `friction_type_counts` aggregates by canonical category for narrative
    # input; `friction_by_attribution` splits by attribution
    # (user-actionable / ai-capability / environmental).
    friction_type_counts: dict[str, int] = field(default_factory=dict)
    friction_by_attribution: dict[str, int] = field(default_factory=dict)

    # Time of day (hour 0-23 → message count)
    messages_by_hour: list[int] = field(default_factory=lambda: [0] * 24)

    # Tool errors
    tool_error_counts: dict[str, int] = field(default_factory=dict)

    # ── Prompt quality (v2.3+) ───────────────────────────────────────────────
    # Populated across the full analyzed session-read set. Semantic LLM judgements
    # and heuristic proxy fallbacks are both tracked so the report can explain
    # where the current PQ picture came from.
    pq_sessions_evaluated: int = 0
    pq_llm_session_count: int = 0
    pq_heuristic_session_count: int = 0
    pq_light_session_count: int = 0
    pq_llm_evaluated_count: int = 0
    pq_insufficient_count: int = 0
    pq_llm_failed_count: int = 0
    pq_llm_unavailable_count: int = 0
    pq_avg_dimensions: dict[str, float] = field(default_factory=dict)
    pq_avg_efficiency_score: float = 0.0
    pq_deficit_counts: dict[str, int] = field(default_factory=dict)
    # Up to 4 top takeaways sampled across sessions for the report card.
    # Ordered improve-first then reinforce, then by descending impact.
    pq_top_takeaways: list = field(default_factory=list)

    active_clarification_count: int = 0
    active_clarification_rate: float = 0.0

    # ── Enhanced behavioral metrics ──────────────────────────────────────────

    # Cost (dollar estimate — may be inaccurate for non-Claude tools)
    total_cost_usd: float = 0.0
    avg_cost_per_session: float = 0.0

    # Tokens (authoritative across all tools that record token usage)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0

    # Cache efficiency (Claude Code only; None for tools without cache tokens)
    avg_cache_hit_rate: Optional[float] = None

    # Collaboration rhythm (derived from session clustering within a day)
    # burst: multiple short sessions / day; deep_focus: long single sessions; balanced: mix
    collaboration_rhythm_type: str = ""

    # Weekday distribution (0=Mon … 6=Sun → session count)
    weekday_session_counts: list[int] = field(default_factory=lambda: [0] * 7)

    # Skill signals
    # unique tool types / total tool calls (0–1); higher = broader tool repertoire
    tool_diversity_index: float = 0.0
    # fraction of sessions that used MCP, subagent, or web tools
    advanced_feature_ratio: float = 0.0
    # fraction of sessions that produced at least one commit
    commit_rate: float = 0.0
    # average session duration in minutes
    avg_session_duration_minutes: float = 0.0
    # Median is more robust to long-tail outliers (e.g. resumed sessions whose
    # JSONL keeps growing for days) and is the value displayed/used downstream.
    # Mean is retained as a secondary aggregate.
    median_session_duration_minutes: float = 0.0

    # ── Collaboration execution signals ────────────────────────────────────────

    # Autonomous execution depth: avg / max tool calls between consecutive human-text messages
    avg_autonomous_chain_length: float = 0.0
    max_autonomous_chain_length: int = 0

    # Delivery verification: fraction of sessions with write/edit → any bash in same chain
    verification_behavior_rate: float = 0.0

    # Testing: fraction of sessions that ran a test runner command (informational only)
    test_run_rate: float = 0.0

    # Heavy-tool sessions: fraction where AI ran ≥15 tool calls total
    # (captures single-chain deep autonomous runs, not just multi-turn back-and-forth)
    heavy_session_rate: float = 0.0
    # Absolute count alongside rate — a heavy user with many sessions and 30%
    # heavy rate did more autonomous execution than a light user with few
    # sessions and 60% rate; rate alone hides that difference.
    heavy_session_count: int = 0

    # Subagent usage: fraction of sessions that spawned subagents
    # (used to compensate chain length underestimation in parent sessions)
    subagent_session_rate: float = 0.0
    # Orchestration depth signals.  total_subagent_invocations counts actual
    # subagent runs across all sessions (5 sequential Task calls in 1 session = 5,
    # not 1); subagent_session_count is the absolute count of sessions using any subagent.
    subagent_session_count: int = 0
    total_subagent_invocations: int = 0

    # Decomposed specialty rates: each rate is 0-1 so a session-rich user is not
    # penalized when only a fraction of their sessions touch any one specialty.
    # Agentic scoring credits each independently.
    mcp_session_rate: float = 0.0
    mcp_session_count: int = 0
    web_session_rate: float = 0.0  # web_search OR web_fetch (still grouped — same intent)
    web_session_count: int = 0

    # Reusable asset creation signals.  Tracking absolute counts because asset
    # creation is rare and "1 skill written" is qualitatively different from "0".
    skill_authored_count: int = 0           # total distinct skill files authored
    hook_modified_session_count: int = 0    # # sessions that modified hook config
    mcp_authored_session_count: int = 0     # # sessions that touched MCP code/config

    # Tool capability breadth: how many distinct capability tiers (of ~11) were used.
    # More stable than raw tool count which inflates with MCP tool variety.
    tier_diversity_count: int = 0

    # Tool / model ecosystem diversity signals.
    # distinct_tool_count: # of distinct AI CLI products used in the window
    # (e.g. claude_code + codex + opencode = 3).  For tool-specific reports
    # this is always 1.
    distinct_tool_count: int = 0
    # distinct_model_count: # of distinct LLM models invoked across all
    # sessions (e.g. opus + sonnet + haiku = 3).  Captures model-selection
    # sophistication.
    distinct_model_count: int = 0
    # total_token_volume: sum of input + output + cache_read + cache_write
    # across all sessions.  Full caliber (includes cached reads) — high
    # consumption strongly correlates with AI proficiency; abuse detection
    # is an orthogonal anti-fraud concern, not a reason to under-count.
    total_token_volume: int = 0

    # AI capability creation (LLM-derived from session summary).  Counts sessions
    # where the user created reusable AI assets (skill / agent / workflow / MCP
    # server) rather than merely using AI for ordinary tasks.
    workflow_build_substantial_count: int = 0
    workflow_build_moderate_count: int = 0
    # # of distinct non-"none" ai_authoring_category values observed
    # (e.g. authored a skill + an mcp server = 2 distinct categories).
    ai_authoring_distinct_categories: int = 0

    # Structured collaboration signals, counted from SessionRead.work_style.
    # `structured` is the union {plan_driven, spec_driven, tdd, adaptive}
    # — used by scoring.  Per-style counts are informational.
    workflow_structured_session_count: int = 0
    workflow_plan_session_count: int = 0
    workflow_spec_session_count: int = 0
    workflow_tdd_session_count: int = 0
    workflow_vibe_session_count: int = 0
    # Detected public workflow frameworks (name, session_count) top-8.
    # Populated from SessionRecord.slash_commands + unique_skills_used.
    top_workflow_frameworks: list[tuple[str, int]] = field(default_factory=list)
    # Detected local/private method frameworks (name, session_count) top-8.
    # Names come from report.local_method_frameworks + local hub extraction.
    top_local_method_frameworks: list[tuple[str, int]] = field(default_factory=list)
    advanced_feature_counts: dict[str, int] = field(default_factory=dict)
    skill_usage_session_rate: float = 0.0
    public_framework_session_rate: float = 0.0
    local_method_framework_session_rate: float = 0.0
    workflow_fingerprint_session_rate: float = 0.0
    workflow_reuse_depth: int = 0
    asset_authoring_session_rate: float = 0.0
    human_intervention_session_count: int = 0
    human_intervention_session_rate: float = 0.0
    agentic_system_score: float = 0.0

    # Prompt quality (informational — not scored, context-dependent)
    constraint_prompt_rate: float = 0.0
    code_context_rate: float = 0.0  # fraction with file paths / code / errors in first prompt
    # Average word count of opening prompts
    avg_prompt_word_count: float = 0.0

    # Skill / workflow automation. Usage signals are stronger than inventory:
    # a large local skill library is context, but repeated runtime use is what
    # can lift the agentic system maturity.
    tool_build_rate: float = 0.0          # fraction of sessions with ≥1 Skill tool call
    unique_skill_count: int = 0
    assetized_session_rate: float = 0.0      # sessions that reused or authored reusable AI assets

    # Task-type segmentation for delivery-closure scoring.
    # Code sessions: at least one code-language file touched (Python/TS/JS/Go/Rust/…)
    code_session_count: int = 0
    # Delivery verification rate among code sessions only (write/edit → any bash in same chain)
    code_verification_rate: float = 0.0

    # Aggregated growth level (L1–L5) and mirror score (0–100).
    # Level boundaries: L1 0-37 / L2 38-55 / L3 56-74 / L4 75-89 / L5 90-100 (see scorer._LEVEL_MIN_SCORE).
    growth_level: str = ""
    mirror_score: int = 0
    # Per-axis sub-scores. Keys: intent_clarity / execution_driving /
    # implementation_depth / delivery_closure / adaptive_recovery. Values are
    # floats (pre-round) and drive the report capability section.
    agentic_sub_scores: dict[str, float] = field(default_factory=dict)
    radar_axes: list[RadarAxis] = field(default_factory=list)
    gap_rankings: list[GrowthGap] = field(default_factory=list)
    growth_stage: Optional[GrowthStage] = None

    # Optional: AI asset footprint from user-configured asset roots.
    # Populated by service layer when --asset-root / config.report.asset_roots
    # is provided; None when no roots were configured or scanning was skipped.
    agent_asset: Optional[AgentAssetStats] = None
