---
title: AI Growth Mirror v1.0.1 设计多轮 Review
domain: growth_mirror
status: canonical
document_type: review
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/design/v1.0.1-DESIGN.md
    role: reviewed_sdd
  - path: docs/design/ADR-v1.0.1-trust-resilience.md
    role: reviewed_adr
---

# AI Growth Mirror v1.0.1 设计多轮 Review

## Review 范围

- SDD：`docs/design/v1.0.1-DESIGN.md`
- ADR：`docs/design/ADR-v1.0.1-trust-resilience.md`
- 上游：SPEC-GROWTH-MIRROR-1.0.1-HARDENING 1.0.4
- Round 1：覆盖性、freshness、性能与依赖方向。
- Round 2：隐私/提示注入、故障链、Windows 文件语义。
- Round 3：关闭性、回滚、四高二低三底座与可实施性。

## Round 1：覆盖与架构

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR1-001 | P1 | 执行层清洗无法阻止未来调用点绕过 `complete_json_with_retries` 直接调用 gateway。 | 增加 AST 架构门禁：除 execution/provider gateway 外禁止 `complete_json` 直接调用。 | CLOSED |
| DR1-002 | P1 | 最大 mtime 不保证单调，workspace 删除/时间回拨可能不失效。 | 对有序相对路径+原始 bytes 生成稳定 SHA-256 revision；正 revision 不等即 stale；需求 AC-002 同步回灌。 | CLOSED |
| DR1-003 | P2 | 任一 workspace 变化使全部 OpenCode cache 失效，精度较粗。 | 明确作为 v1.0.1 的正确性优先取舍；复杂度仍为 `O(S+W)`。 | ACCEPTED |

## Round 2：安全与故障链

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR2-001 | P1 | 通用绝对路径正则可能只删除含空格路径的一部分。 | `project_path` 模板变量先逐值调用同一 sanitizer，中央执行层再做兜底。 | CLOSED |
| DR2-002 | P1 | work-focus 按行生成匿名标签会让同一项目出现多个标签。 | 请求内维护 normalized path 到 `project-NN` 的映射。 | CLOSED |
| DR2-003 | P1 | snapshot staging 失败若不清理会残留临时目录。 | 只清理本任务创建且经根路径验证的精确 staging 目录。 | CLOSED |
| DR2-004 | P2 | 仅记录异常类型降低了 provider 排错细节。 | 接受安全优先；保留 log_context、attempt、类型和稳定事件码，不记录可能回显请求的异常文本。 | ACCEPTED |

## Round 3：关闭性与可实施性

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR3-001 | P2 | snapshot 目录发布成功但 index 写失败会产生长期孤儿。 | index 失败时验证并删除本次新建的未索引 snapshot，再传播失败。 | CLOSED |
| DR3-002 | P2 | 多文件 report 只能保证单文件原子，不能跨文件系统事务。 | 明确本版本契约为单 artifact 完整性；snapshot bundle 另用目录 staging。跨文件 transaction 不冒充已实现。 | ACCEPTED_LIMITATION |
| DR3-003 | P2 | 四组合 matrix 增加 CI 时间。 | 项目规模小且无系统依赖；保留四组合。超预算时可拆 job/缓存，不削减平台门禁。 | ACCEPTED |

## 追踪与原则复核

- REQ-001..REQ-008、NFR-001..NFR-007、SEC-001..SEC-005、AC-001..AC-009 均在 SDD 出现并映射验证入口。
- 高价值：无 Fact 映射的全域重构被排除。
- 高可信：隐私、坏输入、写失败、评分漂移均有 Red/负例。
- 高效能：OpenCode 明确 `O(S+W)`；status 有结构+耗时双门禁。
- 高演进：隐私、atomic、i18n、calibration、snapshot owner 均为单一扩展点。
- 低上下文/低变更成本：模块 owner、事件码、白名单和命令冻结；Schema/CLI/artifact 保持。
- 可维护/安全/可观测：零反向依赖 allowlist、fail closed、稳定安全日志。

## 结论

`PASS`。三轮结束后未关闭 P0/P1 为 0；未决 P0 为 `NONE`。SDD 可标记 `approval: frozen`，ADR 的 DEC-001 至 DEC-003 可标记 `accepted`，允许生成实现任务契约。

### Round 4：执行前路径校验

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR4-001 | P1 | 初版白名单把公开英文 README 写成不存在的 `README.en.md`。 | 以仓内链接与文件事实修正为 `en/README.md`；SDD 与 Task Contract 同步。 | CLOSED |

结论：`PASS`。路径纠正不改变设计行为，未关闭 P0/P1 仍为 0。

### Round 5：参考实现运行反馈

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR5-001 | P1 | Windows 当前文件系统上每次 `os.fsync` 实测约阻塞 30 秒，违反高效能并使报告多产物写入不可接受。 | 保留共同的 temp+flush+close+replace；仅 POSIX 执行 fsync。单文件原子性契约不变。 | CLOSED |
| DR5-002 | P1 | 隐私 canary 证明通用 `token=` 未被 secret assignment pattern 覆盖。 | 将 `token` 加入统一 sanitizer 的结构化 secret 键集合。 | CLOSED |

结论：`PASS`。参考实现 Red/首次 Green 的运行证据已回灌设计；未关闭 P0/P1 为 0。

### Round 6：实现期 CI 性能纠偏

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR6-001 | P1 | locked sync 后由 `uv run` 执行完整 Windows 套件时，临时目录 fixture 出现约 31 秒级延迟；最初误归因于 pytest 9。 | 用同一 pytest 8.4.2 对照证明直接 `.venv` 完整套件约 4 秒；撤销 pytest 上界，CI 改为 locked sync 后直接调用平台 `.venv` Python。 | CLOSED |
| DR6-002 | P2 | 文档仍写所有平台都 fsync，与 Windows 运行证据不符。 | 冻结为 POSIX fsync；Windows flush+close+replace，并由故障注入验证单文件原子性。 | CLOSED |

结论：`PASS`。未关闭 P0/P1 为 0；远端 hosted CI 仍为 `NOT_RUN`。

## 修订记录

- 2026-09-02：完成 Round 7/8，关闭 canonical/mirror 角色、snapshot projection 与自动门禁的设计问题。
- 2026-09-01：完成三轮设计 Review 并冻结 SDD/ADR。
- 2026-09-01：执行前路径校验完成 Round 4，修正英文 README 真路径。
- 2026-09-01：参考实现运行反馈完成 Round 5，校准 Windows 原子写持久性/性能取舍并补齐 token 模式。
- 2026-09-02：实现期 Round 6 关闭 CI 包装层性能误判，撤销无依据 pytest 上界并同步 SDD 1.0.4。

### Round 7：唯一真源架构反证

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR7-001 | P0 | 仅在文档写“中文优先”不能阻止英文继续自称 canonical。 | 英文活动文档统一 `status: mirror` + `canonical_path`；自动发现同名中文 owner 并校验路径/关键元数据。 | CLOSED |
| DR7-002 | P0 | 将 runtime/archive 映射任选一处作为 owner 会造成错误分层或 application 反向依赖。 | 新增 `domain/snapshots/projection.py`，只承载纯业务映射；application 与 infra 都向 domain 依赖。 | CLOSED |
| DR7-003 | P1 | 只把 `_snapshot_source_from_payloads` 改成 public 仍可能保留旧私有 alias。 | 直接改 canonical 名并同步调用/测试；AST 门禁禁止 application import infra 下划线符号。 | CLOSED |
| DR7-004 | P1 | 新建“真源清单”能集中说明，但会成为第三份会漂移的资产。 | 拒绝 registry；owner 表只写入现有 canonical SDD/架构文档，测试从目录/代码动态发现。 | CLOSED |

结论：`PASS`。依赖方向保持 CLI/Application → Infra/Domain，Domain 不依赖上层；未关闭 P0/P1 为 0。

### Round 8：门禁可杀死性与变更成本

| ID | 等级 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| DR8-001 | P1 | 测试若复制当前 action SHA，只会把漂移变成双改。 | 正则枚举 workflow 的全部 `uses:`，要求每项 `@<40 hex>`；具体 SHA 仅由 workflow 定义。 | CLOSED |
| DR8-002 | P1 | i18n 只检查 zh/en 文件存在不能阻止缺 key/额外 key。 | `STATUS_LABEL_KEYS` 成为 schema owner，loader 对 catalog exact set fail closed，双语测试覆盖。 | CLOSED |
| DR8-003 | P1 | hub skill 的版本快照即使本轮改成 1.0.1，下次仍会漂移。 | 删除可变“当前值”，改为 owner 查询路径；skill 工程门验证入口、结构和尺寸。 | CLOSED |
| DR8-004 | P2 | 全量英文逐字一致无法可靠自动化。 | 机器只锁角色、owner path、版本/批准等关键 metadata 与互链；语义翻译保留人工 Review，不伪装成逐字同构。 | ACCEPTED_LIMITATION |

结论：`PASS`。设计符合高可信、高演进、低上下文与低变更成本；未决 P0 为 `NONE`，可进入实现。
