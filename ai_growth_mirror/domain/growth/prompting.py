"""Pure prompt-style and closure-guidance rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..signals.framework import detect_frameworks, framework_display_name
from ..session.model import SessionRecord
from ..signals.model import SessionRead

PROMPT_STYLE_TYPES = (
    "explicit_requirement_prompt",
    "indexed_prompt",
    "mixed_prompt",
    "under_specified_prompt",
)

TASK_TYPE_CLOSURE_MAP: dict[str, tuple[str, ...]] = {
    "code_change": ("test", "smoke", "schema_validation"),
    "config_or_prompt_change": ("golden_case", "before_after", "example_replay"),
    "design_or_requirements": ("checklist", "fact_alignment", "manual_review"),
    "writing_or_content": ("manual_review", "before_after", "fact_alignment"),
    "exploration_or_analysis": ("fact_alignment", "manual_review", "user_acceptance"),
}

OPEN_ENDED_TASK_TYPES = frozenset({
    "design_or_requirements",
    "exploration_or_analysis",
    "writing_or_content",
})
ENGINEERED_TASK_TYPES = frozenset({
    "code_change",
    "config_or_prompt_change",
})

_INDEX_TERMS = (
    "agents.md",
    "claude.md",
    "project_rules.md",
    "cursor rule",
    "cursor rules",
    ".cursor/rules",
    "instructions",
    "rules",
    "workflow",
    "skill",
    "requirements_design",
    "code_review",
    "delivery_review",
    "architecture_review",
    "bug_triage",
)

_EXPLICIT_MARKERS = (
    "背景",
    "当前问题",
    "目标结果",
    "约束",
    "验收",
    "输出格式",
    "相关文件",
    "参考材料",
    "background",
    "current problem",
    "goal",
    "constraint",
    "acceptance",
    "output format",
    "reference",
)

_TASK_VARIABLE_TERMS = (
    "基于",
    "围绕",
    "针对",
    "对象",
    "输入材料",
    "目标结果",
    "验收标准",
    "收口方式",
    "输出格式",
    "边界场景",
    "重点考虑",
    "重点关注",
    "现象",
    "根因",
    "模块",
    "文件",
    "路径",
    "接口",
    "错误",
    "phase",
    "module",
    "file",
    "input materials",
    "target result",
    "closure method",
    "output format",
    "acceptance",
    "acceptance criteria",
    "focus on",
    "based on",
)

_CODE_CHANGE_TERMS = (
    "bug",
    "fix",
    "接口",
    "api",
    "代码",
    "实现",
    "测试",
    "回归",
    "schema",
    ".py",
    ".ts",
    ".java",
)

_CONFIG_PROMPT_TERMS = (
    "prompt",
    "template",
    "模板",
    "agents.md",
    "rules",
    "skill",
    "workflow",
    "配置",
    "instruction",
)

_DESIGN_TERMS = (
    "需求",
    "设计",
    "方案",
    "架构",
    "requirements",
    "architecture",
    "design",
    "adr",
)

_WRITING_TERMS = (
    "文案",
    "文章",
    "简历",
    "报告文案",
    "copy",
    "content",
    "resume",
)

_ANALYSIS_TERMS = (
    "分析",
    "调研",
    "诊断",
    "比较",
    "探索",
    "analysis",
    "research",
    "exploration",
)


@dataclass
class PromptStyleSignal:
    prompt_style: str = "under_specified_prompt"
    trigger_terms: list[str] = field(default_factory=list)
    rule_refs: list[str] = field(default_factory=list)
    skill_refs: list[str] = field(default_factory=list)
    slash_refs: list[str] = field(default_factory=list)
    framework_refs: list[str] = field(default_factory=list)
    task_variables_present: bool = False
    explicit_requirement_markers: int = 0
    repeated_trigger_usage: bool = False
    stable_trigger: bool = False
    has_rule_anchor: bool = False
    ai_rule_resolution: bool = False


@dataclass
class TriggerMaturitySignal:
    stability: str = "light"
    rule_support: str = "light"
    retrievability: str = "light"
    variable_completion: str = "missing"
    assetization: str = "light"


@dataclass
class ClosureGuidanceSignal:
    task_type: str = "exploration_or_analysis"
    mode: str = "engineered"
    expected_closure_methods: list[str] = field(default_factory=list)
    missing_closure_methods: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class FrictionSynthesisIntent:
    id: str
    pattern_key: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: int = 60


def assess_prompt_style(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
) -> tuple[PromptStyleSignal, TriggerMaturitySignal]:
    rows = [_classify_prompt(session, _read_by_id(session_reads).get(session.session_id)) for session in sessions]
    if not rows:
        return PromptStyleSignal(), TriggerMaturitySignal()

    style_scores: dict[str, int] = {key: 0 for key in PROMPT_STYLE_TYPES}
    trigger_terms: list[str] = []
    rule_refs: list[str] = []
    skill_refs: list[str] = []
    slash_refs: list[str] = []
    framework_refs: list[str] = []
    task_variables_present = False
    explicit_markers = 0
    repeated_trigger_count = 0
    stable_trigger_count = 0
    ai_rule_resolution = False
    for row in rows:
        style_scores[row.prompt_style] = style_scores.get(row.prompt_style, 0) + _style_weight(row.prompt_style)
        trigger_terms.extend(row.trigger_terms)
        rule_refs.extend(row.rule_refs)
        skill_refs.extend(row.skill_refs)
        slash_refs.extend(row.slash_refs)
        framework_refs.extend(row.framework_refs)
        task_variables_present = task_variables_present or row.task_variables_present
        explicit_markers = max(explicit_markers, row.explicit_requirement_markers)
        repeated_trigger_count += 1 if row.repeated_trigger_usage else 0
        stable_trigger_count += 1 if row.stable_trigger else 0
        ai_rule_resolution = ai_rule_resolution or row.ai_rule_resolution

    prompt_style = max(
        PROMPT_STYLE_TYPES,
        key=lambda key: (style_scores.get(key, 0), -PROMPT_STYLE_TYPES.index(key)),
    )
    deduped_terms = _dedupe_preserve(trigger_terms)[:6]
    deduped_refs = _dedupe_preserve(rule_refs)[:4]
    style_signal = PromptStyleSignal(
        prompt_style=prompt_style,
        trigger_terms=deduped_terms,
        rule_refs=deduped_refs,
        skill_refs=_dedupe_preserve(skill_refs)[:4],
        slash_refs=_dedupe_preserve(slash_refs)[:4],
        framework_refs=_dedupe_preserve(framework_refs)[:4],
        task_variables_present=task_variables_present,
        explicit_requirement_markers=explicit_markers,
        repeated_trigger_usage=repeated_trigger_count >= 2,
        stable_trigger=stable_trigger_count >= 2 or (
            prompt_style in {"indexed_prompt", "mixed_prompt"}
            and bool(deduped_terms or skill_refs or slash_refs or framework_refs)
        ),
        has_rule_anchor=bool(deduped_refs or deduped_terms or skill_refs or slash_refs or framework_refs),
        ai_rule_resolution=ai_rule_resolution,
    )
    return style_signal, _trigger_maturity(style_signal)


def assess_closure_guidance(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
) -> ClosureGuidanceSignal:
    dominant_task_type, evidence = infer_task_type(sessions, session_reads)
    expected = list(TASK_TYPE_CLOSURE_MAP.get(dominant_task_type, TASK_TYPE_CLOSURE_MAP["exploration_or_analysis"]))
    observed = _observed_closure_methods(sessions, session_reads, dominant_task_type)
    missing = [item for item in expected if item not in observed]
    if dominant_task_type in {"design_or_requirements", "writing_or_content", "exploration_or_analysis"}:
        missing = [item for item in missing if item != "test"]
    mode = "open_ended" if dominant_task_type in OPEN_ENDED_TASK_TYPES else "engineered"
    return ClosureGuidanceSignal(
        task_type=dominant_task_type,
        mode=mode,
        expected_closure_methods=expected,
        missing_closure_methods=missing[:3],
        evidence=evidence[:4],
    )


def infer_task_type(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
) -> tuple[str, list[str]]:
    read_by_id = _read_by_id(session_reads)
    scores = {
        "code_change": 0,
        "config_or_prompt_change": 0,
        "design_or_requirements": 0,
        "writing_or_content": 0,
        "exploration_or_analysis": 0,
    }
    evidence: list[str] = []
    for session in sessions:
        text = _session_text(session)
        lower = text.lower()
        read = read_by_id.get(session.session_id)
        if _contains_any(lower, _CONFIG_PROMPT_TERMS):
            scores["config_or_prompt_change"] += 3
            evidence.append("prompt_or_rule_change")
        if _contains_any(lower, _DESIGN_TERMS):
            scores["design_or_requirements"] += 3
            evidence.append("design_or_requirements")
        if _contains_any(lower, _WRITING_TERMS):
            scores["writing_or_content"] += 3
            evidence.append("writing_or_content")
        if _contains_any(lower, _ANALYSIS_TERMS):
            scores["exploration_or_analysis"] += 2
            evidence.append("analysis_or_exploration")
        if _contains_any(lower, _CODE_CHANGE_TERMS) or session.prompt_has_code_context:
            scores["code_change"] += 4
            evidence.append("code_or_bug_change")
        if read:
            mix = read.work_intent_mix or {}
            scores["code_change"] += 2 * int(bool(mix.get("fix_bug") or mix.get("implement_feature") or mix.get("refactor_code")))
            scores["design_or_requirements"] += 2 * int(bool(mix.get("design_solution") or mix.get("define_requirement")))
            scores["writing_or_content"] += 2 * int(bool(mix.get("write_content") or mix.get("polish_copy")))
            scores["exploration_or_analysis"] += 2 * int(bool(mix.get("explore") or mix.get("analysis")))

    ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    task_type = ranked[0][0] if ranked and ranked[0][1] > 0 else "exploration_or_analysis"
    return task_type, _dedupe_preserve(evidence)


def build_friction_synthesis_intents(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    prompt_style_signal: PromptStyleSignal,
    closure_signal: ClosureGuidanceSignal,
    top_deficit_keys: list[str],
    stats: object,
) -> list[FrictionSynthesisIntent]:
    """Rank friction synthesis patterns; at most two intents with evidence refs."""
    del sessions, session_reads, stats  # reserved for future session-level evidence
    intents: list[FrictionSynthesisIntent] = []

    def _append(pattern_key: str, evidence_refs: list[str]) -> None:
        if len(intents) >= 2:
            return
        refs = _dedupe_preserve([ref for ref in evidence_refs if ref])[:4]
        if not refs:
            return
        hit_count = len(refs)
        confidence = min(90, max(60, 60 + 10 * (hit_count - 1)))
        intents.append(
            FrictionSynthesisIntent(
                id=f"friction:{pattern_key}",
                pattern_key=pattern_key,
                evidence_refs=refs,
                confidence=confidence,
            )
        )

    if prompt_style_signal.prompt_style == "indexed_prompt":
        matching = [key for key in ("missing-context", "vague-request") if key in top_deficit_keys]
        if matching:
            _append("indexed_but_unfront", [f"deficit:{key}" for key in matching])

    if closure_signal.missing_closure_methods:
        refs = [f"closure:{method}" for method in closure_signal.missing_closure_methods[:2]]
        refs.extend(closure_signal.evidence[:2])
        _append("closure_mismatch", refs)

    if prompt_style_signal.prompt_style == "under_specified_prompt":
        refs = [f"deficit:{top_deficit_keys[0]}"] if top_deficit_keys else ["style:under_specified_prompt"]
        _append("under_specified", refs)

    if "missing-acceptance-criteria" in top_deficit_keys:
        _append("acceptance_gap", ["deficit:missing-acceptance-criteria"])

    if top_deficit_keys:
        _append("general_focus", [f"deficit:{top_deficit_keys[0]}"])

    return intents


def _classify_prompt(session: SessionRecord, read: SessionRead | None) -> PromptStyleSignal:
    text = _session_text(session)
    lower = text.lower()
    trigger_terms = _extract_trigger_terms(lower)
    rule_refs = _extract_rule_refs(lower)
    skill_refs = [skill for skill in (session.unique_skills_used or []) if skill][:4]
    slash_refs = [command.lstrip("/") for command in (session.slash_commands or []) if command][:4]
    framework_refs = [
        framework_display_name(match.framework.name)
        for match in detect_frameworks(session)
    ][:4]
    explicit_markers = sum(1 for marker in _EXPLICIT_MARKERS if marker in lower)
    task_variables_present = _has_task_variables(lower, session)
    repeated_trigger_usage = bool(trigger_terms or skill_refs or slash_refs or framework_refs)
    ai_rule_resolution = bool(
        session.skill_invocation_count > 0
        or session.unique_skills_used
        or session.slash_commands
        or framework_refs
        or (read and read.work_style in {"spec_driven", "method_guided", "adaptive"})
    )
    stable_trigger = bool(
        (trigger_terms or skill_refs or slash_refs or framework_refs)
        and (session.prompt_word_count <= 40 or ai_rule_resolution)
    )
    indexed = bool(trigger_terms or rule_refs or skill_refs or slash_refs or framework_refs or ai_rule_resolution)
    explicit = explicit_markers >= 3 or (
        session.prompt_has_constraint and session.prompt_word_count >= 20 and task_variables_present
    )

    if indexed and task_variables_present:
        prompt_style = "mixed_prompt"
    elif indexed:
        prompt_style = "indexed_prompt"
    elif explicit:
        prompt_style = "explicit_requirement_prompt"
    else:
        prompt_style = "under_specified_prompt"
    return PromptStyleSignal(
        prompt_style=prompt_style,
        trigger_terms=trigger_terms,
        rule_refs=rule_refs,
        skill_refs=skill_refs,
        slash_refs=slash_refs,
        framework_refs=framework_refs,
        task_variables_present=task_variables_present,
        explicit_requirement_markers=explicit_markers,
        repeated_trigger_usage=repeated_trigger_usage,
        stable_trigger=stable_trigger,
        has_rule_anchor=bool(trigger_terms or rule_refs),
        ai_rule_resolution=ai_rule_resolution,
    )


def _trigger_maturity(style: PromptStyleSignal) -> TriggerMaturitySignal:
    return TriggerMaturitySignal(
        stability="stable" if style.stable_trigger else ("emerging" if style.repeated_trigger_usage else "light"),
        rule_support="supported" if style.has_rule_anchor else "light",
        retrievability="clear" if style.ai_rule_resolution else ("likely" if style.has_rule_anchor else "unclear"),
        variable_completion="complete" if style.task_variables_present else "missing",
        assetization="strong" if style.trigger_terms and style.has_rule_anchor else ("emerging" if style.trigger_terms else "light"),
    )


def _style_weight(prompt_style: str) -> int:
    return {
        "mixed_prompt": 4,
        "indexed_prompt": 3,
        "explicit_requirement_prompt": 2,
        "under_specified_prompt": 1,
    }.get(prompt_style, 0)


def _read_by_id(session_reads: list[SessionRead]) -> dict[str, SessionRead]:
    return {item.session_id: item for item in session_reads}


def _session_text(session: SessionRecord) -> str:
    parts = [session.first_prompt, *session.top_user_messages[:2]]
    return "\n".join(part for part in parts if part).strip()


def _extract_trigger_terms(lower: str) -> list[str]:
    terms = [term for term in _INDEX_TERMS if term in lower]
    code_like = re.findall(r"\b[a-z]+(?:_[a-z0-9]+){1,3}\b", lower)
    for term in code_like:
        if term in {"missing_context", "scope_drift", "acceptance_criteria"}:
            continue
        if term not in terms and any(key in term for key in ("design", "review", "workflow", "prompt", "architecture", "delivery", "bug")):
            terms.append(term)
    return terms[:6]


def _extract_rule_refs(lower: str) -> list[str]:
    refs: list[str] = []
    if "agents.md" in lower:
        refs.append("AGENTS.md")
    if "claude.md" in lower:
        refs.append("CLAUDE.md")
    if "project_rules.md" in lower:
        refs.append("PROJECT_RULES.md")
    if "cursor rules" in lower or "cursor rule" in lower or ".cursor/rules" in lower:
        refs.append("Cursor Rules")
    if "instruction" in lower or "instructions" in lower:
        refs.append("instructions")
    if "workflow" in lower:
        refs.append("workflow")
    if "skill" in lower:
        refs.append("skill")
    if "rules" in lower:
        refs.append("rules")
    return refs[:5]


def _has_task_variables(lower: str, session: SessionRecord) -> bool:
    file_refs = [
        match.lower()
        for match in re.findall(r"\b[a-z0-9_./-]+\.(?:py|ts|tsx|js|java|json|sql|md|yaml|yml)\b", lower)
    ]
    meaningful_files = [
        ref
        for ref in file_refs
        if ref.split("/")[-1] not in {"agents.md", "claude.md", "project_rules.md", "rules.md"}
    ]
    return bool(
        meaningful_files
        or session.prompt_has_code_context and bool(meaningful_files)
        or _contains_any(lower, _TASK_VARIABLE_TERMS)
        or re.search(r"(基于|按照|针对).{0,24}(模块|页面|接口|报告|图表|schema|handler|service|component)", lower)
        or re.search(r"(focus on|based on).{0,24}(module|page|api|report|chart|schema|handler|service|component)", lower)
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _observed_closure_methods(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    task_type: str,
) -> set[str]:
    observed: set[str] = set()
    if any(session.has_test_commands for session in sessions):
        observed.add("test")
    if any(session.has_verification_behavior for session in sessions):
        observed.add("smoke")
    if task_type == "config_or_prompt_change":
        observed.add("before_after")
        if any(read.prompt_lens and read.prompt_lens.takeaways for read in session_reads):
            observed.add("example_replay")
    if task_type == "design_or_requirements":
        observed.add("fact_alignment")
        if any(read.work_style in {"plan_driven", "spec_driven"} for read in session_reads):
            observed.add("checklist")
    if task_type == "writing_or_content":
        observed.add("manual_review")
    if task_type == "exploration_or_analysis":
        observed.add("fact_alignment")
    return observed


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for item in items:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows
