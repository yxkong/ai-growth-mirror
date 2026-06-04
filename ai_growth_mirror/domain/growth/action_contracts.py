"""Action Contract Generator.

Upgrades the fixed 5-item contract list in growth_plan into a dynamic
generator that produces specific rule/skill/workflow draft recommendations
based on this period's high-frequency correction patterns, diagnosis
signals, and Agentic Evidence Graph summary.

Domain-only: no I/O, no LLM calls, no application or infra imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import GrowthProfile
    from .evidence_graph import AgenticEvidenceGraphSummary


# ---------------------------------------------------------------------------
# Contract types
# ---------------------------------------------------------------------------


@dataclass
class ActionContractItem:
    """One concrete auto-generated action contract item."""

    kind: str  # "rule" | "skill" | "workflow" | "checklist"
    title: str
    rationale: str
    draft_content: str = ""  # minimal sketch of the rule/skill/workflow
    evidence_refs: list[str] = field(default_factory=list)
    priority: int = 50  # 0–100; higher = more urgent


@dataclass
class ActionContractReport:
    """Full action contract for one priority or the whole period."""

    items: list[ActionContractItem] = field(default_factory=list)
    generated_by: str = "rule_engine"
    total_human_corrections: int = 0


# ---------------------------------------------------------------------------
# Pattern → contract mapping
# ---------------------------------------------------------------------------

_DEFICIT_RULE_TEMPLATES: dict[str, ActionContractItem] = {
    "missing-acceptance-criteria": ActionContractItem(
        kind="rule",
        title="验收标准前置规则",
        rationale="检测到多次'无验收标准'缺口，说明 AI 频繁过早判定完成。",
        draft_content=(
            "规则草稿：发起类任务时，Agent 必须先返回：\n"
            "1. 判断口径 — 本次按什么原则判好坏？\n"
            "2. 反例边界 — 哪些输出看似完整但仍算不合格？\n"
            "3. 验收门禁 — 完成后要跑哪些测试 / 自检链路？"
        ),
        evidence_refs=["pq_deficit.missing-acceptance-criteria"],
        priority=95,
    ),
    "missing-context": ActionContractItem(
        kind="rule",
        title="上下文前置规则",
        rationale="多次'上下文缺失'缺口，AI 需先补问才能行动。",
        draft_content=(
            "规则草稿：首轮必须包含：现象 / 相关文件 / 约束 / 验收。\n"
            "若缺少以上任一项，Agent 应先索取而非假设。"
        ),
        evidence_refs=["pq_deficit.missing-context"],
        priority=90,
    ),
    "vague-request": ActionContractItem(
        kind="skill",
        title="请求细化 Skill",
        rationale="检测到模糊请求模式，AI 频繁给建议而非产出。",
        draft_content=(
            "Skill 草稿：当 first_prompt 语义分析为'愿望式'时，\n"
            "自动触发：'请把目标改写为动作序列：定位 → 修改 → 验证 → 总结。'"
        ),
        evidence_refs=["pq_deficit.vague-request"],
        priority=88,
    ),
    "unclear-correction": ActionContractItem(
        kind="rule",
        title="纠偏锐利度规则",
        rationale="多次'纠偏不清晰'，AI 沿旧方向持续推进。",
        draft_content=(
            "规则草稿：纠偏时必须同时给出：\n"
            "1. 错误点（what went wrong）\n"
            "2. 正确边界（what is NOT acceptable）\n"
            "3. 下一步最小路径"
        ),
        evidence_refs=["pq_deficit.unclear-correction"],
        priority=85,
    ),
    "scope-drift": ActionContractItem(
        kind="rule",
        title="范围锁定规则",
        rationale="检测到范围漂移，AI 顺手扩大改动面。",
        draft_content=(
            "规则草稿：首轮显式写出[只允许改什么]与[禁止改什么]。\n"
            "Agent 在每轮执行前必须自检是否超出范围。"
        ),
        evidence_refs=["pq_deficit.scope-drift"],
        priority=82,
    ),
}

_AGENTIC_SKILL_TEMPLATE = ActionContractItem(
    kind="skill",
    title="方法路由 Skill",
    rationale="Agentic 系统成熟度低，复杂任务缺少 skill/workflow 自动路由。",
    draft_content=(
        "Skill 草稿（delivery-workflow 兼容）：\n"
        "当用户提出'帮我评估 / 优化 / 设计'类任务时，\n"
        "Agent 必须先返回：\n"
        "1. 将按哪些评估维度判断？\n"
        "2. 需要读取哪些真源文件？\n"
        "3. 完成后跑哪些自检？"
    ),
    evidence_refs=["agentic_system_score", "local_method_framework_rate"],
    priority=90,
)

_HUMAN_COST_WORKFLOW_TEMPLATE = ActionContractItem(
    kind="workflow",
    title="人工纠偏自动化 Workflow",
    rationale="当期人工补规则次数偏高，最高频纠偏点应沉淀为 workflow 入口。",
    draft_content=(
        "Workflow 草稿（基于本期最高频纠偏模式）：\n"
        "- 每次发起新任务时，先查询是否存在对应 rule / skill。\n"
        "- 若不存在，执行后把本次补充的原则保存为新规则草稿。\n"
        "- 下次同类任务自动触发该规则，不再依赖人工补充。"
    ),
    evidence_refs=["human_intervention_session_rate"],
    priority=88,
)

_CLOSURE_WORKFLOW_TEMPLATE = ActionContractItem(
    kind="workflow",
    title="交付收口 Workflow",
    rationale="验证率偏低，任务频繁在无收口状态下结束。",
    draft_content=(
        "Workflow 草稿：每次任务结束前执行收口检查：\n"
        "1. 实现是否覆盖了所有验收条件？\n"
        "2. 是否已跑最小回归测试？\n"
        "3. 是否标记剩余风险？"
    ),
    evidence_refs=["verification_behavior_rate", "delivery_closure_score"],
    priority=85,
)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def generate_action_contracts(
    stats: "GrowthProfile",
    capability_scores: dict[str, float],
    *,
    graph_summary: "AgenticEvidenceGraphSummary | None" = None,
    diagnosis_code: str = "",
    max_items: int = 6,
) -> ActionContractReport:
    """Generate dynamic action contracts from high-frequency correction patterns.

    Rules:
    1. Each contract item maps to a concrete kind (rule / skill / workflow).
    2. Evidence refs must cite real stats fields or diagnosis codes.
    3. Items are ranked by priority and de-duped by kind+title.
    4. At most max_items are returned to avoid overwhelming the user.
    """
    pq_deficit_counts = dict(stats.pq_deficit_counts or {})
    human_intervention_rate = float(getattr(stats, "human_intervention_session_rate", 0.0) or 0.0)
    agentic_score = float(getattr(stats, "agentic_system_score", 0.0) or 0.0)
    verification_rate = float(getattr(stats, "verification_behavior_rate", 0.0) or 0.0)
    delivery_closure_score = capability_scores.get("delivery_closure", 100.0)
    total_human_corrections = getattr(stats, "human_intervention_session_count", 0)

    items: list[ActionContractItem] = []

    # Deficit-driven contracts: generate from highest-frequency deficits
    for deficit_key, count in sorted(pq_deficit_counts.items(), key=lambda x: -x[1]):
        if count < 1:
            continue
        template = _DEFICIT_RULE_TEMPLATES.get(deficit_key)
        if template is None:
            continue
        # Clone and annotate with actual count
        item = ActionContractItem(
            kind=template.kind,
            title=template.title,
            rationale=f"{template.rationale}（本期出现 {count} 次）",
            draft_content=template.draft_content,
            evidence_refs=list(template.evidence_refs) + [f"count={count}"],
            priority=min(100, template.priority + count * 2),
        )
        items.append(item)

    # Agentic system gap contract
    if agentic_score < 65.0:
        item = ActionContractItem(
            kind=_AGENTIC_SKILL_TEMPLATE.kind,
            title=_AGENTIC_SKILL_TEMPLATE.title,
            rationale=f"{_AGENTIC_SKILL_TEMPLATE.rationale}（当前分值 {round(agentic_score)}）",
            draft_content=_AGENTIC_SKILL_TEMPLATE.draft_content,
            evidence_refs=list(_AGENTIC_SKILL_TEMPLATE.evidence_refs) + [f"agentic_score={round(agentic_score)}"],
            priority=_AGENTIC_SKILL_TEMPLATE.priority,
        )
        items.append(item)

    # Human cost contract: if ≥20% sessions needed ≥2 corrections
    if human_intervention_rate >= 0.20:
        human_pct = round(human_intervention_rate * 100)
        item = ActionContractItem(
            kind=_HUMAN_COST_WORKFLOW_TEMPLATE.kind,
            title=_HUMAN_COST_WORKFLOW_TEMPLATE.title,
            rationale=f"{_HUMAN_COST_WORKFLOW_TEMPLATE.rationale}（{human_pct}% 会话需要 ≥2 次补规则）",
            draft_content=_HUMAN_COST_WORKFLOW_TEMPLATE.draft_content,
            evidence_refs=list(_HUMAN_COST_WORKFLOW_TEMPLATE.evidence_refs) + [f"rate={human_pct}%"],
            priority=min(100, _HUMAN_COST_WORKFLOW_TEMPLATE.priority + int(human_pct)),
        )
        items.append(item)

    # Delivery closure contract: if verification rate low or delivery score low
    if verification_rate < 0.40 or delivery_closure_score < 60.0:
        item = ActionContractItem(
            kind=_CLOSURE_WORKFLOW_TEMPLATE.kind,
            title=_CLOSURE_WORKFLOW_TEMPLATE.title,
            rationale=(
                f"{_CLOSURE_WORKFLOW_TEMPLATE.rationale}"
                f"（验证率 {round(verification_rate * 100)}% / 交付收口轴 {round(delivery_closure_score)}）"
            ),
            draft_content=_CLOSURE_WORKFLOW_TEMPLATE.draft_content,
            evidence_refs=list(_CLOSURE_WORKFLOW_TEMPLATE.evidence_refs),
            priority=_CLOSURE_WORKFLOW_TEMPLATE.priority,
        )
        items.append(item)

    # Evidence Graph signal: enrich with cross-dimension observation
    if graph_summary is not None and graph_summary.high_intervention_rate >= 0.15:
        high_pct = round(graph_summary.high_intervention_rate * 100)
        items.append(
            ActionContractItem(
                kind="checklist",
                title="高干预会话清单",
                rationale=f"证据图显示 {high_pct}% 会话需要 ≥2 次人工干预，建议转成 checklist 驱动。",
                draft_content=(
                    "Checklist 草稿（每次发起高复杂度任务前）：\n"
                    "□ 已声明判断口径？\n"
                    "□ 已声明反例边界？\n"
                    "□ 已声明证据来源？\n"
                    "□ 已声明交付形态？\n"
                    "□ 已声明验收门禁？"
                ),
                evidence_refs=[f"graph.high_intervention_rate={high_pct}%"],
                priority=78,
            )
        )

    # De-dup by kind+title, sort by priority descending
    seen: set[str] = set()
    deduped: list[ActionContractItem] = []
    for item in sorted(items, key=lambda x: -x.priority):
        key = f"{item.kind}::{item.title}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_items:
            break

    return ActionContractReport(
        items=deduped,
        generated_by="rule_engine",
        total_human_corrections=total_human_corrections,
    )


def action_contract_to_lines(report: ActionContractReport) -> list[str]:
    """Render contract items as concise human-readable lines for growth_plan."""
    lines: list[str] = []
    kind_emoji = {"rule": "Rule", "skill": "Skill", "workflow": "Workflow", "checklist": "Checklist"}
    for item in report.items:
        prefix = kind_emoji.get(item.kind, item.kind.title())
        lines.append(f"{prefix}：{item.title} — {item.rationale}")
    return lines
