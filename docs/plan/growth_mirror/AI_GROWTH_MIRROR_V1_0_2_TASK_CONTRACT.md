---
title: AI Growth Mirror v1.0.2 DDD 可解释评估实现 Task Contract
status: canonical
document_type: task_contract
spec_id: SPEC-GROWTH-MIRROR-1.0.2-DDD-EXPLAINABLE-ASSESSMENT
spec_version: 1.0.0
design_version: 1.0.0
version: 1.0.0
created: 2026-09-02
updated: 2026-09-02
---

# Task Contract: AI Growth Mirror v1.0.2

## 1. 目标与授权边界

- 目标：按 SDD/ADR hard cut 实现单一评分政策、DDD 主链、DeepSeek Harness/ZCode readers、解释/训练闭环与项目 skill 优化。
- 写入：本仓代码/测试/文档/版本资产，以及已登记 hub 中 `ai-growth-mirror-dev` 真源和 Gate 5 Replay。
- 禁止：reset/stash/clean、删除冻结 inventory、读写 credentials/model-io、提交/推送/发布、修改生产或远端状态。
- 脏区规则：只 patch 目标文件；已有变更逐文件保留，不以格式化覆盖无关内容。

## 2. 顺序与门禁

| Task | 输入 | 产物 | Red/验收 | 状态初值 |
|---|---|---|---|---|
| T1 Policy VO | Spec REQ-005~010；SDD §4.1~4.3 | assessment policy/value objects/service | missing、anti-gaming、weights、confidence tests | READY |
| T2 Domain hard cut | REQ-014 | pure SessionRecord；capability/scorer projection | layer/second-formula tests | BLOCKED_BY_T1 |
| T3 DSH ACL | REQ-001/002 | raw+zstd reader、root roll-up、diagnostics | golden/negative/perf/privacy | READY |
| T4 ZCode ACL | REQ-001/003 | read-only SQLite reader、probe/roll-up | golden/schema/read-only/privacy | READY |
| T5 Catalog | REQ-015 | canonical registry + CLI derivation | drift/alias tests | BLOCKED_BY_T3_T4 |
| T6 Explain/Loop | REQ-011~013 | sidecar/view/i18n/policy compare/action criteria | snapshot/user-visible tests | BLOCKED_BY_T1 |
| T7 Skill/docs/version | REQ-016 | hub skill reference/routes；1.0.2 projections | baseline/held-out/skill/version gates | BLOCKED_BY_T1_T5_T6 |
| T8 Closure | AC-001~012 | full test/compile/CLI/render/review/replay | all runtime gates exit 0 | BLOCKED_BY_ALL |

## 3. 实现约束

- TDD：每个逻辑切片先记录当前失败，再做最小 Green；测试不能复制 owner 值形成第二真源。
- DDD：domain 无 adapter/cache/path/sqlite/zstd/render/I/O；reader 无评分；application 只编排和解释。
- 真源：policy/catalog/orchestrator 各一个 owner；无 compatibility alias、dual write 或 fallback formula。
- 指标：missing 不送分；体量不送分；趋势功能需绑定 outcome/verification；跨 policy fail closed。
- readers：只读、流式、root roll-up；错误日志无正文；unknown format/schema 不猜。
- 文档/skill：修改既有资产前 `backup-file`；workspace skill junction 不作为 owner。

## 4. 验证命令与通过判据

| 层级 | 命令/动作 | 判据 |
|---|---|---|
| targeted | 新 reader/policy/explanation/snapshot/layer tests | Red 有根因；Green 全部 exit 0 |
| unit/eval | `.venv` Python `-m pytest tests/unit tests/evals -q` | 全部通过，无跳过核心用例 |
| static | `python -m compileall -q ai_growth_mirror`、drift/AST gates | exit 0，无第二真源 |
| CLI | 脱敏 fixture + 本机 DSH/ZCode 只读 smoke | parsed/diagnostics 合理，无内容泄露 |
| user-visible | 生成 HTML/JSON 并检查 policy/coverage/why/action | 主链可打开、字段一致 |
| skill | entrypoint/structure/size + baseline/held-out | 全门通过 |
| release | GitHub Actions/发布 | 本轮 `NOT_RUN`，不得冒充完成 |

## 5. 输出状态

- `PASS`：AC-001~012 的 local static/contract/runtime/user-visible 均有证据，release 单列 `NOT_RUN`。
- `BLOCKED`：真实格式与声明不符且第三次仍无法在授权边界内关闭，或必须升级 Cache Schema/外部写入。
- `FAIL`：任何 P0 未关闭、第二真源存在、隐私负例失败、全量回归失败。
