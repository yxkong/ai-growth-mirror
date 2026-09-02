---
title: AI Growth Mirror v1.0.1 实现与安全 Review
status: canonical
document_type: implementation_review
spec_id: SPEC-GROWTH-MIRROR-1.0.1-HARDENING
spec_version: 1.0.5
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/v1.0.1-DESIGN.md
    role: verifies
  - path: docs/plan/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_TASK_CONTRACT.md
    role: verifies
---

# AI Growth Mirror v1.0.1 实现与安全 Review

## Review 边界

- 覆盖：TASK-001 至 TASK-009、对应代码/测试/文档/CI/hub project skill 交付面。
- 排除：任务开始前的 hub 注册改动、用户 OpenCode 在途改动的作者归属、未跟踪 `nul`、真实 provider/真实 OpenCode 数据/浏览器/远端 GitHub Actions。
- 判定：实现门 `PASS`；发布门 `NOT_RUN`。未关闭 P0/P1：0。

## Round 1：正确性与回归

| ID | 等级 | 发现 | 修复与证据 | 状态 |
|---|---|---|---|---|
| IR1-001 | P1 | cache 旧测试仍假定 revision 只增不减，与内容 hash 语义冲突。 | 改为正 revision 不等即 stale；前进/回退/相等均有断言。 | CLOSED |
| IR1-002 | P1 | snapshot hard cut 后两个消费者仍从 infra 转发导入产品常量。 | 改为从 `product.py` 真源导入；layer + report 测试通过。 | CLOSED |
| IR1-003 | P1 | OpenCode 混合字符串/数字时间会在排序时抛错。 | 加安全时间归一与 `AGM-OPENCODE-EVENT-TIME-INVALID`；健康事件仍可解析。 | CLOSED |
| IR1-004 | P1 | 合法 JSON 但非对象的 snapshot profile 会令 `status` 崩溃。 | 增加 shape gate 和稳定 warning；历史存在但无契约时安全降级。 | CLOSED |

## Round 2：安全与故障语义

| ID | 等级 | 发现 | 修复与证据 | 状态 |
|---|---|---|---|---|
| IR2-001 | P1 | LLM retry `log_context` 可携带源 session id，存在隐私暴露/日志注入面。 | context 收敛为五个固定值，未知值回落 `llm-json`；canary caplog 证明异常正文和不可信 context 不回显。 | CLOSED |
| IR2-002 | P1 | 四类 prompt 的不可信证据边界需要防静态漂移。 | 架构测试逐一锁定 system 指令与 `UNTRUSTED_EVIDENCE_BEGIN/END`。 | CLOSED |
| IR2-003 | P1 | cache/snapshot 写失败可能破坏既有产物或留下孤儿。 | 故障注入验证旧字节保留、临时文件清理、index 失败删除本次未索引 bundle 并传播异常。 | CLOSED |
| IR2-004 | P2 | 规则脱敏无法证明识别任意自然语言业务机密。 | README 双语明确边界；高隐私场景使用 `--no-llm`。 | ACCEPTED_LIMITATION |

## Round 3：维护性、性能与发布面

| ID | 等级 | 发现 | 修复与证据 | 状态 |
|---|---|---|---|---|
| IR3-001 | P1 | Windows 全量套件由 `uv run` 包装执行时出现约 31 秒/临时目录 fixture 延迟。 | locked sync 后直接执行平台 `.venv` Python；本机 326 项约 4 秒通过；workflow contract 已锁定。 | CLOSED |
| IR3-002 | P1 | 新配置字段未出现在 `config.example.yaml`。 | 标准备份后补充 `weekly_session_target: 8` 及正整数说明。 | CLOSED |
| IR3-003 | P1 | infra 曾反向依赖 application。 | snapshot view 组装迁至 `application/snapshot_service.py`，allowlist 删除，AST 层门通过。 | CLOSED |
| IR3-004 | P2 | hosted matrix 只有 workflow 静态/本地契约证据。 | 保持 `release: NOT_RUN`，推送后观察四组合才能签发 release。 | OPEN_LIMITATION |

## Round 4：唯一真源与依赖方向

| ID | 等级 | 发现 | 修复与证据 | 状态 |
|---|---|---|---|---|
| IR4-001 | P0 | 中英文活动文档同时标为 canonical，索引还明确写“中英双真源”。 | 中文活动契约保留 canonical；所有同名英文文档改为 `status: mirror` + `canonical_path`，关键元数据动态对拍。 | CLOSED |
| IR4-002 | P0 | actionable friction 与 friction-topic 在 application/infra 两处定义，且别名集合不同。 | 新建纯 `domain/snapshots/projection.py`，runtime/archive 共用；AST 测试禁止消费者重定义。 | CLOSED |
| IR4-003 | P1 | application 导入 infra 私有 `_snapshot_source_from_payloads`。 | canonical 直接改名为 public `snapshot_source_from_payloads`，同步调用/测试，不保留 alias；layer gate 禁私有跨层 import。 | CLOSED |
| IR4-004 | P1 | status zh/en 只有文件级存在性，没有 exact key schema。 | `STATUS_LABEL_KEYS` 成为 schema owner，loader 对 missing/extra/non-string fail closed。 | CLOSED |

## Round 5：派生面与 skill 工程门

| ID | 等级 | 发现 | 修复与证据 | 状态 |
|---|---|---|---|---|
| IR5-001 | P1 | CI contract test 复制 `setup-uv` SHA，升级 action 要双改。 | 删除 SHA 常量，动态枚举全部 `uses:` 并验证 40 位 commit pin。 | CLOSED |
| IR5-002 | P1 | `config.example.yaml` 的周目标是手工投影。 | 配置测试直接对拍 `GrowthMirrorConfig` owner。 | CLOSED |
| IR5-003 | P1 | hub project skill 的“当前代码快照”仍停在 1.0.0，且把中英文称为平行真源。 | 移除可变当前值，改为 owner 查询；中文 canonical/英文 mirror；junction 不写入。 | CLOSED |
| IR5-004 | P2 | 英文逐字语义无法由 metadata test 完整证明。 | 机器锁 owner path、角色、版本/批准状态与互链；翻译语义保留人工 Review。 | ACCEPTED_LIMITATION |

## 四高二低三底座复核

| 原则 | 实现投影 | 证据 |
|---|---|---|
| 高价值 | 只关闭 Fact Pack 中可信、正确性、韧性、发布缺口 | Spec/Task 白名单；无六轴/Schema 扩张 |
| 高可信 | Red-Green、负例、故障注入、固定评分夹具、派生面变异门 | 336 tests；5 类 calibration invariants；metadata/AST/behavior checks |
| 高效能 | OpenCode `O(S+W)`、status 千记录门、CI 避开包装层慢路径 | call-count/performance tests；本地全量约 4 秒 |
| 高演进 | privacy/atomic/catalog/calibration/snapshot projection/application facade 单一真源 | AST、metadata 与行为契约测试 |
| 低上下文成本 | 稳定事件码、canonical_path、owner 查询、版本/CI 自动检查 | docs index、version/CI/skill gates |
| 低变更成本 | CLI/Schema/评分权重不变，hard cut 不留兼容壳 | Schema 1.0；layer test 无 allowlist |
| 可维护 | application/domain/infra 依赖方向恢复 | `test_layer_dependencies.py` |
| 安全 | 出站最小化、统一脱敏、不可信证据隔离、安全日志 | `test_llm_privacy.py` |
| 可观测 | 坏 cache/OpenCode/snapshot/provider 有稳定 warning 且不回显敏感正文 | caplog 与坏输入用例 |

## 证据矩阵

| 门 | 证据等级 | 实际证据 | 结论 |
|---|---|---|---|
| Spec/SDD/ADR/Task | contract | `SPEC_SDD_STRUCTURE=ok checked=4 mode=implementation-ready` | PASS |
| unit + calibration | runtime | 336 tests，退出码 0 | PASS |
| unique truth source | contract/runtime | mirror metadata、snapshot projection parity、private-import AST、status schema、structural action pin | PASS |
| project skill | contract | `SKILL_ENTRYPOINTS=ok`、`SKILL_REFERENCES_STRUCTURE=ok`、`SKILL_SIZE_OK nonempty=143 max=150` | PASS |
| compile | runtime | `.venv` Python `compileall`，退出码 0 | PASS |
| lock | contract/runtime | `uv sync --locked --extra dev`、`uv lock --check` | PASS |
| package | runtime | sdist + wheel v1.0.1 构建成功 | PASS |
| CLI version | user-visible/runtime | `python -m ai_growth_mirror.cli --version` 输出 1.0.1 | PASS |
| diff | static | `git diff --check` | PASS |
| 真实 LLM/OpenCode/browser | limitation | 本任务不读取真实私有数据、不产生外部调用 | NOT_RUN |
| hosted GitHub Actions | release | 未推送/未观察四组合 | NOT_RUN |

## 最终结论

本地实现、契约、运行、唯一真源与构建门 `PASS`；Fact Pack 范围内无未关闭 P0/P1。由于真实外部数据、浏览器和 hosted CI 未运行，整体交付为 `DONE_WITH_CONCERNS`，不得宣称 release `PASS`。
