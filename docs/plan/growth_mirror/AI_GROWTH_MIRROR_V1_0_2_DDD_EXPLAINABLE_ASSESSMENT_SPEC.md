---
title: AI Growth Mirror v1.0.2 DDD 与可解释评估 Feature Spec
status: canonical
document_type: feature_spec
spec_id: SPEC-GROWTH-MIRROR-1.0.2-DDD-EXPLAINABLE-ASSESSMENT
version: 1.0.0
approval: frozen
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/ARCHITECTURE_PRINCIPLES.md
    role: architecture_owner
  - path: docs/review/growth_mirror/AI_GROWTH_MIRROR_V1_0_2_REQUIREMENTS_REVIEW.md
    role: review
---

# Feature Spec: AI Growth Mirror v1.0.2 DDD 与可解释评估

> **文档性质**：本轮 Full Path 的需求唯一真源。目标是让“会话事实 → 指标 → 原因 → 训练动作 → 下期回看”形成可验证闭环，并接入 DeepSeek Harness 与 ZCode Agent。本文冻结用户价值、范围、可观察契约和验收；实现结构由 SDD/ADR 承接。

## 修订记录

| 版本 | 日期 | 修订要点 | 备份/引用 |
|---|---|---|---|
| 1.0.0 | 2026-09-02 | 冻结 DDD 边界、评分策略、解释闭环和两类 reader 契约 | — |

## 1. Fact Pack

| ID | 类型 | 事实或判断 | 来源路径/命令 | 证据等级 |
|---|---|---|---|---|
| FACT-001 | current_code | 当前产品主链为 reader → SessionRecord/SessionRead → scorer → report/snapshot；336 个 unit/eval 测试基线通过 | `pytest tests/unit tests/evals -q` | runtime |
| FACT-002 | current_code | `domain/growth/scorer.py` 同时承担聚合、信号公式、等级、雷达、缺口排序，单文件超过 1100 行 | `rg -n '^def ' ai_growth_mirror/domain/growth/scorer.py` | static |
| FACT-003 | current_code | 六轴权重在 scorer 总分与 `domain/snapshots/comparison.py::AXIS_WEIGHTS` 分别维护，存在漂移面 | 两个源文件 | static |
| FACT-004 | current_code | `domain/growth/capability.py` 在缺少 sub-score 时维护第二套能力公式 | `compute_capability_scores` | static |
| FACT-005 | current_code | 当前公式重复使用 effective contract，缺观测时 goal locking 返回 100，无有效契约时 compliance 为 1.0；token 总量、工具/模型多样性、commit/raw file volume 可正向拉分 | `scorer.py::_compute_growth_level`、`_populate_task_contract_signals` | static |
| FACT-006 | current_code | `SessionRecord` 持有 `_adapter/_raw_ref` 并调用 adapter/cache，领域实体泄漏基础设施生命周期 | `domain/session/model.py::SessionRecord.ensure_parsed` | static |
| FACT-007 | current_code | application 主链直接 import concrete infra，工具选择列表与 adapter 注册表分离 | `application/orchestrator.py`、`domain/session/tool_registry.py`、`infra/readers/__init__.py` | static |
| FACT-008 | external_official | DeepSeek Harness 使用 append-only event log，默认物理格式为 `session.jsonl.zstd`，当前 session format v0 且 developer preview 允许破坏性变化 | DeepSeek Harness 官方 repo 与 session persistence 文档 | contract |
| FACT-009 | local_runtime | 本机 `~/.dsh/sessions/<cwd>/<session>/session.jsonl.zstd` 存在；脱敏 schema 侦察确认 header + logical events + packed chunk rows | `.tmp/inspect_dsh_shape.py`（仅输出 key/type/count） | runtime |
| FACT-010 | external_official | ZCode 当前产品强调 Goal/Plan、Skills、Subagents、AGENTS.md、验证与状态恢复 | `https://zcode.z.ai/en/docs/agents`、`/goal`、`/subagents` | contract |
| FACT-011 | local_runtime | `~/.zcode/cli/db/db.sqlite` 包含 session/message/part/tool_usage/model_usage/turn_usage/workflow 等关系；`tasks-index.sqlite` 仅足够做桌面任务索引，不能替代会话事实 | `.tmp/inspect_zcode_cli_shape.py`、`.tmp/inspect_zcode_schema.py`（仅 schema/key/type/count） | runtime |
| FACT-012 | trend | 当前 Agent 工具共同趋势是持久目标、可恢复长任务、隔离委派、Skill/指令资产、确定性 Hook/验证与可追溯事件，而不是单纯增加模型调用次数 | DeepSeek、ZCode、Claude Code 官方文档 | contract |
| FACT-013 | repository | `HEAD` 与 `origin/main` ahead/behind 为 `0/0`；工作区存在大量本任务前的未提交改动 | `git fetch origin --prune`、`git status -sb` | runtime |

### Assumptions

| ID | 假设 | 最小验证动作 | 失效影响 |
|---|---|---|---|
| ASM-001 | `~/.zcode/cli/db/db.sqlite` 是 ZCode Agent 运行时的本地会话事实库 | 对真实但脱敏的单会话做 DB → SessionRecord 对拍 | 若失效，ZCode 只能标 `BLOCKED_BY_FORMAT`，不得回退读模型 I/O headers |
| ASM-002 | DeepSeek Harness v0 的 logical event 足够映射当前 SessionRecord，不需要解析 reasoning/text chunk 才能得到用户消息、工具与 usage | fixture 覆盖 header/user/tool/result/step/end/goal/subagent | 若失效，reader 只输出可证明字段，缺失字段为 unknown |
| ASM-003 | 本轮评分语义变化不修改 SessionRecord/SessionRead 缓存 shape | 运行 cache/version alignment 契约测试 | 若出现 shape 变化，停止并升级 Cache Schema 与产品版本线 |

### Unknowns

| ID | 未知项 | 是否阻断冻结 | 关闭条件 |
|---|---|---|---|
| UNK-001 | DeepSeek Harness 后续 developer-preview format 是否变化 | no | reader 只接受已知 header/version/row shape；未知版本 fail closed 并给诊断 |
| UNK-002 | ZCode 桌面未来是否迁移/替换 CLI SQLite schema | no | 通过 required-table/column capability probe；不满足则跳过并给 schema mismatch |
| UNK-003 | 新评分阈值对大规模真实用户的分布效果 | no | 本轮用 synthetic calibration + invariance；真实人群校准留作后续匿名数据研究，不能冒充已完成 |

### Risks

| ID | 风险 | 等级 | 缓解或停止条件 |
|---|---|---|---|
| RISK-001 | 评分公式变化导致历史趋势伪涨跌 | P0 | 新增唯一 assessment policy version；跨版本只显示不可比，不计算 delta |
| RISK-002 | “严格 DDD”演变为无价值大迁移 | P1 | 只拆已证实的领域/基础设施泄漏和评分真源；行为不变的旁支不重构 |
| RISK-003 | reader 读取真实凭据、headers 或把私密内容写日志 | P0 | 只读会话真源；禁读 credentials；日志仅路径类型/计数/错误码；fixture 脱敏 |
| RISK-004 | 子 Agent 子会话被当独立用户任务，重复计分 | P0 | 分析单位冻结为 user-visible root task；子会话证据向根任务汇总，usage 可单独全量统计 |
| RISK-005 | tool/model/token/file volume 造成“高消耗=高成熟”游戏化 | P0 | 从正向能力公式移除原始体量；仅保留成本/强度说明或饱和后的辅助证据 |
| RISK-006 | 当前脏工作区被覆盖 | P0 | 不 reset/stash/clean；仅最小 patch；每轮核对 diff 和目标文件 |

## 2. 目标与价值

- 目标用户：使用一种或多种 AI 编程 Agent、希望稳定交付并持续改善协作方式的个人开发者。
- 当前问题：产品能给出分数，但部分公式可被体量和工具数量误导；同一权重存在多真源；恢复轴在无恢复机会时仍可能获得高分；reader 对新型事件溯源/目标驱动工具尚未覆盖。
- 用户价值：不仅知道“哪一轴高/低”，还知道该结论来自哪些可核对事实、哪些证据缺失、下一次要练什么，以及训练是否在后续任务中兑现。
- 可观察结果：支持 DeepSeek Harness、ZCode；每个轴有 policy version、coverage、主要正/负贡献；跨版本趋势不漂移；报告训练项能在下一期回看。
- 更小闭环：先以 root task 为单位完成两个 reader + 单一评分策略 + tooltip/sidecar 解释 + snapshot 可比性门禁，不增加新的平行报告流水线。

## 3. 范围

### In Scope

- 以 bounded context、实体/值对象、领域服务、端口/适配器、防腐层表达本次主链。
- 移除 SessionRecord 的基础设施懒加载职责；外部格式解析只在 infra reader。
- 建立六轴、轴权重、等级阈值、component 权重、policy version 的唯一真源。
- 修复重复计权、missing-as-perfect、raw-volume reward、无恢复机会送分、跨版本强比较等逻辑问题。
- 保持四证法 ↔ 六轴映射；六轴仍为产品主轴，不新增第七轴。
- 轴分输出 evidence coverage、component contributions、confidence 与不可用原因；报告和 sidecar 可解释。
- DeepSeek Harness v0 JSONL/Zstd reader：root task、child roll-up、goal/subagent/tool/usage、损坏/未知格式诊断。
- ZCode SQLite reader：root task、child roll-up、message/part/tool/model/usage、schema capability probe、只读并发访问。
- CLI/配置/README/中英文设计/项目 skill/测试/校准/Replay 同步。
- 保持 `generate_report_artifacts` 唯一业务主链；若 composition root 调整，必须只有一个公开入口。

### Out of Scope

- 上传或集中收集真实用户会话做群体排名。
- 为工具做生产级完整回放器，或解释私有 reasoning 内容。
- 读取 ZCode model-io rollout headers/credentials 作为会话主源。
- 自动迁移/改写 DeepSeek 或 ZCode 原始数据。
- 发布 GitHub Release、推送远端、生产部署。
- 用 DDD 名义重写无关 HTML/CSS、LLM provider 或历史文档。

## 4. 用户场景

| ID | 用户 | 触发条件 | 期望结果 | 失败时可恢复动作 |
|---|---|---|---|---|
| SCN-001 | DeepSeek Harness 用户 | `generate --tools deepseek-harness` | 根任务被解析，子会话工作汇总一次，报告含可解释评分 | 未知 version/损坏日志逐会话跳过并给安全诊断 |
| SCN-002 | ZCode 用户 | `generate --tools zcode` | 从只读 SQLite 得到任务、工具、usage、目标/委派信号 | schema 不满足时输出缺失表/列，不读 rollout 兜底 |
| SCN-003 | 多工具用户 | `--tools all` | 两个新 reader 与既有 reader 一致进入统一领域事实，不产生工具专属加分 | 单个 reader 失败不终止其它工具 |
| SCN-004 | 成长报告用户 | 查看雷达 tooltip/sidecar | 看到得分、覆盖、主要支撑、主要短板、缺失证据 | 无证据时显示“暂无足够证据”，不是 0 或 100 |
| SCN-005 | 连续使用用户 | 本期与上期 policy 不同 | 明确显示不可直接比较 | 生成新基线后下一期恢复同策略比较 |
| SCN-006 | 训练用户 | 上期生成 Action Contract，本期再次生成 | 能看到是否执行、是否有效及下步调整 | 证据不足时显示 unknown，不宣称完成 |

## 5. 需求与业务规则

| ID | 需求/规则 | 事实来源 | 优先级 | 异常情况 |
|---|---|---|---|---|
| REQ-001 | 分析单位必须是 user-visible root task；子任务/子 Agent 证据汇总到根任务，禁止重复计分 | FACT-008/010/011 | P0 | 孤儿子任务独立跳过或标 orphan，不猜根 |
| REQ-002 | DeepSeek Harness reader 支持 v0 raw JSONL 与默认 concatenated Zstd frames，流式读取，不解读 reasoning | FACT-008/009 | P0 | 未安装 zstd 依赖必须给可行动错误；未知 version fail closed |
| REQ-003 | ZCode reader 只读 `~/.zcode/cli/db/db.sqlite` 的声明表/列；不得使用 model-io headers 或桌面缓存补会话正文 | FACT-011 | P0 | WAL/锁/schema mismatch 有明确诊断 |
| REQ-004 | reader 只负责 ACL：外部记录 → 统一 SessionRecord；评分规则不得进入 reader | FACT-007 | P0 | 工具特有字段没有统一语义时保留 unknown |
| REQ-005 | 六轴权重、内部 component 定义、等级阈值、policy version 只有一个 canonical owner，comparison/report/tests 只投影 | FACT-003/004 | P0 | 任意重复常量由结构测试阻断 |
| REQ-006 | 缺失观测不等于 0，也不等于 100；component 动态排除并重归一，轴证据不足可 unavailable | FACT-005 | P0 | 有明确信号为 0 时保留真实 0 |
| REQ-007 | 原始 token、文件总量、commit、模型/工具种类不得直接提升成熟度；只可作成本/强度/辅助证据 | FACT-005/012 | P0 | 任何再引入须先 ADR + anti-gaming 用例 |
| REQ-008 | contract 不重复计权；无有效 contract 时 compliance unavailable；goal-locking 未观测时 unavailable | FACT-005 | P0 | denominator=0 不输出 100% |
| REQ-009 | adaptive recovery 仅在存在错误、偏航、用户中断或 resistance opportunity 时评分；无机会时 unavailable | FACT-005 | P0 | 少于最小机会数时低置信或 unavailable |
| REQ-010 | 子 Agent、Skill、MCP、Goal、Hook、Plan 等趋势信号只证明方法/编排存在，必须与交付/验证证据结合，不能按次数送分 | FACT-010/012 | P0 | 只有调用无结果时不正向加分 |
| REQ-011 | 每轴输出 component value/weight/availability/evidence count/confidence，application 负责 i18n 解释 | 产品定位 | P0 | domain 禁止写最终中文/英文句子 |
| REQ-012 | snapshot/sidecar 写入 assessment policy version；不同 policy 不计算 axis/mirror delta | RISK-001 | P0 | legacy snapshot 明确 incomparable |
| REQ-013 | 训练项必须绑定 weakest evidence component、可执行动作、下期判据；最多 2 项，并能回看 | 用户目标 | P1 | 无证据不生成泛化模板 |
| REQ-014 | DDD 边界至少包含 Session Observation、Growth Assessment、Learning Loop；domain 不持有 adapter/cache/I/O，infra 不定义评分，application 不复制领域规则 | FACT-002/006/007 | P0 | 层依赖测试阻断回潮 |
| REQ-015 | 工具目录从 adapter catalog 派生 CLI choices；alias 仅做输入规范化，不维护第二份支持列表 | FACT-007 | P1 | registry/CLI drift 测试失败即阻断 |
| REQ-016 | `ai-growth-mirror-dev` 增加评分政策、reader 事实查证、policy drift、root-task roll-up 的首读路由与验证 | 用户要求 | P1 | hub 真源修改后必须过 skill 工程完成门 |

## 6. 契约

| 契约面 | 唯一术语/字段 | 输入 | 输出 | 错误/空值语义 |
|---|---|---|---|---|
| 分析单位 | `root_task` | parent/child sessions | 一个 SessionRecord + roll-up evidence | orphan 不猜测归属 |
| 评分版本 | `assessment_policy_version` | canonical policy | profile/snapshot/sidecar string | 不同版本 `incomparable` |
| 指标观测 | `MetricObservation` | numerator/denominator 或 bounded value | value/available/evidence_count/confidence | missing = unavailable |
| 轴评估 | `AxisAssessment` | available components | score/components/coverage/confidence | 无足够 component = unavailable |
| DeepSeek | `deepseek_harness` | `session.jsonl`/`.zstd` v0 | SessionRecord | corrupt/unknown format 单会话诊断 |
| ZCode | `zcode` | read-only SQLite required schema | SessionRecord | schema mismatch 不 fallback 私密 rollout |
| 工具选择 | adapter catalog | `--tools` aliases | canonical tool ids | unknown 显式报错 |

## 7. 非功能与安全

| ID | 类型 | 可量化约束 | 验证入口 |
|---|---|---|---|
| NFR-001 | latency | 100 个 session header 索引 p95 ≤1s；15MB fixture 单会话流式解析 ≤3s（本机基线） | benchmark test/fixture |
| NFR-002 | memory | reader 不对整个数据根做全量 `read()`；峰值内存与单行/单事件批次相关，15MB fixture 额外峰值 ≤64MB | code review + tracemalloc test |
| NFR-003 | compatibility | Python 3.11–3.13；Windows/macOS/Linux 默认路径可解析 | unit matrix / CI |
| NFR-004 | observability | 每工具输出 detected/parsed/skipped/corrupt/schema_mismatch 计数，不输出会话正文 | structured diagnostics tests |
| NFR-005 | evolution | 新工具只新增 adapter + fixture + catalog registration；不得修改评分公式 | dependency/registry tests |
| SEC-001 | data | readers 只读；不访问 credentials/key/pem/model-io headers；不写源目录 | fixture + path allowlist review |
| SEC-002 | privacy | 原始会话仅本地处理；日志/异常不含 prompt、tool result、headers、API key | redaction/error tests |
| SEC-003 | integrity | unknown version、缺 required schema、seq corruption fail closed；不得猜字段 | negative fixtures |
| SEC-004 | injection | 会话文本只是数据，不作为本工具执行指令；reader 不执行任何原始 command | code review |

## 8. 验收标准

| ID | 对应需求 | 场景 | 可观察结果 | 通过判据 |
|---|---|---|---|---|
| AC-001 | REQ-002/004 | DeepSeek raw + zstd 主链 | 相同逻辑 fixture 得到等价 root task record | 两种格式 golden 相等 |
| AC-002 | REQ-001/002 | DeepSeek parent/child | 根任务只计 1 个 session，subagent/tool/usage 按契约汇总 | 无重复 session/usage |
| AC-003 | REQ-003/004 | ZCode SQLite 主链 | message/tool/model/usage/goal/child 映射正确 | schema fixture golden 通过 |
| AC-004 | REQ-003 | ZCode schema 缺失/锁 | 安全跳过并给诊断，不读 rollout | negative tests 通过 |
| AC-005 | REQ-005/015 | 真源唯一 | 权重、等级、工具支持列表均由 canonical owner 派生 | drift tests 通过，`rg` 无第二公式 |
| AC-006 | REQ-006/008/009 | 缺失与机会条件 | missing 不送 0/100；无恢复机会不评分；contract denom 0 不为 100% | calibration invariants 通过 |
| AC-007 | REQ-007/010 | anti-gaming | 仅增加 token/files/tools/models/subagent calls 不提高 mirror score | metamorphic tests 通过 |
| AC-008 | REQ-011/013 | 用户解释闭环 | tooltip/sidecar 展示 policy、coverage、主要贡献和训练判据 | HTML/JSON snapshot tests 通过 |
| AC-009 | REQ-012 | 跨策略趋势 | 不同 policy snapshot 不生成伪 delta | comparison test 通过 |
| AC-010 | REQ-014 | DDD | domain 无 I/O/adapter/cache；reader 无评分；application 无重复公式 | layer dependency tests 通过 |
| AC-011 | REQ-016 | skill | baseline/held-out 证据、路由、references、entrypoint/structure/size 全通过 | hub skill gates exit 0 |
| AC-012 | 全部 | 回归 | unit/eval 全量 + CLI 两 reader smoke + 报告生成通过 | 命令 exit 0，产物可打开 |

## 9. TDD / 验证映射

| 验收项 | 可测试行为 | 验证类型 | 证据等级 |
|---|---|---|---|
| AC-001~004 | reader golden/negative/roll-up | TDD | runtime |
| AC-005~007 | policy drift + metric invariance | TDD | runtime |
| AC-008~009 | report/sidecar/snapshot policy | TDD | runtime/user-visible |
| AC-010 | dependency direction | TDD | static/runtime |
| AC-011 | skill routes/gates | TEST_AFTER | contract/runtime |
| AC-012 | full suite/CLI | TEST_AFTER | runtime/user-visible |

## 10. 风险与人工确认点

| 风险/决策 | 影响 | 是否需要人工确认 | 确认人/结论 |
|---|---|---|---|
| RISK-001 | 历史趋势中断一代 | no | 用户已要求真源唯一、不得漂移；选择 fail-closed 可比性门 |
| RISK-002 | DDD 重构范围 | no | 用户已明确要求严格 DDD；以主链和证实问题为边界 |
| RISK-003 | 本机私密数据 | no | 只读 schema/key/type/count 已执行；实现使用脱敏 fixture |
| 删除/发布/推送 | 越出目标安全边界 | yes | 本轮禁止 |

## 11. 追踪矩阵

| 需求/约束 | 设计锚点 | 验收项 | 状态 |
|---|---|---|---|
| REQ-001~004 | SDD §4.2/4.3 | AC-001~004 | covered |
| REQ-005~010 | SDD §4.4 | AC-005~007 | covered |
| REQ-011~013 | SDD §4.5 | AC-008~009 | covered |
| REQ-014~016 | SDD §4.1/4.6 | AC-010~011 | covered |
| NFR-001~005 | SDD §7 | AC-001~012 | covered |
| SEC-001~004 | SDD §4.3/7 | AC-004/010/012 | covered |
