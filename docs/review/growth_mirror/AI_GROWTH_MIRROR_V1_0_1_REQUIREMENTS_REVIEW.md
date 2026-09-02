---
title: AI Growth Mirror v1.0.1 需求多轮 Review
domain: growth_mirror
status: canonical
document_type: review
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/plan/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_HARDENING_SPEC.md
    role: reviewed_source
---

# AI Growth Mirror v1.0.1 需求多轮 Review

## Review 范围与方法

- 被审文档：`SPEC-GROWTH-MIRROR-1.0.1-HARDENING`。
- Round 1：完整性、可验收性、Fact-to-AC 追踪和范围收敛。
- Round 2：安全、隐私、提示注入、架构与演进成本。
- Round 3：关闭性复核，确认前两轮 P0/P1 已进入冻结 Spec，且未引入新的阻断项。
- Round 6：唯一真源反证，检查 canonical owner、派生投影和第二实现。
- Round 7：关闭性复核，确认去漂移约束不会制造第三份 registry 或兼容壳。
- Review 证据等级：静态 + 契约；尚未进入设计和实现，因此 runtime/release 证据按阶段不适用。

## Round 1：完整性与可验收性

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| RR1-001 | P1 | 隐私需求只覆盖 session-read，但 prompt-quality 直接发送相同原始字段，work-focus/coaching 发送派生文本。 | REQ-001 扩展为所有 LLM user prompt 的统一出站边界；AC-001 要求覆盖四类调用。 | CLOSED |
| RR1-002 | P2 | diagnostics 只描述“稳定事件码”，没有列出词汇表。 | 保持需求层的稳定性约束；事件码清单在 SDD 冻结。 | DEFERRED_TO_SDD |
| RR1-003 | P2 | “关键持久化”需要明确文件白名单，避免实现漏项或无限扩张。 | REQ-004/AC-004 冻结 cache、report、snapshot、index 四类；具体函数在 SDD 白名单化。 | CLOSED |
| RR1-004 | P2 | 结构 checker 初次调用失败：原稿元数据/章节名不符合模板，且只传 Spec 时工具会联检内置 SDD/ADR/Task 模板。 | Spec 已按官方模板重构；完整结构检查在设计包齐备后执行。 | CLOSED_WITH_EVIDENCE_PENDING |

### Round 1 结论

- 未关闭 P0：0。
- 未关闭 P1：0。
- P2：RR1-002 进入 SDD；RR1-004 的完整工具证据等待设计包，均不阻断需求内容冻结。

## Round 2：安全、架构与演进性

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| RR2-001 | P1 | 通用路径正则不能删除 work-focus 中的裸项目名，商业项目名仍可能外发。 | REQ-001/契约/AC-001 增加源项目名匿名稳定标签。 | CLOSED |
| RR2-002 | P1 | 脱敏不能替代 prompt-injection 边界，用户文本可能尝试改变评分指令。 | 新增 SEC-005；要求不可信证据分隔、system 约束与注入 fixture。 | CLOSED |
| RR2-003 | P1 | provider 异常字符串可能回显请求正文，单纯“不记录 prompt”不足。 | SEC-005 明确异常日志只记录事件码和异常类型。 | CLOSED |
| RR2-004 | P2 | 100ms 性能门禁在共享 CI 可能抖动。 | NFR-002 保留 100ms 设计目标，CI 硬门槛放宽至 500ms并增加单遍扫描结构断言。 | CLOSED |
| RR2-005 | P2 | v1.0.1 原路线图主题调整可能误解为已交付团队聚合。 | Scope 明确只修 status 的既有多机器 cache 读取，团队聚合顺延 v1.0.2 或以后。 | CLOSED |

### Round 2 结论

- 未关闭 P0：0。
- 未关闭 P1：0。
- 未关闭 P2：0。

## Round 3：关闭性复核

检查项：

- FACT-001..FACT-011 均有范围决策，其中产品缺陷均映射 REQ/AC。
- REQ-001..REQ-008、NFR-001..NFR-007、SEC-001..SEC-005 均进入追踪矩阵。
- 主链路、失败路径、隐私、安全日志、性能、兼容、回滚、runtime/release 层级均有验收语义。
- “全部问题”边界、未跟踪 `nul` 文件、真实外部运行 `NOT_RUN` 均被显式声明。
- 未发现会迫使改变 Cache Schema、六轴权重或 CLI public contract 的需求。

结论：`PASS`。未关闭 P0/P1 为 0；允许将 Spec 标记为 `approval: frozen`，进入 SDD/ADR 阶段。

## Round 4：设计取证回灌

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| RR4-001 | P1 | `status` 历史快照固定读取 cwd，而报告支持 `report.output_dir`，会产生错误的“首次生成”。 | 新增 FACT-012；REQ-003/AC-003 冻结 snapshot archive 必须从 `report.output_dir` 解析。 | CLOSED |

结论：`PASS`。该发现属于既有 status 范围内的可观察错误，不改变版本、Schema 或公开 CLI；回灌后未关闭 P0/P1 仍为 0，可继续设计。

## Round 5：freshness 契约精化

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| RR5-001 | P1 | “mtime 增大”不能覆盖 workspace 删除、时间回拨和最大值下降。 | AC-002 改为稳定 freshness revision “发生变化”；字段形状与 Cache Schema 不变。 | CLOSED |

结论：`PASS`。这是 REQ-002 既有 freshness 语义的精化，不改变范围；未关闭 P0/P1 为 0。

## Round 6：唯一真源反证

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| RR6-001 | P0 | 文档把中文、英文同时标为 canonical，冲突时没有机器可执行的裁决顺序。 | 新增 FACT-013、REQ-009、AC-010：中文活动契约为唯一 canonical，英文为带 `canonical_path` 的 mirror。 | CLOSED |
| RR6-002 | P0 | actionable friction 规则在 runtime 与 archive 路径各有实现且集合不同，相同输入可能因入口不同得到不同结果。 | 新增 FACT-014：规则下沉到一个 domain owner，两条路径都复用；禁止保留旧私有副本。 | CLOSED |
| RR6-003 | P1 | 测试复制 `setup-uv` 的当前 SHA，action 升级需要同步两处可变值。 | 测试只验证所有 workflow action 都是 40 位 commit pin；具体 SHA 只存在 workflow。 | CLOSED |
| RR6-004 | P1 | 项目 skill 把当前版本、当前设计文件写成长期规则，已经停留在 1.0.0。 | skill 改为查询 `pyproject.toml`、`domain/cache_schema.py` 和设计索引；移除可变快照值。 | CLOSED |

结论：`PASS`。新增约束直接复用已有 owner，不新增 manifest/registry；未关闭 P0/P1 为 0。

## Round 7：范围与停止条件复核

- 英文文档继续保留用户价值，但只作为受检翻译镜像；不以删除镜像换取表面单源。
- `__version__`、`uv.lock`、README badge、配置示例属于不可避免的发布投影，由测试与 owner 对拍，不被描述为独立真源。
- snapshot 规则只做 hard cut，不保留旧函数 alias；application 不再 import infra 私有符号。
- 不改变 Product 1.0.1、Cache Schema 1.0、六轴、CLI 或 artifact shape。
- hosted CI、真实 LLM/OpenCode、浏览器仍按 `NOT_RUN` 管理，不因静态门禁通过而升级证据等级。

结论：`PASS`。Spec 1.0.5 可重新冻结并进入 SDD/ADR 补充设计；未决 P0 为 `NONE`。

## 修订记录

- 2026-09-02：完成 Round 6/7，冻结 canonical/derived 角色、snapshot 规则单源和去漂移门禁。
- 2026-09-01：设计 Review 触发 Round 5，将 OpenCode freshness 从单调 mtime 改为稳定 revision 变化契约。
- 2026-09-01：设计取证触发 Round 4，补齐 `report.output_dir` 的 status 历史定位契约并重新冻结。
- 2026-09-01：完成三轮需求 Review，关闭全部 P0/P1，冻结 Spec。
