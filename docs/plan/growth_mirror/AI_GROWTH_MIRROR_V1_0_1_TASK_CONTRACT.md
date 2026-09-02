---
title: AI Growth Mirror v1.0.1 可信与韧性加固 Task Contract
status: canonical
document_type: task_contract
spec_id: SPEC-GROWTH-MIRROR-1.0.1-HARDENING
spec_version: 1.0.5
version: 1.0.3
approval: frozen
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/design/v1.0.1-DESIGN.md
    role: source
  - path: docs/design/ADR-v1.0.1-trust-resilience.md
    role: decision
---

# Task Contract: AI Growth Mirror v1.0.1 可信与韧性加固

> **文档性质**：连接 frozen Spec/SDD 与 `delivery-workflow` 实现；本 Contract 已冻结，任何白名单外实现先回到设计。

## 修订记录

| 版本 | 日期 | 修订要点 | 备份/引用 |
|---|---|---|---|
| 1.0.3 | 2026-09-02 | 唯一真源增量：新增 TASK-009、canonical/mirror 与 snapshot projection 白名单 | 设计 Review Round 7/8 |
| 1.0.2 | 2026-09-02 | 收口 Review：补入配置示例与 revision 语义回归测试白名单 | 代码/安全 Review |
| 1.0.1 | 2026-09-02 | 实现期 Review：全量门改为 locked sync 后直接调用平台 `.venv` Python；澄清代码 checkpoint 与文档备份边界 | 设计 Review Round 6 |
| 1.0.0 | 2026-09-01 | 冻结 TASK-001 至 TASK-008 范围、TDD、参考实现与验收 | — |

## 任务目标

- TASK-001：实现 REQ-001，交付 AC-001 的全 LLM 出站隐私最小闭环。
- TASK-002：实现 REQ-004 的 atomic I/O 参考实现并扩展到白名单消费者，交付 AC-004。
- TASK-003：实现 REQ-002，交付 AC-002 的 OpenCode 正确性、freshness 与线性采集。
- TASK-004：实现 REQ-003，交付 AC-003 的多机器 status、output_dir、i18n 与配置。
- TASK-005：实现 REQ-005，交付 AC-005 的 snapshot 分层 hard cut。
- TASK-006：实现 REQ-006，交付 AC-006 的 calibration 门禁。
- TASK-007：实现 REQ-007，交付 AC-007 的 locked cross-platform CI/build。
- TASK-008：实现 REQ-008，交付 AC-008；最后执行 AC-009 全量收口。
- TASK-009：实现 REQ-009，交付 AC-010 的 canonical/mirror、snapshot projection、status schema、CI pin 与 project skill 去漂移闭环。

## 路由

fullstack。实现节奏由 `delivery-workflow` 主导；领域实现使用 `ai-growth-mirror-dev` §开发入口协议、§版本一致性协议、§中英双语文档发布协议；行为变更使用 `tdd-workflow`；已有文档/脚本改前使用 `doc-script-governance`。

## 输入

- Spec：SPEC-GROWTH-MIRROR-1.0.1-HARDENING 1.0.5
- SDD：`docs/design/v1.0.1-DESIGN.md` 1.0.5 frozen
- ADR：DEC-001 / DEC-002 / DEC-003 / DEC-004 accepted
- 项目技能：`ai-growth-mirror-dev` §开发入口协议、§版本一致性协议、§中英双语文档发布协议
- 事实锚点：FACT-001 至 FACT-012，其中 FACT-010/FACT-011 是基线与工作区约束

## 范围

### 只允许改

实现模块：

- `ai_growth_mirror/infra/llm/privacy.py`
- `ai_growth_mirror/infra/llm/execution.py`
- `ai_growth_mirror/infra/extractors/llm.py`
- `ai_growth_mirror/infra/extractors/prompt_quality.py`
- `ai_growth_mirror/infra/llm/work_focus.py`
- `ai_growth_mirror/infra/llm/coach.py`
- `ai_growth_mirror/assets/prompts/session_read/*.md.j2`
- `ai_growth_mirror/assets/prompts/prompt_lens/*.md.j2`
- `ai_growth_mirror/assets/prompts/work_focus/*.md.j2`
- `ai_growth_mirror/assets/prompts/growth_coach/*.md.j2`
- `ai_growth_mirror/infra/io/__init__.py`
- `ai_growth_mirror/infra/io/atomic.py`
- `ai_growth_mirror/infra/cache/store.py`
- `ai_growth_mirror/domain/session/model.py`
- `ai_growth_mirror/infra/readers/opencode.py`
- `ai_growth_mirror/application/status_view.py`
- `ai_growth_mirror/application/label_catalogs.py`
- `ai_growth_mirror/application/snapshot_service.py`
- `ai_growth_mirror/application/personal_report_service.py`
- `ai_growth_mirror/application/orchestrator.py`
- `ai_growth_mirror/infra/snapshots.py`
- `ai_growth_mirror/config.py`
- `config.example.yaml`
- `ai_growth_mirror/cli.py`
- `ai_growth_mirror/assets/i18n/status_zh.yaml`
- `ai_growth_mirror/assets/i18n/status_en.yaml`
- `ai_growth_mirror/domain/snapshots/projection.py`

测试与交付面：

- `tests/unit/test_llm_privacy.py`
- `tests/unit/test_atomic_io.py`
- `tests/unit/test_opencode_reader.py`
- `tests/unit/test_cli_status.py`
- `tests/unit/test_config.py`
- `tests/unit/test_cache_store.py`
- `tests/unit/test_cache_freshness.py`
- `tests/unit/test_layer_dependencies.py`
- `tests/unit/test_personal_growth_report.py`
- `tests/unit/test_report_generation_service.py`
- `tests/unit/test_version_alignment.py`
- `tests/unit/test_ci_contract.py`
- `tests/unit/test_snapshot_projection.py`
- `tests/evals/fixtures/scoring_calibration_v1.json`
- `tests/evals/test_scoring_calibration.py`
- `.github/workflows/unit-tests.yml`
- `pyproject.toml`、`uv.lock`、`ai_growth_mirror/__init__.py`
- `README.md`、`en/README.md`
- `docs/README.md`、`docs/en/README.md`
- `docs/config/OPEN_SOURCE_GOVERNANCE.md`、`docs/en/config/OPEN_SOURCE_GOVERNANCE.md`
- `docs/design/ARCHITECTURE_PRINCIPLES.md`、`docs/en/design/ARCHITECTURE_PRINCIPLES.md`
- `docs/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md`、`docs/en/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md`
- `docs/design/README.md`、`docs/en/design/README.md`
- `docs/design/PRODUCT_ROADMAP.md`、`docs/en/design/PRODUCT_ROADMAP.md`
- `docs/design/v0.6.0-DESIGN.md`、`docs/en/design/v0.6.0-DESIGN.md`
- `docs/design/v0.7.0-DESIGN.md`、`docs/en/design/v0.7.0-DESIGN.md`
- `docs/design/v0.8.0-DESIGN.md`、`docs/en/design/v0.8.0-DESIGN.md`
- `docs/design/v0.8.1-DESIGN.md`、`docs/en/design/v0.8.1-DESIGN.md`
- `docs/design/v1.0.0-DESIGN.md`、`docs/en/design/v1.0.0-DESIGN.md`
- `docs/design/AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md`、`docs/en/design/AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md`
- 本任务新建的 Spec/SDD/ADR/Task/Review 文档。
- hub canonical skill：`skills/projects/ai-growth-mirror/ai-growth-mirror-dev/{SKILL.md,README.md,references/INDEX.md,references/architecture_and_layers.md,references/product_and_scoring_model.md}`；仓内 `.agents/skills/...` 仅为 junction，不在挂载入口写入。

### 禁止改

- `ai_growth_mirror/domain/cache_schema.py`、六轴权重/公式、既有 CLI command names。
- 除 OpenCode 外的 reader 行为；与 FACT/REQ 无关的 HTML/CSS/模板重构。
- `docs/review/growth_mirror/REPORT_VALUE_RECOVERY_INVENTORY.md`。
- `.cursorrules`、`AGENTS.md`、`CLAUDE.md`、`.gitignore` 及任务开始前属于用户/hub 的其他修改。
- 未跟踪 `nul` 文件、真实 OpenCode/LLM 数据、仓外路径、hub prompts。

### 越界处理

- 白名单外改动先停止并更新 Contract。
- 与用户/历史改动冲突时保留现状并标 NEEDS_CONTEXT。
- 代码与设计冲突时先裁决真源，不用兼容层掩盖。
- 需要 Cache Schema/六轴/CLI 变化、删除用户文件、真实网络调用时停止并请求人工裁决。

## 契约

| 契约面 | 冻结内容 | 关联需求 |
|---|---|---|
| LLM privacy | 全部 feature user prompt 经统一 sanitizer；static system 不改写；无 raw fallback | REQ-001 / SEC-001, SEC-002, SEC-005 |
| freshness | 正 revision 不相等即 stale；OpenCode revision 来自有序来源内容 | REQ-002 / NFR-001 |
| status | 三元组去重、`report.output_dir`、catalog、positive target | REQ-003 / NFR-002, NFR-006 |
| persistence | same-dir temp + fsync + replace；snapshot staging/index-last | REQ-004 / SEC-004 |
| layering | infra 到 application import 为 0；snapshot owner hard cut | REQ-005 / NFR-006, NFR-007 |
| calibration | schema 1.0 synthetic invariants，经唯一 `aggregate` | REQ-006 / NFR-007 |
| CI/release | locked uv、4 matrix、unit+eval、compile、build | REQ-007 / NFR-003 |
| version | Product 1.0.1 / Cache Schema 1.0，中英文一致 | REQ-008 / SEC-003 |
| truth source | 中文 canonical / 英文 checked mirror；domain snapshot projection；status key schema；workflow pin value 单点；project skill 查询 owner | REQ-009 / NFR-008 |

## Project Contract

- 触发原因：APPLICABLE（业务仓与已登记 hub project skill 的事实契约联动；无共享 API/DB）。
- 当前真源：本仓 `pyproject.toml`、`domain/cache_schema.py`、冻结 Spec/SDD/ADR。
- 参与项目/技能：ai-growth-mirror 与 hub canonical project skill；`delivery-workflow` + `ai-growth-mirror-dev` + `skill-engineering` + `doc-script-governance`。
- owner 裁决：业务代码/`pyproject.toml`/中文 canonical docs 为产品事实；hub skill 只保存稳定查询入口与边界，不复制可变当前值；仓内 junction 不是真源。
- 差异与裁决：Cache Schema 与产品版本独立；本次只 bump 产品 patch，不迁移 cache。

## 参考实现门

- Reference target：TASK-001 的 `privacy.py + execution.py` 和 TASK-002 的 `atomic.py + CacheStore`。
- 不可变契约：raw prompt 不出站、system 不改写、旧文件写失败不变、无临时残留。
- Representative sample：含空格 Windows path + Unix path + canary token + injection 的单次 LLM 请求；replace 故障下的既有 record。
- 第一批白名单：上述 reference target 与对应两份新测试；黑名单为其他消费者。
- 第一批 Green 后必须先 Review API、错误语义、日志与 Windows 路径，再允许推广到其余调用点/文件写入点。
- 停止条件：需要第二清洗器/第二 atomic helper、system prompt 被改写、测试只能依赖真实数据、旧文件无法保留。

## 验收标准

| Task | 验收项 | 主链/失败链 | 通过判据 |
|---|---|---|---|
| TASK-001 | AC-001 | 四类 LLM + injection/provider error | mock/caplog 无 canary；架构门禁无绕过 |
| TASK-002 | AC-004 | cache/report/snapshot/index write failure | 旧字节不变，tmp 清理，异常传播 |
| TASK-003 | AC-002 | OpenCode healthy/dirty/change/add/remove | 健康数据、revision、单次扫描、warning 正确 |
| TASK-004 | AC-003 | local/machine/corrupt/output_dir/zh/en/target | 去重/历史/文案/预算/警告正确 |
| TASK-005 | AC-005 | archive/compare + AST dependency | artifact 不变，allowlist 为 0 |
| TASK-006 | AC-006 | 五个合成 scorer cases | 所有不变量通过且受控变异可杀死 |
| TASK-007 | AC-007 | workflow contract + local commands | matrix/locked/tests/build 均存在且本地核心通过 |
| TASK-008 | AC-008, AC-009 | version/docs/full regression | v1.0.1/Schema1.0/双语/lock/build/diff 全过 |
| TASK-009 | AC-010 | metadata mutation/snapshot parity/private import/status catalog/action pin/skill gate | 所有派生面能回到唯一 owner；无双定义、私有跨层 import、SHA 测试常量或旧值快照 |

## TDD 执行判定

| 行为 | 上游锚点 | 判定（TDD / TEST_AFTER / NOT_APPLICABLE） | Red 预期失败 | Green 命令 | Refactor 结论 |
|---|---|---|---|---|---|
| LLM privacy | AC-001 | TDD | raw canary/path 出现在 mock request | `uv run pytest tests/unit/test_llm_privacy.py -q` | 一个 sanitizer/一个执行门 |
| atomic I/O | AC-004 | TDD | replace 失败破坏旧目标或残留 tmp | `uv run pytest tests/unit/test_atomic_io.py tests/unit/test_cache_store.py -q` | JSON helper 不复制协议 |
| OpenCode | AC-002 | TDD | 坏字段丢全文件、revision 不变或重复扫描 | `uv run pytest tests/unit/test_opencode_reader.py -q` | snapshot owner 在 adapter |
| status | AC-003 | TDD | 多机器/output_dir/i18n/target 失败 | `uv run pytest tests/unit/test_cli_status.py tests/unit/test_config.py -q` | build/render 分离 |
| snapshot layers | AC-005 | TDD | 无 allowlist 后架构测试失败 | `uv run pytest tests/unit/test_layer_dependencies.py tests/unit/test_personal_growth_report.py -q` | application facade 单一 owner |
| calibration | AC-006 | TDD | eval fixture/runner 缺失 | `uv run pytest tests/evals -q` | 只断言不变量 |
| CI contract | AC-007 | TDD | 当前 workflow 不含 matrix/locked/build | `uv run pytest tests/unit/test_ci_contract.py -q` | action pin 单一 |
| version/docs | AC-008 | TDD | 双语/1.0.1 检查对当前 1.0.0 失败 | `uv run pytest tests/unit/test_version_alignment.py -q` | 版本真源唯一 |
| truth source | AC-010 | TDD | mirror 自称 canonical、snapshot 两规则不一致、private import、catalog key drift、SHA 常量和 skill 旧值被 Red 捕获 | `.venv` Python 跑 version/layer/CI/status/snapshot tests；hub skill gates | owner 不复制、projection 可验证 |
| 全量 | AC-009 | TEST_AFTER | NOT_APPLICABLE | `uv sync --locked --extra dev` 后由平台 `.venv` Python 执行 `pytest tests/unit tests/evals -q` | 只修本次回归 |

## 主链证据矩阵

| 主链步骤 | 证据等级（static / contract / runtime / user-visible / release / limitation） | 实际证据 | 结论/局限 |
|---|---|---|---|
| AC-001..AC-006 | runtime | targeted pytest + 5 类 calibration fixture | PASS |
| AC-007 | static/runtime/release | workflow contract + locked sync + local build；hosted CI | 本地 PASS；hosted CI `NOT_RUN` |
| AC-008 | contract/runtime/user-visible | version/link tests + CLI `--version` | PASS，Product 1.0.1 / Schema 1.0 |
| AC-009 | runtime/limitation | 326 tests + compile/build/lock/diff | 本地 PASS；真实 LLM/OpenCode/browser `NOT_RUN` |
| AC-010 | contract/runtime | targeted truth-source tests + hub entrypoint/structure/size | PASS；hosted CI 仍 `NOT_RUN` |

## 回退方式

- git checkpoint：NOT_APPLICABLE；当前工作区已有用户/hub 未提交修改，禁止自动 commit/stash/reset。
- 文件备份：已有 docs/scripts 在修改前用 `doc-script-governance` 标准 `backup-file` 入口创建 L2 备份；代码文件按 `delivery-workflow` checkpoint/diff 纪律保护；新文件不备份。
- SQL/配置回滚：无 SQL；配置新增字段删除后默认行为回到 8，但正式回退必须保持版本/测试同步。
- feature flag：NOT_APPLICABLE；隐私和原子写不得加可关闭开关。
- 回退验证：对应 targeted Red/Green 命令 + 全量 AC-009；逐文件 diff 确认未触碰禁止范围。

## 完成状态

DONE_WITH_CONCERNS（实现、契约、运行与本地构建门通过；hosted CI 与真实外部数据/浏览器为 `NOT_RUN`）。
