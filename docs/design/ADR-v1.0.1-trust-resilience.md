---
title: v1.0.1 统一信任边界与韧性写入 ADR
status: canonical
document_type: adr
spec_id: SPEC-GROWTH-MIRROR-1.0.1-HARDENING
spec_version: 1.0.5
version: 1.0.4
decision_status: accepted
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/plan/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_HARDENING_SPEC.md
    role: source
  - path: docs/design/v1.0.1-DESIGN.md
    role: design
---

# ADR: v1.0.1 统一信任边界与韧性写入

English version: [ADR-v1.0.1-trust-resilience.md](../en/design/ADR-v1.0.1-trust-resilience.md)

> **文档性质**：记录 SDD 中存在真实备选方案的架构决策；只有 `decision_status: accepted` 才可进入实现。

## 修订记录

| 版本 | 日期 | 修订要点 | 备份/引用 |
|---|---|---|---|
| 1.0.4 | 2026-09-02 | 接受 DEC-004：canonical + checked mirror 与 domain snapshot projection 单源 | `docs/review/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_DESIGN_REVIEW.md` |
| 1.0.3 | 2026-09-01 | 三轮设计 Review 后接受 DEC-001 至 DEC-003 | `docs/review/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_DESIGN_REVIEW.md` |
| 1.0.0 | 2026-09-01 | 提出 DEC-001 至 DEC-003 | — |

## 状态

- 决策：DEC-001 统一 LLM user-prompt 出站边界
- 决策：DEC-002 单一 atomic I/O 与 snapshot owner hard cut
- 决策：DEC-003 合成不变量 calibration + locked cross-platform CI
- 决策：DEC-004 canonical + checked mirror；snapshot 业务投影归 domain 单源
- 状态：accepted

## 背景

REQ-001/REQ-004/REQ-005/REQ-006/REQ-007/REQ-009 不是彼此独立的小修：它们共同暴露了边界能力分散的问题。当前每个 LLM 调用点自行拼 prompt、多个模块直接写文件、infra snapshot 同时承担 application 组装、评分测试与 CI 只覆盖局部；中英文文档和 snapshot runtime/archive 映射还出现了双 owner。如果继续逐点补丁，会产生更多平行真源，难以证明 SEC-001 至 SEC-005 和 AC-001/AC-004/AC-005/AC-006/AC-007/AC-010。

## 约束

- 技术与项目指纹：Python 3.12+、本地文件产品、uv、Click/Jinja2/YAML、现有 domain/application/infra 分层。
- 业务与共享契约：Product v1.0.1 / Cache Schema 1.0；CLI、六轴和 cache 路径不变。
- 时间与成本：只处理冻结 Fact Pack；不重写 scorer/templates/readers 全域。
- 不改范围：不新增网络依赖、数据库、遥测或 compatibility shell。
- 安全与回滚：SEC-001 至 SEC-005；写失败保留旧文件，隐私失败不得发送 raw prompt。

## 备选方案

| 决策 | 方案 | 优点 | 缺点 | 风险 | 停止条件 |
|---|---|---|---|---|---|
| DEC-001 | A：各 LLM 调用点独立脱敏 | 局部改动少 | 容易漏新调用、模式漂移 | 不能证明全覆盖 | 新增第五类调用即可能失守 |
| DEC-001 | B：执行层统一清洗，上游数据最小化 | 单一强制边界，调用点仍可限制语义数据 | 需要测试 system/user 分离，过度规则可能损失语义 | 正则边界需持续校准 | system prompt 被改写或主任务词大量丢失 |
| DEC-002 | A：每个模块各自实现 temp + replace | 改动可分散 | 实现细节/错误语义重复 | 第二真源、Windows 差异 | 任一消费者行为漂移 |
| DEC-002 | B：单一 atomic primitive；snapshot 组装归 application | 写入语义唯一、分层可验证 | 需要更新多处导入和测试 | snapshot 变更半径 | artifact shape 或 CLI 行为变化 |
| DEC-003 | A：冻结整份报告 golden，只跑 Linux 单版本 | 容易建立 | 文案变化脆弱，跨平台漏检 | 高维护成本、假安全 | 小文案改动频繁破门 |
| DEC-003 | B：合成数据不变量 + Windows/Linux/Python matrix + locked uv | 直接保护评分关系和发布面 | CI 成本增加 | matrix 约四倍 | 时长超过预算再按数据拆 job，不减少平台 |
| DEC-004 | A：中英文均为 canonical；runtime/archive 各维护映射 | 局部自治 | 冲突无裁决点，规则已漂移 | 用户看到不同结果 | 任一镜像或入口发生差异 |
| DEC-004 | B：新增独立 truth registry | 关系集中 | registry 自身成为第三份需同步资产 | 多一层上下文和维护成本 | registry 与 owner 冲突 |
| DEC-004 | C：沿用现有 owner，英文为 checked mirror；业务映射归 domain | 无第三份 registry，保留英文可达性，同输入同结果 | 需要元数据/AST/行为门禁 | 一次性 hard cut 影响多文件 | public contract 或 artifact shape 变化 |

## 决策

- DEC-001 选择 B：所有 LLM user prompt 必须经过执行层统一清洗；调用点只负责数据最小化、匿名项目标签和证据分隔。
- DEC-002 选择 B：建立唯一 atomic text/JSON primitive；POSIX flush+fsync+replace，Windows flush+close+replace；snapshot orchestration hard cut 到 application，不保留 infra compatibility shell。
- DEC-003 选择 B：以版本化合成 fixture 断言 scorer 不变量，并使用 locked uv 的跨平台/跨 Python CI。
- DEC-004 选择 C：中文活动契约为唯一文档 canonical，英文为带 `canonical_path` 的受检 mirror；snapshot 业务投影下沉 domain，application/infra 只消费；测试验证 action pin 结构而不复制 SHA。旧私有函数直接删除/改名，不留 alias。

## 决策原因

### 问题前置

- 不裁决 DEC-001：下一次新增 LLM feature 时会在运行期重新暴露敏感值，届时只能靠事故发现。
- 不裁决 DEC-002：中断/磁盘错误会在用户打开报告或下一次读 cache 时才发现半文件；infra 反向依赖继续扩大。
- 不裁决 DEC-003：评分与 Windows 发布回归最晚在用户使用阶段暴露，修复成本高于 CI 阶段。
- 不裁决 DEC-004：翻译、skill、测试和 runtime/archive 会继续以“同步”为名独立演化，冲突直到发布或用户对比才暴露。
- 已暴露问题：边界覆盖错误、`O(S×W)` 预算、i18n/写入第二真源、snapshot 依赖反向、Windows/版本证据缺口。
- 未决 P0：NONE。

### 架构取舍

四个选择以高可信为第一约束：统一隐私/写入边界、calibration 和 checked projection 让负例可证明；以高效能收敛 OpenCode 算法，同时接受 CI matrix 的固定成本；以高演进和低上下文成本换取单一扩展点；以低变更成本保持 Schema/CLI/artifact；通过分层、fail closed、稳定事件码和 owner metadata 补齐可维护、安全、可观测底座。牺牲的是一次性内部 import/metadata 迁移、更多失败路径测试与 CI 时间，但这些成本在实现/发布前可见且可预算。

## 影响范围

- 代码：`infra/llm`、四类 LLM feature adapter/templates、OpenCode/cache/snapshots、application status/snapshot/report、CLI/config。
- 接口/数据/配置：新增 `report.weekly_session_target`；不新增 cache 字段；snapshot artifact shape 不变。
- 运维/可观测：稳定 `AGM-*` warning；CI 扩至四个 OS/Python 组合；无生产部署动作。
- 文档与兼容：产品 v1.0.1、Schema 1.0；中英文 README/设计/路线图同步；内部 snapshot import hard cut。
- 真源治理：中文契约 canonical、英文 mirror；项目 skill 不保存可变“当前版本”快照；CI pin 具体值只在 workflow；status catalog key schema 单源。

## 回滚方案

- DEC-001：可回调具体 pattern/长度预算，但不得移除统一执行边界或恢复原文 fallback。
- DEC-002：可把 application facade 回退到上一实现提交，但 atomic primitive 和旧文件保护必须保留；不得通过 infra→application allowlist 回滚。
- DEC-003：可按耗时拆分 CI job/缓存依赖，但不得删除 Windows、Python 3.13、locked sync、eval 或 build 任何门禁。
- DEC-004：可修正 mirror 翻译或 projection 适配器，但不得恢复双 canonical、跨层私有 import、重复业务映射或测试内 SHA 常量。
- 所有回滚先运行 AC-001、AC-004、AC-005、AC-006、AC-007、AC-009 和 AC-010。

## 后续验证

- [ ] AC-001 已覆盖 DEC-001 的四类主链、提示注入和安全日志失败链。
- [ ] AC-004/AC-005 已覆盖 DEC-002 的 replace 失败、snapshot artifact 和依赖方向。
- [ ] AC-006/AC-007 已覆盖 DEC-003 的不变量与 matrix workflow。
- [ ] AC-010 已覆盖 DEC-004 的 mirror metadata、domain projection、public import、status key parity 与 structural action pin。
