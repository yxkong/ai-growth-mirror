---
title: AI Growth Mirror v1.0.2 设计多轮 Review
domain: growth_mirror
status: canonical
document_type: review
version: 1.0.0
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/v1.0.2-DESIGN.md
    role: reviewed_design
  - path: docs/design/ADR-v1.0.2-assessment-policy-and-root-task.md
    role: reviewed_decision
---

# AI Growth Mirror v1.0.2 设计多轮 Review

## 1. 判据

- Review 只证明设计达到 implementation-ready，不证明代码、运行、发布已完成。
- PASS 条件：REQ/NFR/SEC 全覆盖；未决 P0 为 NONE；无多真源/隐式兼容；公式有因果与 anti-gaming 约束；外部失败链安全可观测。

## 2. Round 1 — DDD 边界与依赖方向

### Findings

1. 仅把 scorer 拆文件不等于 DDD；必须先明确 Session Observation、Growth Assessment、Learning Loop 的语言与 ownership。
2. 将 composition root 另建为公开入口会与现有 orchestrator 形成双主链。
3. 延迟解析若继续由 SessionRecord 持有 adapter/cache，领域仍被基础设施污染。

### 修订

- SDD §2/3 明确三上下文、领域对象、端口和禁止项。
- 保持 `application/orchestrator.generate_report_artifacts` 唯一业务编排；composition 只注入端口。
- SessionRecord 纯化；延迟 materialization 只能存在 infra/port implementation。
- 增加 layer/second-source AST gates。

结论：`REVISION_REQUIRED → 已修订`。

## 3. Round 2 — 指标数学、逻辑与可解释性

### Findings

1. “动态重归一”若不同时输出 coverage，会让少量证据的 90 分看似与完整证据等价。
2. file/session 即使保留为辅助，也可能被无限堆文件游戏化。
3. agentic feature 存在性不等于能力；委派失败、Skill 无结果不能奖励。
4. 总分 hidden modifier/floor 会破坏 component 到结果的可解释链。

### 修订

- 值对象同时输出 availability、coverage、confidence、evidence count、reason codes。
- 文件信号低权重且饱和；超过阈值不涨分。
- delegation/Skill/Goal/Hook/Plan 必须绑定根任务 outcome/verification。
- 删除 asset bonus、consistency modifier 和 level floor；总分只做一次加权。
- 新增 token/files/tools/models/subagents 变换不涨分的 metamorphic gate。

结论：`REVISION_REQUIRED → 已修订`。

## 4. Round 3 — Reader、隐私、性能与演进

### Findings

1. DSH 默认是 concatenated Zstd frames，普通一次性 decompress 不能证明覆盖；packed rows 也可能重复 logical data。
2. ZCode 有多个本地数据面，若 schema 失败后读 rollout，会扩大隐私和漂移面。
3. root roll-up 若只处理一层 child 或按时间猜 parent，会重复/误归属。
4. silent catch 会让“支持工具”与“实际解析 0 条”无法区分。

### 修订

- Zstd 流式 reader；只消费 logical events；header/version/seq gate。
- ZCode 只读 CLI DB + required schema；明确禁止 tasks-index/model-io fallback。
- parent graph 递归、去重、cycle/depth/orphan fail closed。
- structured diagnostics 冻结 detected/parsed/skipped/corrupt/schema_mismatch/orphan。
- 增加 15MB 时间/内存预算和日志 canary。

结论：`REVISION_REQUIRED → 已修订`。

## 5. Round 4 — 真源、迁移、闭环与回退

### 反证结果

| 问题 | 结果 |
|---|---|
| policy 的任何消费者是否能自行定义权重/阈值？ | 不能；只能 import owner 或消费 assessment，AST gate 阻断 |
| 工具目录是否仍有 CLI/list 两份？ | 不能；CLI/all/status 从 catalog 派生 |
| policy 变化后历史是否静默比较？ | 不会；legacy/不同 version 明确 incomparable |
| 训练是否只是建议文本？ | 不是；绑定弱 component、动作、成功信号和下期状态 |
| reader 失败是否会降级到不安全源？ | 不会；fail closed 并给诊断，其它 reader 继续 |
| DDD 是否扩大为全仓重写？ | 没有；只切主链已证实泄漏与真源 |
| 回退是否恢复第二真源？ | 不允许；policy 语义变化必须新版本 |

### 四高二低三底座 Review

| 透镜 | Review 结论 |
|---|---|
| 高价值 | why→action→next check 是用户闭环；不以更多指标替代价值 |
| 高可信 | missing、anti-gaming、policy comparable、格式 gate 完整 |
| 高性能 | header/stream/query 设计有数字预算 |
| 高演进 | external capability probe 与 policy version 解耦 |
| 低上下文 | policy/catalog/orchestrator 单 owner |
| 低变更 | Cache Schema 1.0、主链 hard cut、无全仓迁移 |
| 可维护 | bounded context、值对象、ACL、依赖测试 |
| 安全 | read-only、禁 reasoning/body/fallback、canary |
| 可观测 | reader 计数、axis coverage/confidence/reasons |

## 6. 实施准备检查

- [x] Spec 冻结且 requirement review PASS。
- [x] SDD 的边界、数据、公式、错误、性能、安全、迁移、回退完整。
- [x] ADR 的真实备选方案与后果已接受。
- [x] Task Contract 有顺序、写入边界、Red/Green 和完成判据。
- [x] AC-001~012 全部映射到验证。
- [x] 未决 P0：`NONE`。

最终结论：`DESIGN REVIEW PASS`。允许进入 TDD 实现；任何新增 policy 语义、Cache Schema 变化或外部 fallback 必须退回 Spec/ADR。
