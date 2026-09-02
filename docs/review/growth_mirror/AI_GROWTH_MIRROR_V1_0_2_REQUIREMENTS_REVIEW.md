---
title: AI Growth Mirror v1.0.2 需求多轮 Review
domain: growth_mirror
status: canonical
document_type: review
version: 1.0.0
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/plan/growth_mirror/AI_GROWTH_MIRROR_V1_0_2_DDD_EXPLAINABLE_ASSESSMENT_SPEC.md
    role: reviewed_spec
---

# AI Growth Mirror v1.0.2 需求多轮 Review

## 修订记录

| 版本 | 日期 | 修订要点 | 备份/引用 |
|---|---|---|---|
| 1.0.0 | 2026-09-02 | 完成四轮需求反证与冻结审查 | — |

## 1. Review 范围与判据

- 范围：DDD 边界、六轴指标逻辑、解释/训练闭环、DeepSeek Harness/ZCode reader、隐私/演进/性能。
- 判据：不存在未决 P0；事实/假设/未知分离；每个 REQ/NFR/SEC 有验收；不新增并行真源；不把工具流行度当能力。
- 非结论：本 Review 不证明代码已实现，不证明真实人群统计校准完成，不证明已发布。

## 2. Round 1 — 价值、边界与真源

### Findings

1. 原提法“严格 DDD”若不限定边界，会诱发全仓形式化迁移；已收缩为主链中的领域泄漏、评分真源和外部 ACL。
2. 原评分权重在 scorer/comparison 分散，capability 还有备用公式；会导致同名指标不同值。
3. “新增 reader”若只注册 CLI，会漏掉 root/child 语义、schema 演进和隐私失败链。

### 修订

- 新增 REQ-005/014/015，冻结 canonical policy、DDD 依赖与 adapter catalog。
- 新增 RISK-002，禁止以 DDD 名义重写无关模块。
- 分析单位明确为 root task，子会话只汇总证据。

### 结论

`REVISION_REQUIRED → 已修订`。

## 3. Round 2 — 指标数学、因果与 anti-gaming

### Findings

1. effective contract 在 framing 中重复进入；compliance denominator=0 时返回 1.0，属于 missing-as-perfect。
2. goal-locking turns 缺失时返回 100；adaptive recovery 无机会时可因默认值获得高分。
3. token 总量、文件总量、commit、工具/模型多样性、subagent 次数能抬分，但都不等价于有效结果。
4. consistency modifier、asset bonus、L4/L5 floor 同时存在，解释复杂且形成离散跃迁。
5. 所有轴共用 session_count confidence，无法表达某轴其实没有相应证据。

### 修订

- 新增 REQ-006~010：missing 动态排除、机会条件、移除 raw-volume reward、能力信号与结果证据绑定。
- 新增 `MetricObservation/AxisAssessment` 契约；coverage/confidence 按轴计算。
- 新增 AC-006/007 metamorphic invariants：只增加消耗/调用次数不得涨分。
- 新增 policy version 与跨版本 incomparable。

### 反方复核

- 是否会因此惩罚高强度专家？不会；高强度仍进入 usage/节奏说明，但成熟度只由可复现的结果/方法证据提升。
- 是否会因没有故障而没有 recovery 分？会显示 unavailable，并在总分中按可用轴重归一，不把“没遇到问题”误判为恢复能力差或强。

### 结论

`REVISION_REQUIRED → 已修订`。

## 4. Round 3 — 当前趋势、reader 事实与安全

### Findings

1. DeepSeek Harness 官方默认 Zstd，且 format v0 无兼容承诺；只支持 raw JSONL 会形成假支持。
2. DSH packed rows 与 logical events 并存；reader 不应依赖 reasoning chunk 得出业务信号。
3. ZCode 存在 desktop task index、CLI DB、rollout 等多个文件；model-io rollout 含 headers，不应作为产品主源。
4. Goal、Plan、Skill、Subagent、Hook 是当前趋势，但按存在次数加分会奖励“功能陈列”。

### 修订

- DeepSeek 同时覆盖 raw/Zstd、header/version/seq corruption、root/child roll-up。
- ZCode 以 CLI SQLite required schema 为事实源；desktop index 仅索引，rollout 禁用。
- 趋势信号进入 Method/Orchestration 证据，但与验证/交付绑定。
- 增加 SEC-001~004 与 NFR-004。

### 结论

`REVISION_REQUIRED → 已修订`。

## 5. Round 4 — 完整性与实施准备

### 反证问题

| 问题 | 结论 |
|---|---|
| 哪个 fact 其实是 assumption？ | ZCode runtime DB owner 与 DSH logical event 完整性保留为 ASM-001/002，并有对拍关闭动作 |
| 哪个 P0 可缩成更小闭环？ | 不做全仓重写；只修主链 DDD、policy、两个 reader、解释/趋势门 |
| 哪个失败链无恢复动作？ | unknown format/schema/corrupt/缺依赖/跨 policy 均有可观察状态和后续动作 |
| 哪个安全约束只有口号？ | SEC 均落到 path、read-only、redaction、negative fixture |
| 哪个性能目标无数字？ | NFR-001/002 已给时间和内存预算 |
| 哪个需求改变共享契约？ | assessment policy/snapshot 可比性明确版本化；Cache Schema 变化被列为停止条件 |
| 哪个需求无验收？ | REQ/NFR/SEC 均进入 §11 与 AC-001~012 |

### 四高二低三底座前置检查

| 透镜 | 已暴露问题 | 需求决策 |
|---|---|---|
| 高价值 | 体量分不帮助用户进步 | 只奖励结果、验证、复用方法和有效恢复 |
| 高可信 | missing 送分、跨策略比较 | observation availability + policy version + fail closed |
| 高性能 | Zstd 大日志/SQLite 并发 | header 索引、流式解析、只读查询、root roll-up |
| 高演进 | developer preview/schema 变化 | capability probe，不兼容猜测，不双写 |
| 低上下文成本 | 权重/工具列表多真源 | policy/catalog 单一 owner |
| 低变更成本 | 全仓 DDD 重写风险 | 只切主链真实边界，保留现有报告编排 |
| 可维护 | scorer 巨型、domain 懒加载 | 领域服务/值对象/ACL，层依赖测试 |
| 安全 | 会话/headers/credentials | allowlist + read-only + redaction + 不执行内容 |
| 可观测 | reader 跳过无原因、轴无 coverage | structured diagnostics + axis evidence |

### 最终状态

- 未决 P0：`NONE`
- Spec 追踪：`COMPLETE`
- 需求 Review：`PASS`
- 可进入：SDD + ADR + Task Contract 设计阶段
