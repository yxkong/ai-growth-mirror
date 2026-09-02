---
title: v1.0.2 单一评估政策与根任务反腐层 ADR
status: canonical
document_type: adr
spec_id: SPEC-GROWTH-MIRROR-1.0.2-DDD-EXPLAINABLE-ASSESSMENT
spec_version: 1.0.0
version: 1.0.0
decision_status: accepted
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/v1.0.2-DESIGN.md
    role: design
---

# ADR: v1.0.2 单一评估政策与根任务反腐层

English version: [ADR-v1.0.2-assessment-policy-and-root-task.md](../en/design/ADR-v1.0.2-assessment-policy-and-root-task.md)

## 1. 背景

现状同时存在第二套 capability 公式、两份轴权重、missing-as-perfect、体量奖励和跨语义快照比较；外部 Agent 工具又从单会话转向 Goal/Plan/Skill/Subagent/Hook 与可恢复事件流。若继续按文件格式和工具次数补丁，评分会漂移，子会话会重复计分，用户也无法理解原因。

## 2. 决策

| ID | 决策 | 选择 |
|---|---|---|
| DEC-101 | 评分政策 | 一个 versioned `assessment_policy` owner；scorer/capability/comparison 只消费，不复制 |
| DEC-102 | 缺失与总分 | missing=unavailable；component/axis 动态重归一；coverage 不足整轴不可用 |
| DEC-103 | 能力证据 | 只奖励结果、验证、结构化方法和有效恢复；raw token/files/commits/tool/model/subagent counts 不直接奖励 |
| DEC-104 | 分析单位 | user-visible root task；child session 证据向根汇总一次 |
| DEC-105 | 外部接入 | DeepSeek/ZCode 通过版本化 ACL/capability probe；未知格式 fail closed，无私密 fallback |
| DEC-106 | 历史演进 | snapshot 携带 policy version；不同版本不可比，不双写兼容评分 |

## 3. 备选与取舍

| 决策 | 备选 | 否决原因 |
|---|---|---|
| DEC-101 | scorer、capability、comparison 各自维护方便的公式 | 已形成实际漂移；用户无法知道哪份定义有效 |
| DEC-102 | missing=0 或 missing=100 | 分别把未观测误判为失败或成熟；两者均破坏因果 |
| DEC-103 | 用调用量代表 Agentic 熟练度 | 奖励成本和功能陈列，可被无结果调用游戏化 |
| DEC-104 | 每个 session 独立评分 | 多 Agent 工具会把一个用户任务重复计算，模型切换也改变样本数 |
| DEC-105 | 尽力猜字段或读 ZCode rollout fallback | preview/schema 漂移会静默污染结果；rollout 含高敏请求/响应 |
| DEC-106 | 在同一 policy version 原地修公式 | 历史 delta 失真，无法证明趋势 |

选择牺牲了历史连续曲线和对未知格式的“看似可用”，换取可解释、可审计和可演进。产品以新 policy 建立基线，不伪造可比性。

## 4. DDD 影响

- Session Observation 拥有 root/child 统一语义；reader 是 ACL，不是领域模型。
- Growth Assessment 拥有 observation、axis、policy 和 assessment service；任何展示文案在 application。
- Learning Loop 只消费同 policy 的 assessment，形成 action contract 与 outcome。
- `SessionRecord` 移除 adapter/cache 生命周期；infra 可维护延迟 materialization 对象，但不能渗入 domain。
- `application/orchestrator.generate_report_artifacts` 保持唯一业务主编排，避免 composition root 演变为第二 pipeline。

## 5. 四高二低三底座裁决

- 高价值/可信：优先关闭体量分、missing 分和伪趋势，而不是增加更多漂亮指标。
- 高性能/演进：流式 Zstd、SQLite 定向查询和 capability gate；不为未知版本维护永久兼容层。
- 低上下文/变更：一个 policy、一个 catalog、一个 root 语义；Product 1.0.2，Cache Schema 1.0。
- 可维护/安全/可观测：依赖门禁、只读 ACL、隐私日志、结构化诊断和每轴 coverage。

## 6. 后果与约束

- 正向：指标可追溯、reader 可扩展、跨工具不因物理 session 数不同而失真。
- 成本：需一次性删除备用公式和旧修饰器；旧 snapshot 与新报告出现明确断点。
- 硬约束：policy 任意语义变化必须新版本 + ADR + invariance；禁止 alias/双写/旧公式 fallback。
- 未决 P0：`NONE`。

## 7. 回退与验证

- 回退 reader 不得改变评分政策；回退 policy 必须恢复完整 2.0 实现与版本，不能混搭。
- 验证以 second-source scanner、metamorphic calibration、cross-policy gate、root roll-up golden、privacy negative 为准。
- 发布前 unit/eval/compile/CLI/render 必须全部通过；远端 release 未执行仍标 `NOT_RUN`。
