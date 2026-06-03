---
title: AI Growth Mirror 来源真相与教练重构设计
domain: growth_mirror
status: canonical
updated_at: 2026-06-03
score_target: 9.8
supersedes: docs/plan/plan.md, docs/plan/需求.md
---

# AI Growth Mirror — 来源真相与教练重构设计 + 排期

> 本文是本轮"来源真相 / Prompt 教练 / 摩擦综合判断 / 报告决策化"改造的设计与排期真源。
> 取代 `docs/plan/plan.md`、`docs/plan/需求.md`（二者内容重复、文件路径引用错误，待确认后归档）。
> 架构边界以 `docs/design/ARCHITECTURE_PRINCIPLES.md` 为准；产品语义以 `AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md` 为准。

## 0. 背景与根因

### 0.1 用户疑问

"既然全量跑了 LLM，为什么报告里还有 heuristic 代理来源？"

### 0.2 根因（代码实锤）

heuristic 出现 **不等于"没配 LLM"**。即使 LLM 全程可用，以下会话也永远拿不到 LLM 语义评估而被回退为 `source="heuristic"`：

- 会话太短：用户消息 `< 5` 条（`MIN_USER_MESSAGES_FOR_PQ = 5`，`infra/extractors/prompt_quality.py`），根本不调 LLM；
- LLM 调用/解析失败：该会话回退代理；
- 完全未配 LLM：全程代理。

当前 `PromptLensScores` 把这三种状态全部压成同一个 `source="heuristic"`（`infra/extractors/heuristic.py`），导致无法如实披露。

### 0.3 两条已定决策

1. 对 heuristic：**如实披露代理来源**（不走"严格隐藏"），与现有设计真源 §5.4 一致。
2. `friction_synthesis`：**配了 LLM 走 LLM（效果更好），未配回退规则**，与现有 Coaching 的"LLM + 规则降级"同构。

## 1. 产品走向（北极星）

AI 成长镜 = 一面"能说真话、且能把问题翻译成下一步动作"的协作镜子。三条主线：

- 真相线：每个结论都能说清"怎么得出、可信度多少"。
- 诊断线：标签 → 人话综合判断 → 可改动作。
- 决策线：主报告 3 分钟读完即知"在哪/怎么问/怎么练"，深挖去 compare。
- 个性化生成线：能从真实证据推出来的内容才展示；推不出来就留白，不用模板冒充用户当期状态。
- Agentic 等级线：等级优先看真实会话中的 skill / workflow / tool / verification 使用与复用；hub / asset_root 文件库存只作低权重背景，不能单独代表用户能力阶段。本地/私有方法框架通过 `report.local_method_frameworks` 显式配置或 `asset_roots` 扫描提取，再与真实会话 skill / slash 使用做精确匹配后进入聚合。

## 2. 来源真相模型（决策 1）

### 2.1 真值层：用 `evaluation_status` 取代被滥用的 `source`

`domain/signals/model.py :: PromptLensScores` 新增/调整：

- `evaluation_status`：`llm_evaluated | insufficient_input | llm_failed | llm_unavailable | not_applicable`
- `coverage`：`full | light | none`（只表完整度）
- `source_engine`：`llm | heuristic`（内部调试用，不上主报告）

### 2.2 运行级 `run_mode`

`run_mode: llm | heuristic_only`（本次是否配了 LLM），用于区分"系统没跑 LLM" vs "会话不达标"。

### 2.3 用户可见口径（如实披露）

主报告（轻量一句人话）示例：

> 本期 164 个会话纳入 Prompt 评估：85 个完成 LLM 语义判断；72 个因会话过短改用轻量代理；5 个 LLM 评估失败已回退代理；2 个不适用。代理结果仅作弱提示，不参与强结论。

compare / 附录：各 status 计数 + 随时间变化 + 完整度 breakdown。

约束：所有面向用户文案走 `assets/i18n/`，`domain/` 不硬编码文案。

## 3. friction_synthesis（决策 2：LLM 优先 / 规则兜底）

### 3.1 架构（守分层红线）

- `domain/growth/prompting.py :: build_friction_synthesis_intent()`：纯规则，产出 `id / pattern_key / evidence_refs / confidence`，不含面向用户句子。
- `infra/llm/coach.py` 或新 `assets/prompts/friction_synthesis/`：LLM 基于 intent + 证据生成 `explanation / next_action`。
- `domain/signals/payloads.py :: parse_friction_synthesis_payload()`：LLM JSON → DTO，守解析契约。
- `application/prompt_coach.py`：配 LLM 用 LLM 结果；否则用 intent + `assets/i18n` 模板拼人话。

### 3.2 护栏

LLM 输出的 `evidence_refs` 必须命中真实 findings；缺证据降级规则句，禁止编造；`confidence` 随证据量衰减。

### 3.3 字段

`friction_synthesis: { id, label, explanation, next_action, confidence, evidence_refs, generated_by: llm|rule }`

并打通 `growth_plan.linked_friction_synthesis_ids`。

## 4. closure_guidance.mode（低成本）

纯派生属性，不升 schema。`domain/growth/prompting.py` 静态映射：

- `open_ended`：design_or_requirements / exploration_or_analysis / writing_or_content
- `engineered`：code_change / config_or_prompt_change / structured_generation / sql_or_schema

收益：设计/文案类不再被误判"缺测试"；工程类才推 smoke/test/replay。

## 5. 信息架构 / UX

### 主报告 = 决策版

- 主链 5 段全展开：成长信号 → 阶段评估 → [成长轨迹] → Prompt 教练 → 训练冲刺。
- 附录区块（level-guide/friction/exemplars/focus/rhythm/wins/agent-asset/style-lens）默认折叠为可点开卡片（启用已有 `.section-toggle`）。
- Prompt 教练删 `LLM n / heuristic n / light n` 并列行，换 §2.3 人话。
- `下次可以这样问`、`rewrite cards` 只在存在 grounded `better_prompt` 时展示；没有真实改写时，主报告与 compare 都不做静态模板兜底。

### compare = 深度版

补齐 rewrite cards、模板全集、PQ 五维 delta、来源 status 明细；主报告与 compare 的 `axis_deltas` 重复收敛到 compare。

## 6. 排期（P0–P3）

| 阶段 | 目标 | 升 schema/重跑 | 风险 | 价值 |
|---|---|---|---|---|
| P0 体验止血 | 删并列行→人话；附录折叠；closure_guidance.mode | 否 | 极低 | 高·立刻可见 |
| P1 来源真相 | evaluation_status + run_mode 落真值；区分短会话/失败/无LLM；source_summary 升级；主报告+compare+sidecar 切口径 | 是(1.0→1.1，旧 reads 失效重跑) | 中 | 高·兑现如实披露 |
| P2 摩擦综合判断 | friction_synthesis（LLM优先/规则兜底）+ growth_plan 联动 | 否 | 中 | 高·诊断线 |
| P3 compare 深度版 | rewrite/模板全集/PQ细维迁入 compare；主报告去重 | 否 | 低 | 中 |

## 7. 落地文件清单 + 验收

### P0
- `assets/templates/report.html.j2`：删并列来源行保留 source_note；附录区块套 `.section-toggle` 折叠。
- `domain/growth/prompting.py`：`ClosureGuidanceSignal` 加 `mode` 派生 + 常量。
- `application/prompt_coach.py` / `report_view.py`：closure_guidance view 增 `mode`。
- `assets/i18n/view_model_{zh,en}.yaml`、`template_labels_*`：加 open_ended/engineered 文案。
- `Prompt Coach` 个性化输出加严格护栏：`suggested_next_prompt` 与 `rewrite_cards` 只接真实 evidence-backed 改写；`universal/scenario template` 不再作为 personal report / compare / growth_plan 的兜底输入。
- `Level Evidence` 新增 `Agentic 系统成熟度`：以实际 skill/workflow 使用、公开 framework 指纹、本地方法框架命中、重复复用、资产创作和高杠杆功能为主证据；资产库存仅作为上下文，防止把某个用户的目录结构泛化成所有人的等级标准。
- 验收：`pytest tests/unit -q`；新增"主报告无并列三数字"、mode 断言，以及"无 grounded rewrite 时不展示模板 prompt" 断言。

### P1
- `domain/signals/model.py`：`PromptLensScores` 加 `evaluation_status`，`coverage` 增 `none`，保留内部 `source_engine`。
- `infra/extractors/{prompt_quality,heuristic,llm}.py`：按 短会话/失败/无LLM 落不同 `evaluation_status`。
- `domain/cache_schema.py`：`CACHE_SCHEMA_VERSION → "1.1"`。
- `domain/growth/scorer.py`：按 status 聚合计数。
- `application/{prompt_coach,report_view,summary_payload}.py` + 模板 + compare：切新 source_summary（run_mode + 各 status count + user_facing_note）。
- 验收：短会话计入 insufficient 而非 heuristic；pytest 通过。

### P2
- `domain/growth/prompting.py` + `domain/signals/payloads.py` 新 DTO；`infra/llm/coach.py` 或新 prompt 包；`application/prompt_coach.py` 选择逻辑；`growth_plan.py` 加 `linked_friction_synthesis_ids`；sidecar + 模板。
- 验收：LLM 路径证据可回链；无 LLM 走规则句；growth_plan 能引用；pytest 通过。

### P3
- `assets/templates/snapshot_compare.html.j2` + `application/growth_trajectory.py`：补 rewrite/模板/PQ细维；主报告去 axis_deltas 重复。
- 验收：compare 渲染包含新明细；pytest 通过。

## 8. 与现有契约的关系 / 待办

- P1 落地后需在 `AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md` §5.4 补一句"区分 insufficient/failed/unavailable"，保持文档与实现一致。
- `docs/plan/plan.md`、`docs/plan/需求.md` 待用户确认后归档，不在本轮删除。

## 修订记录

- 2026-06-02：合并 plan.md/需求.md 两份重复方案，校正 ai-insights 错误路径，确立来源真相模型与 P0–P3 排期。
