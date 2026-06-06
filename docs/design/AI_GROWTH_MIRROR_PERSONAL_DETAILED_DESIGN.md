---
title: AI Growth Mirror Personal Detailed Design
domain: growth_mirror
status: canonical
updated_at: 2026-06-06
score_target: 9.9
---

# AI Growth Mirror Personal Detailed Design

## 1. 产品定位

个人版不是“员工分析报告”，而是一个个人可持续使用的 AI 协作成长产品。

对用户的价值表达必须是：

- 帮我看见自己的协作习惯
- 帮我提升提问与工作流质量
- 帮我把高质量方法沉淀下来

而不是：

- 评估我是不是好员工
- 计算我值不值得被考核

## 2. 产品命名

产品名：

- `AI 成长镜`

页面主标题：

- `本期协作进化报告`

默认导出文件名：

- `ai-growth-mirror.html`

## 3. 信息架构

首页主链区块（与 `report_view._build_report_sections` 导航顺序一致）：

1. **首屏摘要**（Hero + Usage 卡片，`#section-summary`）
2. **成长信号总览**（含五轴雷达与「协作能力地图」子区块，`#section-growth-signals`）
3. **阶段评估**（`#section-level-evidence`）
4. **协作等级说明**（`#section-level-guide`）
5. **Prompt 成长教练**（`#section-prompt-coach`）
6. **摩擦根因地图**（`#section-friction`）
7. **本期值得保留的方法**（`#section-exemplars`）
8. **下一阶段训练冲刺**（2 项，`#section-growth-plan`）
9. **你在做什么**（`#section-focus`）
10. **协作节奏**（`#section-rhythm`）
11. **本期亮点**（`#section-wins`）

条件 / 附录区块：

- **AI 资产足迹**（`#section-agent-asset`，需 hub / asset 配置）
- **成长轨迹**（`#section-growth-delta`，需当前生成前已存在历史 snapshot；通常第 2 次 generate 起出现）
  - 顶部先展示 **近 30 天趋势结论**，趋势指标至少覆盖 `mirror_score`、`growth_level`、五轴、Prompt Quality 五维、行动型摩擦五类
  - 同一天多次 generate 时，页面默认只展示当天最后一次 snapshot；sidecar JSON 必须保留 `window_points` 全量点位和 `daily_points` 展示点位
  - 当 `daily_points < 3` 时只展示已有点位和“数据不足”说明，不强行做长期趋势判断
  - 当历史 snapshot 使用旧能力轴（`delegation / verification / breadth / authorship / outcome / workflow`）或缺少当前五轴时，趋势与 latest-vs-previous 必须降为低置信，并标记 schema mismatch；禁止把跨评分模型变化的点位包装成强趋势
  - 若存在上一期 snapshot，则同区块下半部分继续展示 **本期 vs 上一期变化诊断**
  - 诊断区顶部必须包含 5 张 summary cards：当前阶段、协作指数变化、最大进步轴、当前短板轴、置信度/样本量说明
  - 诊断区中部至少包含五轴对比、成长变化瀑布、Prompt Quality 来源说明、摩擦与恢复变化、方法资产沉淀
  - 诊断区底部必须有关键证据卡片与下一阶段优先训练建议，所有结论都要能回到 sidecar JSON 的结构化字段
- **协作风格透镜**（`#section-style-lens`，附录，不在主导航）

约束：

- 主报告 Hero 只负责“你现在在哪、为什么这么判断、接下来练什么”，不重复分享卡内容。
- 分享页只保留对外可发的一句话、3 条关键信息与阶段/分数，不出现“适合分享的一页摘要”这类内部产物式文案。
- 主报告必须提供完整快速导航，导航顺序与页面锚点顺序一致。
- 成长轨迹主视角固定是“近 30 天窗口趋势”；“本期 vs 当前生成前最近一份 snapshot”只作为同区块底部的辅助诊断。
- 无历史 snapshot 时，主报告不展示空图表；第一次 generate 只归档 snapshot，不显示该区块。
- 对比区块里的 Prompt Quality、usage、样本量都必须显式说明置信边界，禁止把 heuristic 或低样本包装成确定结论。

## 4. 文案策略

## 4.1 必须避免的词

- 员工
- 企业
- 考核
- 绩效
- 排名
- 画像打分
- 工作节奏（对外统一为 **协作节奏**，见 `#section-rhythm`）

## 4.2 建议使用的词

- 成长
- 进化
- 协作
- 镜像
- 方法
- 训练
- 风格
- 协作节奏

## 4.3 实现命名（与 UI 一致）

个人主链内部字段与 i18n 键统一使用 `collaboration_rhythm`：

- 领域：`GrowthProfile.collaboration_rhythm_type`
- 视图：`CollaborationRhythmSectionView`、`PersonalReportView.collaboration_rhythm`
- i18n：`view_model_*.yaml` → `collaboration_rhythm`
- 侧车 JSON：`summary.json` → `collaboration_rhythm`

锚点 ID 保持 `#section-rhythm` 不变，避免破坏已有书签与测试锚点。

## 5. 数据映射

## 5.1 阶段定位

底层字段：

- `growth_level`
- `mirror_score`

前台转义：

- `growth_level` 作为“当前阶段”
- `mirror_score` 作为“协作指数”

## 5.2 五轴成长底盘

底层字段：

- `radar_axes`（五轴分值与 reason）
- `growth_stage`（`strongest_axis` / `primary_gap` / `next_breakthrough`）
- 五轴子分字典（聚合内部键：`intent_clarity`、`execution_driving`、`implementation_depth`、`delivery_closure`、`adaptive_recovery`）

前台命名：

- `任务表达`
- `协作驱动`
- `实现下潜`
- `交付收口`
- `恢复推进`

区块名：

- `成长信号总览`
- `协作能力地图`

约束：

- 雷达图或等价主图只承载这五轴
- `mirror_score` / `growth_level` 可以保留，但必须由五轴与置信修正推出
- 用户必须同时看到 `strongest_axis`、`primary_gap`、`next_breakthrough`

## 5.3 风格 / 短板 / 阶段

底层字段：

- `style_traits`
- `gap_rankings`
- `summary.growth_stage`

前台原则：

- `style_traits` 回答“你通常怎么协作”
- `gap_rankings` 回答“你当前最欠缺什么”
- `growth_stage` 回答“你整体处在哪个成长区间”

禁止把这三类信息混成同一种表达，尤其不能把阶段性短板直接说成性格缺陷。

## 5.3.1 Agentic 系统成熟度

`growth_level` 不再只表达“会不会使用 AI”，而是表达用户是否能稳定调动一套 Agentic operating system：真实使用、工具编排、上下文工程、验证闭环、偏航恢复与方法资产回流。

一级能力：

- `Intent Framing`：目标、边界、约束、验收是否前置。
- `Workflow Orchestration`：是否能组织 plan / spec / tdd / delivery workflow 等多阶段推进。
- `Tool & Skill Leverage`：是否在真实会话中使用 skill、slash command、MCP、subagent、多模型或其他高杠杆工具。
- `Context Engineering`：是否把文件、规则、文档、错误日志和历史上下文带入任务。
- `Execution Depth`：是否进入真实实现链路和复杂边界。
- `Verification Closure`：是否把结果带到 test / build / smoke / replay / golden case / commit 等可验证状态。
- `Adaptive Recovery`：偏航、报错或阻塞后是否能基于新证据恢复推进。
- `Method Assetization`：是否把有效方法沉淀为 skill / rule / prompt / script / checklist / ADR，并在后续任务中回流使用。

证据优先级：

- `Observed Usage` 最高：真实会话里出现 skill / slash / workflow / tool / verification 调用。
- `Local Method Framework Match` 很高：`report.local_method_frameworks` 显式配置或 `asset_roots` 从本地 hub 提取出的私有方法名，在真实会话的 skill / slash 使用中被精确命中。
- `Repeated Pattern` 次高：同一方法、skill、workflow 指纹跨多个会话重复出现。
- `Authored Asset` 中等：创建或修改 skill / rule / prompt / script / governance asset。
- `Inventory Context` 最低：asset_root / hub 里存在文件，只能作为背景和低权重上下文。

产品约束：

- 用户目录结构不可被硬编码成通用能力标准。有人放在 `share/projects`，有人放在 `./skills`，有人只通过 slash command 或 MCP 使用能力；报告应优先看真实使用和复用，不以目录分类概全。
- `local_method_frameworks` 是可配置、可从本地 hub 提取、最终进入聚合的真源：配置项与扫描结果先合并为候选清单，再与会话中的 `unique_skills_used` / `slash_commands` 做规范化精确匹配。未被真实任务命中的候选只展示为资产上下文，不参与等级主证据。
- skill / rule / prompt 文件数量不能单独把用户推到 L4 / L5；只有当这些资产在真实任务里被使用、复用、编排或验证闭环支撑时，才进入等级主证据。
- `level_evidence` 必须展示 `Agentic 系统成熟度`，并同时呈现使用率、workflow 指纹、公开框架命中、本地方法命中、重复复用、资产创作和高杠杆功能使用。库存证据只能作为低权重背景，不能冒充用户当期状态。
- `human_intervention_session_rate` 是第一版“降低人工介入成本”事实指标：只统计当前人工纠偏压力，不直接声称已减少成本；只有存在可比历史后，才允许表达减少趋势。
- 数据不足时显示“未观察到”或留白，不用静态模板或资产库存替用户编造能力画像。

## 5.4 Prompt 模块

底层字段：

- `pq_avg_dimensions`
- `pq_deficit_counts`
- `pq_top_takeaways`
- `pq_sessions_evaluated`
- `pq_llm_session_count`（兼容保留）/ `pq_heuristic_session_count`（兼容保留）/ `pq_light_session_count`（兼容保留）
- `pq_llm_evaluated_count` / `pq_insufficient_count` / `pq_llm_failed_count` / `pq_llm_unavailable_count`（按 `evaluation_status` 统计，P1 新增）
- `PromptLensScores.evaluation_status`：`llm_evaluated | insufficient_input | llm_failed | llm_unavailable | not_applicable`

前台区块：

- `Prompt 成长教练`

目标：

- 不是解释模型机制
- 而是给用户一眼看懂的“下一步怎么提得更好”
- 优先使用 `pq_top_takeaways`、真实 prompt 片段和改写示例，而不是只给抽象建议
- 能从真实证据生成就生成；不能生成就留白或不展示，禁止用静态模板兜底冒充“你当前就是这样”
- `Prompt 成长教练` 必须覆盖**全程 PQ 主链**，不能再因为短会话或 LLM 不可用而静默断档
- `heuristic` 只允许作为代理来源展示，不能被描述成另一套独立的“Prompt Quality 评估产品”
- prompt 包输入文案对外统一使用 `evidence packet` / `period summary packet` 等中性口径，不再依赖产品自述式前缀
- prompt system 文案必须强调“行为证据 + 可训练下一步”，禁止滑回组织评价、绩效评语或工具宣传口吻

来源说明约束：

- 报告里必须显式告诉用户：本期有多少会话完成 LLM 语义判断（`llm_evaluated`）、多少因会话过短回退代理（`insufficient_input`）、多少 LLM 失败（`llm_failed`）、多少整体未配 LLM（`llm_unavailable`）
- `session_read_mode=heuristic` 的含义是"当前来源模式"，不是"另一种 Prompt 质量定义"
- 主报告按非零子句拼装人话；禁止展示 `LLM n / heuristic n / light n` 并列数字

## 5.4.2 Prompt 成长教练升级边界

`Prompt 成长教练` 已从“解释分数”升级为 **AI 提需求诊断器**，固定输出以下几层：

1. `top_deficits`：本期最主要的提需求短板，至少包含问题定义、影响、来源边界、置信度、证据摘要
2. `rewrite_cards`：2-4 张“原始提法 vs 更好提法”训练卡
3. `prompt_style`：识别 `explicit_requirement_prompt / indexed_prompt / mixed_prompt / under_specified_prompt`
4. `suggested_next_prompt`：只允许来自真实 `rewrite_cards` / LLM coaching / grounded takeaway 的改写结果；没有真实个性化改写时，必须为空，不得套静态模板
5. `closure_guidance`：按任务类型给出正确收口方式，而不是默认要求测试；携带 `mode`（`open_ended | engineered` 派生，不升 schema）；`open_ended` 适用于探索/设计/分析/文案，`engineered` 适用于代码/配置/SQL/结构化生成
6. `friction_synthesis`：标签综合判断层，LLM 配置时由 growth_coach 生成（evidence_refs 接地护栏），未配置时由 `domain/growth/prompting.py` 规则兜底；输出"你不是…而是…"风格可改动作；已打通 `growth_plan.linked_friction_synthesis_ids`
7. `preflight_checklist` / `recommended_training_inputs`：面向下一次发送前自检和训练输入建议
8. `universal_template` / `scenario_templates`：只能作为独立参考资产存在，不能在个性化内容缺失时顶替 `rewrite_cards` 或 `suggested_next_prompt` 出现在 personal report / compare / growth plan 主链里

补充约束：

- `indexed_prompt` 是正向方法资产信号，不得直接等价成 `missing-context`
- 静态模板可以作为知识资产维护，但不得包装成“这是你这次最该怎么问”的个性化结论
- Prompt 成长教练不再独立展示完整 `seven_day_training_plan`
- 完整的 `Week 1 / Week 2 / practice_prompt / success_signal / stop_doing` 训练计划统一归口到 `下一阶段训练冲刺`

硬约束：

- 只有在真实 `PromptLensTakeaway.original` 存在时，才允许展示用户原始提法
- 只有存在真实 `better_prompt` / grounding 证据时，才允许展示“下次可以这样问”或改写示例；否则留白
- 只有 heuristic 数据时，必须明确标记为代理来源
- 短会话不足时，不隐藏模块；改为展示来源说明、自检清单，以及明确的数据不足边界

## 5.4.3 下一阶段训练冲刺联动规则

`下一阶段训练冲刺` 必须消费两类上游结果：

- `growth_trajectory`：近 30 天持续低迷轴、本期最新退步轴、本期最新证据
- `prompt_coach`：top deficits、rewrite cards、通用/场景模板
- `agentic_system_score / human_intervention_session_rate`：方法系统化缺口与人工纠偏压力

联动规则：

- Prompt 维度或 deficit 明显偏弱时，输出 `prompt:*` 类型训练任务，但不得用静态模板替代个性化证据
- `agentic_system_score < 75` 或人工纠偏率偏高时，必须生成 `Action Contract`：说明应新增/强化哪个 rule、skill 或 workflow，以及下次自然语言入口如何自动触发
- `intent_clarity + missing-context / vague-request` 合并成“需求表达训练”
- `delivery_closure + missing-acceptance-criteria` 合并成“验收标准训练”
- 每个训练任务都必须附带 `evidence_refs`、`action_contract` 与 `linked_prompt_deficit_ids / linked_template_ids / linked_rewrite_card_ids / linked_growth_trend_refs / linked_closure_guidance_ids`

## 三段式 LLM 诊断层

### 架构

```
Stage 1 (Rule 层)  →  DiagnosisCandidatePacket
Stage 2 (LLM)      →  GroundedDiagnosis (evidence_refs + confidence + why_not_other_diagnosis)
Stage 3 (Rule 排序) →  rerank_diagnosis_result()
```

### 关键合约

| 对象 | 位置 | 说明 |
|------|------|------|
| `DiagnosisCandidate` | `domain/growth/diagnosis.py` | 单条候选：code / urgency / reason_codes / evidence_snippets |
| `DiagnosisCandidatePacket` | 同上 | Stage-1 输出：候选列表 + 人工干预率 + 高频缺口数 + 会话证据 |
| `GroundedDiagnosis` | 同上 | Stage-2 输出：label / explanation / confidence / evidence_refs / why_not_other_diagnosis |
| `DiagnosisResult` | 同上 | primary + secondary 列表 + synthesis_confidence + source |

### 强制约束
- LLM 输出的 `evidence_refs` 必须引用 Stage-1 packet 中的实际证据片段，最少 1 条
- `why_not_other_diagnosis` 必须明确说明为什么不选候选 2
- `synthesis_confidence` 仅在 ≥2 条强证据时标注 "high"
- LLM 不可用时，`rule_fallback_diagnosis()` 直接从 Stage-1 candidates 产出降级结果

## Agentic Evidence Graph

### 六维节点

| 维度 | 字段 | 来源 |
|------|------|------|
| 任务意图 | `task_intent` | `SessionRead.work_intent_mix` 主键 |
| 使用方法 | `method_used` | `unique_skills_used + slash_commands + advanced_features` |
| 使用上下文 | `context_used` | prompt 内容特征 + tool_counts.Read |
| 执行路径 | `execution_path` | tool_counts 组合标签（read→edit→run→verify 等） |
| 收口状态 | `closure_state` | `SessionRead.delivery_outcome` 映射 |
| 人工干预 | `human_intervention` | `user_interruptions` 计数 |

`build_agentic_evidence_graph(sessions, session_reads)` 组装图，`evidence_graph_to_dict()` 序列化。随 `CoreEvidence` 写入报告 sidecar（schema 1.2）。

## Action Contract Generator

替换原 `growth_plan._priority_action_contract` 固定 5 条输出。

`generate_action_contracts(stats, cap_scores, graph_summary, ...)` 规则：
1. 对 `pq_deficit_counts` 中频次最高的缺口，匹配 `_DEFICIT_RULE_TEMPLATES` 产出针对性 rule/skill 草稿
2. `agentic_system_score < 65` 时产出"方法路由 Skill"草稿
3. `human_intervention_session_rate ≥ 0.20` 时产出"人工纠偏自动化 Workflow"草稿
4. `verification_rate < 0.40 or delivery_closure < 60` 时产出"交付收口 Workflow"草稿
5. `graph_summary.high_intervention_rate ≥ 0.15` 时产出五项 Checklist 草稿

输出按 priority 降序，去重，最多 max_items 条。

## human_cost_reduction 趋势

`SnapshotSource.human_intervention_session_rate` 从 `stats.human_intervention_session_rate` 持久化到快照 summary。

`HumanCostTrend`（`domain/snapshots/model.py`）：
- `available: bool` — 两端快照都有数据时 True
- `direction: str` — "improving" | "worsening" | "flat" | "unknown"
- `delta: float` — 当期率 − 上期率（负值为 improving）
- `note: str` — 人类可读趋势文本，如 "human correction rate reduced from 35.0% → 15.0% (−20.0pp)"

在 `SnapshotComparison` 和 `SnapshotTrajectoryWindow` 中均携带此趋势。

## 5.4.1 usage 模块

底层字段：

- `total_input_tokens`
- `total_output_tokens`
- `total_cache_read_tokens`
- `total_cache_write_tokens`
- `total_cost_usd`
- `avg_cost_per_session`
- `avg_cache_hit_rate`
- `subagent_session_count`
- `mcp_session_rate`
- `avg_autonomous_chain_length`
- `median_session_duration_minutes`
- `heavy_session_count`

前台区块：

- `AI 使用概况`（首屏 Hero Usage 卡片 + coverage 说明，非独立导航项）

目标：

- 让用户一眼看到“我这期到底用了多少、强度多大、杠杆多高”
- `memory` 当前未采集，必须明确写出来，而不是静默缺失
- usage 区块只讲真实数据，不讲泛 narrative 空话

## 5.5 摩擦模块

底层字段：

- `friction_by_attribution`
- `friction_type_counts`

前台区块：

- `摩擦根因地图`

强调：

- 问题来自哪里
- 用户下一步可以做什么

## 5.6 exemplar 模块

底层字段：

- `mine_exemplars(...)`

前台区块：

- `本期值得保留的方法`

强调：

- 为什么值得保留
- 如何迁移到下次使用
- 同类型 pattern 不重复出现
- exemplar 卡片必须拆成“为什么值得保留”和“下次怎么迁移”，不能只给静态口号

## 5.7 persona / style traits 模块

底层字段：

- `CollaborationStyleResult`
- `style_traits`

前台区块：

- `协作风格透镜`
- `成长信号总览`

强调：

- 风格偏好
- 成长盲区

不强调：

- 心理学测验感

## 5.8 growth plan 模块

底层字段：

- `build_growth_plan(...)`

前台区块：

- `下一个两周训练冲刺`（导航文案；实现为 2 项 `#section-growth-plan`）

输出结构：

- 训练主题
- 为什么练
- Week 1
- Week 2
- 练习 Prompt

## 5.9 缓存与性能底盘优化 (v0.4.2 / Schema 1.2 架构增量)

为支持多端协作、海量历史日志扫描以及无 Token 数据源的平权，引入以下底层数据及性能机制：

- **缺失型指标动态归一化**：在计算 `implementation_depth` 时，若 [scorer.py](../../ai_growth_mirror/domain/growth/scorer.py) 检测到 `has_token_data` 为 `False`，动态剥离 `total_token_volume`（18% 子权重），其余四项等比扩重至 `1.0`。
- **共享数据库 Per-Session Revision 感知**：对多会话共用单 SQLite（如 Trae/QCoder 的 `state.vscdb`），通过 `get_vscdb_mtime` 取出 `chat.input-history` 等 AI 相关数据行的组合哈希。仅在哈希变更时缓存失效，避免无关 UI 状态写入导致缓存颠簸失效。
- **跨机器缓存物理隔离**：对非 `local` 机器的 session 记录，以 `(source_machine, session_id)` 双重键唯一标识和去重，并隔离存储于子目录中（如 `{cache_dir}/records/{tool_name}/{source_machine}/{session_id}.json`），防止多端缓存互相覆写。
- **惰性解析 (Lazy Placeholder) 机制**：扫描阶段仅使用极速提取的 `project_path` 构造 Placeholder 代理会话，不调昂贵的完整 `parse_session`。当 [orchestrator.py](../../ai_growth_mirror/application/orchestrator.py) 过滤采样定位了最终 session 列表后，才执行 `ensure_parsed` 并写回缓存。

## 6. 交互原则

- 默认自用
- 默认正向反馈
- 默认不横向比较
- 默认不输出组织标签
- 默认告诉用户“怎么提升”

## 7. 工程设计

当前个人版实现以 **严格分层 personal 主链** 为准（架构真源见 `ARCHITECTURE_PRINCIPLES.md`）。

补充边界：

- 删改冻结边界见项目技能 `ai-growth-mirror-dev` → `references/value_recovery_inventory.md`
- 未经新的用户明确确认，不得删除 inventory 中已冻结的主链能力

### 7.1 分层落点

| 层 | 关键文件 | 职责 |
|---|---|---|
| Adapter | `cli.py` | 解析 CLI 入参，调用 application |
| Application | `application/orchestrator.py`、`application/personal_report_service.py`、`application/report_view.py`、`application/html_render.py`、`application/growth_plan.py`、`application/summary_payload.py`、`application/label_catalogs.py` | **personal report 全流程**：collect → extract → aggregate → coaching → assemble view/payload → render → write |
| Domain | `domain/common/contracts.py`、`domain/session/*`、`domain/ingestion/*`、`domain/signals/*`、`domain/growth/*` | 纯模型、枚举、parser、aggregate 等无 I/O 逻辑 |
| Infrastructure | `infra/readers/*`、`infra/extractors/*`、`infra/llm/*`、`infra/cache/store.py`、`infra/snapshots.py`、`infra/i18n/catalog.py`、`infra/enrichers/asset.py` | readers、LLM、缓存、快照、**i18n YAML adapter** |
| Assets | `assets/templates/*.j2`、`assets/i18n/*.yaml`、`assets/prompts/*` | 模板、UI 标签、LLM 提示词真源 |

### 7.2 主链文件索引

- `application/orchestrator.py` — `generate_report_artifacts` / `collect_sessions`
- `domain/common/contracts.py` — `LlmGateway`、`PromptTemplateGateway` 与 Prompt / LLM 请求 DTO
- `domain/session/scope.py`、`domain/session/tool_registry.py`
- `domain/ingestion/model.py`
- `domain/growth/coaching.py`、`domain/growth/planning.py`
- `domain/signals/payloads.py`
- `application/report_view.py`、`application/summary_payload.py`、`application/html_render.py`
- `infra/i18n/catalog.py` — UI 标签 YAML 加载（经 `application/label_catalogs.py` 注入渲染）
- `assets/templates/report.html.j2`
- `assets/i18n/*.yaml`
- `cli.py` — personal 主命令入口

### 7.3 静态资源约束

- 提示词只放 `assets/prompts/`（当前主链：`session_read`、`prompt_lens`、`growth_coach`）
- 提示词共享 partial 只放 `assets/prompts/_partials/`
- UI 标签只放 `assets/i18n/`
- HTML 模板只放 `assets/templates/`
- i18n 读取经 `application/label_catalogs.py` + `infra/i18n/catalog.py`；`html_render.py` 接收预加载 catalog，不直接读 YAML
- 提示词输出 JSON 必须先落到明确 DTO（`domain/signals/payloads.py` 等），再进入 domain / application
- `assets/prompts/**/bak/` 仅作本地备份，不属于公开真源；review 过程文档不在活动区长期保留

### 7.4 主链边界

1. `collect_sessions`（application + infra/readers）只负责采集 `SessionRecord`
2. `extract_session_reads_batch` / `build_heuristic_session_reads_batch`（infra/extractors）只负责生成 `SessionRead`
3. `aggregate`（domain/growth/scorer.py）只负责纯计算 `GrowthProfile`
4. `generate_growth_guidance`（infra/llm/coach.py）负责 LLM coaching；结果以 `CoachingContent` DTO 传入 report
5. `application/report_view.py` 负责展示 DTO、i18n 映射与 section 组装；`application/html_render.py` 只负责 HTML 字符串渲染
6. 文件写盘、sidecar、share surface、快照归档由 `application/personal_report_service.py` 调用 infra 完成

### 7.5 分层收口（持续迭代）

1. 产品命名与页面语义（已完成）
2. application 接管 personal report 写盘与 coaching 编排（已完成：`application/personal_report_service.py`）
3. label catalog 由 application 注入，`html_render.py` 不直接读 YAML（已完成）
4. growth 底盘切换为五轴雷达 + 风格 + 短板 + 趋势（已完成主链）
5. domain 去除展示文案，application 负责 i18n 映射与用户解释（持续迭代）
6. 分享页与传播层补齐（已完成主链：`ai-growth-mirror-share.html`）
7. HTML 渲染收口至 `application/html_render.py`（已完成）
8. 单测与回归收敛（持续：`pytest tests/unit -q --tb=no`）
9. redact / escaping 四输出面回归（已完成）

## 8. 验收标准

- 页面不出现“员工 / 企业 / 绩效 / 考核”主语义
- 默认输出文件名为 `ai-growth-mirror.html`
- 页面标题为 `AI 成长镜`
- 主报告标题为 `本期协作进化报告`
- exemplar 区块切为“方法保留”语义
- persona 区块切为“风格透镜”语义
- CLI 只保留 personal growth mirror 主链
- 提示词目录只保留 `session_read / prompt_lens / growth_coach`
- 单测通过

## 修订记录
- 2026-05-25：形成个人成长版详细设计真源。
- 2026-05-27：阶段/指数字段对齐 `growth_level` / `mirror_score`；五轴底盘字段说明去 `agentic_*` 残留。
- 2026-05-27：对齐严格分层目标架构；application 编排 personal report，i18n 真源经 `label_catalogs.py` + `infra/i18n/catalog.py` 注入。
- 2026-05-27：分享卡改为对外可发的结论卡；主报告补完整导航、减少重复块，Prompt 教练优先展示真实样例与改写示例。
- 2026-05-27：对齐当前代码——HTML 在 `application/html_render.py`；导航顺序与 README 一致；文档去旧产品面表述。
- 2026-05-29：公开 Wrapped Hero/用量口径/协作节奏文案与配色语义对齐；文档治理备份后更新本节。
