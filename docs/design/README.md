---
title: Growth Mirror Design Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-01
---

# AI Growth Mirror 文档索引

## 当前北极星

| 文档 | status | 用途 |
|------|--------|------|
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | **canonical · 唯一架构真源** | 分层、资源归属、提示词命名、稳定性约束 |
| [AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md) | canonical | 产品命名、文案语气、禁词边界 |
| [AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](./AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md) | supporting | 为什么聚焦 AI 用户成长镜 |
| [../org/AI_GROWTH_MIRROR_OPEN_SOURCE_PROPAGATION_DESIGN.md](../org/AI_GROWTH_MIRROR_OPEN_SOURCE_PROPAGATION_DESIGN.md) | supporting | 传播与分享飞轮 |
| [OPEN_SOURCE_GOVERNANCE.md](../config/OPEN_SOURCE_GOVERNANCE.md) | supporting | 仓库治理、脱敏与发布边界 |

仓级入口见 `docs/README.md`。活动区只保留当前 AI 成长镜 真源。

### 过程稿处理原则

- 活动区不再保留并行 plan / review 真源。
- 过程稿统一在 `bak/` 备份后移出活动区，避免与 `ARCHITECTURE_PRINCIPLES.md` 形成双真源。

## 历史材料策略

为避免旧叙事和过时方案继续污染当前真源，历史过程稿与已替代文档不再作为活动区真源。

## 建议阅读顺序

1. 架构总纲 → 2. Personal 详细设计 → 3. 命名与语气边界 → 4. 根因分析 → 5. 传播设计

## 最近更新（Agentic 架构 · v0.4-patch1）

`feat/agentic-diagnosis-graph` 分支已落盘的设计增量（详见 [AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md) 与 [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md)）：

- **三段式 LLM 诊断层**：Rule 候选包 → LLM grounded synthesis（`evidence_refs` + `why_not_other_diagnosis`）→ Rule 重排；`CoachingContent.diagnosis` 字段
- **Agentic Evidence Graph**：六维会话事实图（task_intent / method_used / context_used / execution_path / closure_state / human_intervention），随 `CoreEvidence` sidecar 持久化（schema 1.2）
- **Action Contract Generator**：基于高频纠偏与 agentic 信号动态产出 rule/skill/workflow/checklist 草稿，替换 growth plan 固定 5 条
- **human_cost_reduction 趋势**：`SnapshotSource.human_intervention_session_rate` 持久化 + `HumanCostTrend` 跨快照 improving/worsening/flat 对比

## 修订记录

- 2026-06-04：索引补充 Agentic 架构四 Feature（v0.4-patch1）说明与阅读入口。
- 2026-05-25：创建索引。  
- 2026-05-25：补充 V2 与 12 轮 review。  
- 2026-05-26：全量索引、status 标注、指向重构契约与治理说明。
- 2026-05-26：修正跨目录链接；添加 ARCHITECTURE_PRINCIPLES；历史活动文档移至 archive。
- 2026-05-26：删除历史活动文档引用；明确 `ARCHITECTURE_PRINCIPLES.md` 为唯一架构真源。
- 2026-05-26：移除活动区 plan / review 过程稿，避免旧命名和旧分层继续外溢。
- 2026-05-26：移除与当前 DDD 真相冲突的 `AI_GROWTH_MIRROR_V2_DETAILED_DESIGN.md`。
- 2026-05-26：索引标题去旧品牌词化；阅读顺序改为当前活动区真实文档。
- 2026-05-27：文档与代码同步（Python 3.12+、CLI compare/cache、去 bak 发布边界）；传播设计 status 统一为 supporting。
- 2026-05-29：对外口径统一为 AI 成长镜；去除历史版本暴露文案，并补齐成长轨迹对比说明入口。
- 2026-06-01：架构总纲补齐 7 款工具（国际/国产分组）与产品主流程图，与仓级 README 同步。
