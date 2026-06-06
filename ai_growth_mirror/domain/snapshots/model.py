"""Domain contracts for snapshot archive index entries."""

from __future__ import annotations

from dataclasses import dataclass, field

CURRENT_TRAJECTORY_AXIS_KEYS = frozenset(
    {
        "intent_clarity",
        "execution_driving",
        "implementation_depth",
        "delivery_closure",
        "adaptive_recovery",
    }
)

LEGACY_TRAJECTORY_AXIS_KEYS = frozenset(
    {
        "delegation",
        "verification",
        "breadth",
        "authorship",
        "outcome",
        "workflow",
    }
)


def is_current_axis_schema(axes: dict[str, float]) -> bool:
    return CURRENT_TRAJECTORY_AXIS_KEYS.issubset(set(axes))


def has_legacy_axis_schema(axes: dict[str, float]) -> bool:
    return bool(LEGACY_TRAJECTORY_AXIS_KEYS & set(axes))


@dataclass
class SnapshotIndexEntry:
    snapshot_id: str
    created_at: str
    tool_display_name: str
    report_title: str
    date_range: str
    report_path: str
    report_json_path: str
    profile_path: str
    summary_path: str
    normalized_summary_path: str
    compare_hint: str


@dataclass
class SnapshotMeta:
    snapshot_id: str
    created_at: str
    tool_display_name: str
    report_title: str
    date_range: str


@dataclass
class SnapshotCoverage:
    session_count: int = 0
    session_read_count: int = 0
    quality_eligible: int = 0
    extraction_failed: int = 0
    has_usage_data: bool = False


@dataclass
class SnapshotPromptQuality:
    efficiency_score: float | None = None
    evaluated_sessions: int = 0
    llm_sessions: int = 0
    heuristic_sessions: int = 0
    light_sessions: int = 0
    deficits: dict[str, int] = field(default_factory=dict)


@dataclass
class SnapshotMethodAssets:
    skill_files: int = 0
    prompt_files: int = 0
    rule_files: int = 0
    total_asset_files: int = 0
    unique_skill_count: int = 0
    workflow_build_substantial_count: int = 0
    workflow_build_moderate_count: int = 0
    ai_authoring_distinct_categories: int = 0
    assetized_session_rate: float = 0.0


@dataclass
class SnapshotSource:
    snapshot_id: str = ""
    created_at: str = ""
    date_range: str = ""
    tool_display_name: str = ""
    growth_level: str = ""
    mirror_score: int = 0
    headline: str = ""
    next_focus: str = ""
    strongest_axis_key: str = ""
    weakest_axis_key: str = ""
    axis_scores: dict[str, float] = field(default_factory=dict)
    prompt_quality_dimensions: dict[str, float] = field(default_factory=dict)
    actionable_friction_counts: dict[str, int] = field(default_factory=dict)
    prompt_quality: SnapshotPromptQuality = field(default_factory=SnapshotPromptQuality)
    friction_type_counts: dict[str, int] = field(default_factory=dict)
    friction_by_attribution: dict[str, int] = field(default_factory=dict)
    method_assets: SnapshotMethodAssets = field(default_factory=SnapshotMethodAssets)
    coverage: SnapshotCoverage = field(default_factory=SnapshotCoverage)
    evidence_by_topic: dict[str, list[str]] = field(default_factory=dict)
    sample_count: int = 0
    point_confidence: str = "low"
    # human cost signal: rate of sessions requiring ≥2 user corrections
    human_intervention_session_rate: float | None = None
    action_contracts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TrajectoryPoint:
    snapshot_id: str
    generated_at: str
    date: str
    mirror_score: int
    growth_level: str
    sample_count: int
    confidence: str
    axes: dict[str, float] = field(default_factory=dict)
    prompt_quality: dict[str, float] = field(default_factory=dict)
    friction: dict[str, int] = field(default_factory=dict)
    axis_schema: str = "current"
    comparable: bool = True


@dataclass
class TrajectorySummary:
    label: str = "data_insufficient"
    explanation: str = ""
    confidence: str = "low"
    data_sufficiency: str = ""
    recent_signal: str = ""


@dataclass
class LatestChangeHighlight:
    key: str = ""
    label: str = ""
    delta: float = 0.0
    direction: str = "flat"
    explanation: str = ""


@dataclass
class PromptQualityChangeSummary:
    score_delta: float = 0.0
    direction: str = "flat"
    improved_dimensions: list[str] = field(default_factory=list)
    worsened_dimensions: list[str] = field(default_factory=list)
    source_note: str = ""
    confidence: str = "low"


@dataclass
class FrictionChangeSummary:
    total_delta: int = 0
    reduced_types: list[str] = field(default_factory=list)
    increased_types: list[str] = field(default_factory=list)
    recovery_signal: str = "flat"


@dataclass
class LatestVsPreviousSummary:
    score_delta: float = 0.0
    level_delta: int = 0
    strongest_improvement: LatestChangeHighlight = field(default_factory=LatestChangeHighlight)
    largest_regression: LatestChangeHighlight = field(default_factory=LatestChangeHighlight)
    prompt_quality_delta: PromptQualityChangeSummary = field(default_factory=PromptQualityChangeSummary)
    friction_delta: FrictionChangeSummary = field(default_factory=FrictionChangeSummary)
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class SnapshotTrajectoryWindow:
    window_days: int = 30
    window_points: list[TrajectoryPoint] = field(default_factory=list)
    daily_points: list[TrajectoryPoint] = field(default_factory=list)
    trend_summary: TrajectorySummary = field(default_factory=TrajectorySummary)
    latest_vs_previous: LatestVsPreviousSummary | None = None
    human_cost_trend: HumanCostTrend | None = None


@dataclass
class NumericDelta:
    previous: float = 0.0
    current: float = 0.0
    delta: float = 0.0
    direction: str = "flat"


@dataclass
class AxisDelta:
    key: str
    previous: float
    current: float
    delta: float
    direction: str
    weight: float
    weighted_contribution: float
    magnitude: str


@dataclass
class PromptQualityDelta:
    available: bool = False
    metric: NumericDelta = field(default_factory=NumericDelta)
    previous_llm_sessions: int = 0
    current_llm_sessions: int = 0
    previous_heuristic_sessions: int = 0
    current_heuristic_sessions: int = 0
    previous_light_sessions: int = 0
    current_light_sessions: int = 0
    improved_deficits: list[str] = field(default_factory=list)
    worsened_deficits: list[str] = field(default_factory=list)
    confidence: str = "low"


@dataclass
class FrictionTypeDelta:
    key: str
    previous_count: int
    current_count: int
    delta: int
    direction: str


@dataclass
class FrictionDelta:
    total: NumericDelta = field(default_factory=NumericDelta)
    attribution_deltas: dict[str, NumericDelta] = field(default_factory=dict)
    type_deltas: list[FrictionTypeDelta] = field(default_factory=list)
    reduced_types: list[str] = field(default_factory=list)
    increased_types: list[str] = field(default_factory=list)
    adaptive_recovery_delta: float = 0.0
    recovery_signal: str = "flat"


@dataclass
class MethodAssetDelta:
    total_assets: NumericDelta = field(default_factory=NumericDelta)
    unique_skills: NumericDelta = field(default_factory=NumericDelta)
    workflow_assets: NumericDelta = field(default_factory=NumericDelta)
    assetization_rate: NumericDelta = field(default_factory=NumericDelta)
    stronger_reuse: bool = False


@dataclass
class EvidenceCard:
    topic: str
    axis_key: str = ""
    direction: str = "flat"
    summaries: list[str] = field(default_factory=list)


@dataclass
class ConfidenceAssessment:
    level: str = "low"
    score: int = 0
    sample_size: int = 0
    has_usage_data: bool = False
    has_prompt_quality_data: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class TrainingPriority:
    axis_key: str
    priority: str
    id: str = ""
    reason_codes: list[str] = field(default_factory=list)
    supporting_topics: list[str] = field(default_factory=list)
    evidence_summaries: list[str] = field(default_factory=list)
    linked_prompt_deficit_ids: list[str] = field(default_factory=list)
    linked_template_ids: list[str] = field(default_factory=list)
    linked_rewrite_card_ids: list[str] = field(default_factory=list)


@dataclass
class HumanCostTrend:
    """Trend of human_intervention_session_rate across snapshots."""

    available: bool = False
    previous_rate: float | None = None
    current_rate: float | None = None
    delta: float = 0.0
    direction: str = "flat"  # "improving" | "worsening" | "flat" | "unknown"
    note: str = ""


@dataclass
class TrendSummary:
    direction: str = "flat"  # "improving" | "declining" | "flat"
    confidence: str = "low"  # "high" | "medium" | "low"
    score_delta: float = 0.0


@dataclass
class ContractOutcome:
    axis_key: str
    axis_label: str
    title: str
    previous_score: float | None
    current_score: float | None
    delta: float | None
    status: str              # "improved" | "partial" | "unchanged" | "no_data" | "schema_mismatch"
    confidence: str          # "high" | "medium" | "low"
    explanation: str


@dataclass
class SnapshotComparison:
    previous: SnapshotSource
    current: SnapshotSource
    score: NumericDelta = field(default_factory=NumericDelta)
    level_delta: int = 0
    overall_direction: str = "flat"
    overall_code: str = "stable"
    axis_deltas: list[AxisDelta] = field(default_factory=list)
    waterfall: list[AxisDelta] = field(default_factory=list)
    prompt_quality: PromptQualityDelta = field(default_factory=PromptQualityDelta)
    friction: FrictionDelta = field(default_factory=FrictionDelta)
    method_assets: MethodAssetDelta = field(default_factory=MethodAssetDelta)
    evidence_cards: list[EvidenceCard] = field(default_factory=list)
    confidence: ConfidenceAssessment = field(default_factory=ConfidenceAssessment)
    next_priorities: list[TrainingPriority] = field(default_factory=list)
    human_cost_trend: HumanCostTrend = field(default_factory=HumanCostTrend)
    trend_summary: TrendSummary = field(default_factory=TrendSummary)
    contract_outcomes: list[ContractOutcome] = field(default_factory=list)
