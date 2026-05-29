---
title: AI Growth Mirror Personal Detailed Design
domain: growth_mirror
status: canonical
updated_at: 2026-05-29
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
- **成长轨迹对比**（`#section-growth-delta`，需当前生成前已存在历史 snapshot；通常第 2 次 generate 起出现）
- **协作风格透镜**（`#section-style-lens`，附录，不在主导航）

约束：

- 主报告 Hero 只负责“你现在在哪、为什么这么判断、接下来练什么”，不重复分享卡内容。
- 分享页只保留对外可发的一句话、3 条关键信息与阶段/分数，不出现“适合分享的一页摘要”这类内部产物式文案。
- 主报告必须提供完整快速导航，导航顺序与页面锚点顺序一致。
- “成长轨迹对比”固定表示“本期 vs 当前生成前最近一份 snapshot”，不是任意两期自由拼接。

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

## 5.4 Prompt 模块

底层字段：

- `pq_avg_dimensions`
- `pq_deficit_counts`
- `pq_top_takeaways`
- `pq_sessions_evaluated`
- `pq_llm_session_count`
- `pq_heuristic_session_count`
- `pq_light_session_count`

前台区块：

- `Prompt 成长教练`

目标：

- 不是解释模型机制
- 而是给用户一眼看懂的“下一步怎么提得更好”
- 优先使用 `pq_top_takeaways`、真实 prompt 片段和改写示例，而不是只给抽象建议
- `Prompt 成长教练` 必须覆盖**全程 PQ 主链**，不能再因为短会话或 LLM 不可用而静默断档
- `heuristic` 只允许作为代理来源展示，不能被描述成另一套独立的“Prompt Quality 评估产品”
- prompt 包输入文案对外统一使用 `evidence packet` / `period summary packet` 等中性口径，不再依赖产品自述式前缀
- prompt system 文案必须强调“行为证据 + 可训练下一步”，禁止滑回组织评价、绩效评语或工具宣传口吻

来源说明约束：

- 报告里必须显式告诉用户：本期有多少会话来自 `LLM 语义评估`，多少来自 `代理回填`
- `session_read_mode=heuristic` 的含义是“当前来源模式”，不是“另一种 Prompt 质量定义”

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

