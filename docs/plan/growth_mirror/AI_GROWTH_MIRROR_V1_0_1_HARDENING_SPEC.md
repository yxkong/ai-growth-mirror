---
title: AI Growth Mirror v1.0.1 可信与韧性加固 Feature Spec
status: canonical
document_type: feature_spec
spec_id: SPEC-GROWTH-MIRROR-1.0.1-HARDENING
version: 1.0.5
approval: frozen
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/design/ARCHITECTURE_PRINCIPLES.md
    role: architecture_source
  - path: docs/design/v1.0.0-DESIGN.md
    role: previous_release
---

# Feature Spec: AI Growth Mirror v1.0.1 可信与韧性加固

> **文档性质**：Full Path 的需求规格真源。这里的“解决所有问题”仅指本 Spec Fact Pack 中已有静态、契约或运行证据的问题；`approval: frozen` 前不得进入设计和实现。

## 修订记录

| 版本 | 日期 | 修订要点 | 备份/引用 |
|---|---|---|---|
| 1.0.5 | 2026-09-02 | Review Round 6/7：冻结 canonical/derived 角色、snapshot 规则单源和防漂移门禁 | `docs/review/growth_mirror/AI_GROWTH_MIRROR_V1_0_1_REQUIREMENTS_REVIEW.md` |
| 1.0.4 | 2026-09-01 | Review Round 5：将 OpenCode freshness 验收精化为稳定 revision 变化 | 同上 |
| 1.0.3 | 2026-09-01 | Review Round 4：补齐 status 按 `report.output_dir` 定位历史快照 | 同上 |
| 1.0.2 | 2026-09-01 | Review Round 2/3：补齐匿名项目标签、提示注入边界和安全日志后冻结 | 同上 |
| 1.0.1 | 2026-09-01 | Review Round 1：隐私范围从 session-read 扩展到全部 LLM user prompt | 同上 |
| 1.0.0 | 2026-09-01 | 初稿：冻结事实、范围、契约、四高二低三底座投影与验收 | — |

## 1. Fact Pack

| ID | 类型 | 事实或判断 | 来源路径/命令 | 证据等级 |
|---|---|---|---|---|
| FACT-001 | current_code | session-read 与 prompt-quality LLM prompt 会传入原始 `project_path`/用户消息，现有清洗仅做空白归一化和截断；work-focus/coaching 还会发送派生文本。 | `infra/extractors/llm.py`、`infra/extractors/prompt_quality.py`、`infra/llm/work_focus.py`、`infra/llm/coach.py` | static |
| FACT-002 | current_code | OpenCode 单个二次 JSON 值损坏会使整个文件读取失败；每个 session 都重新扫描 workspace 文件。 | `infra/readers/opencode.py::_read_dat`、`parse_session` | static |
| FACT-003 | current_code | OpenCode freshness 只取 global mtime；unit test 存在读取开发者真实目录且无数据时静默通过的 smoke。 | `iter_raw_sessions`、`tests/unit/test_opencode_reader.py` | static |
| FACT-004 | current_code | `status` 忽略 records 的 source-machine 子目录，固定文案由 Python 语言分支维护，周目标硬编码为 8，坏文件静默跳过。 | `application/status_view.py` | static |
| FACT-005 | current_code | cache、report/snapshot 等关键持久化路径存在直接覆盖写和宽泛静默异常。 | `infra/cache/store.py`、`infra/snapshots.py`、`application/orchestrator.py` | static |
| FACT-006 | current_code | `infra/snapshots.py` 反向依赖 application，架构测试以 allowlist 放行。 | `tests/unit/test_layer_dependencies.py` | static |
| FACT-007 | test_gap | 评分没有版本化 calibration/golden 数据集与不变量门禁。 | `tests/unit/`、`.github/workflows/unit-tests.yml` | static |
| FACT-008 | delivery_gap | CI 仅 Ubuntu/Python 3.12，非冻结安装，只跑 unit tests，不构建发布包。 | `.github/workflows/unit-tests.yml` | static |
| FACT-009 | contract_gap | 版本门禁只检查中文 README；v1.0.1 路线图主题与本次加固范围冲突。 | `tests/unit/test_version_alignment.py`、中英文路线图 | contract |
| FACT-010 | baseline | 当前 `291 tests collected` 且 unit tests 通过；`uv build`、`uv lock --check` 通过；`.venv` 的 `python -m build` 因未安装 `build` 失败。 | 2026-09-01 本地命令 | runtime |
| FACT-011 | workspace | 任务开始前已有 hub 规则、OpenCode reader/session scope 与测试等未提交修改。 | `git status --short --branch` | runtime |
| FACT-012 | current_code | `status` 从 `Path.cwd()` 查找 snapshot archive，而报告产物位置可由 `report.output_dir` 配置。 | `application/status_view.py`、`config.py::ReportConfig.output_dir` | static |
| FACT-013 | contract_gap | 文档索引同时声明“唯一架构真源”和“中英双真源”；英文 SDD/ADR 已指向中文 canonical，但 frontmatter 仍标 `status: canonical`。 | `docs/README.md`、`docs/en/**` | contract |
| FACT-014 | current_code | snapshot 的 actionable friction 与 friction-topic 映射分别存在于 application 和 infra，且同一输入的别名集合已经不一致；application 还跨层 import infra 私有 `_snapshot_source_from_payloads`。 | `application/growth_trajectory.py`、`application/snapshot_service.py`、`infra/snapshots.py` | static |
| FACT-015 | governance_gap | CI contract test 复制当前 `setup-uv` SHA；项目 skill 的当前版本/设计入口仍硬编码 1.0.0，不能从当前代码事实自动收敛。 | `tests/unit/test_ci_contract.py`、hub `ai-growth-mirror-dev` | static / contract |

### Assumptions

| ID | 假设 | 最小验证动作 | 失效影响 |
|---|---|---|---|
| ASM-001 | v1.0.1 可在 Cache Schema 1.0 内完成。 | 设计 Review 检查所有持久化字段。 | 如需 schema 变化，停止并回到需求。 |
| ASM-002 | 当前 OpenCode `.dat` 结构以现有 fixture 与 adapter 注释为本版本契约。 | 固定 fixture + 局部损坏测试。 | 未知真实版本差异标记 `NOT_RUN`，不得臆造支持。 |
| ASM-003 | 用户要求“全部问题”不授权删除非产品文件。 | 对照任务目标与删除规则。 | `nul` 保留并在最终限制中说明。 |

### Unknowns

| ID | 未知项 | 是否阻断冻结 | 关闭条件 |
|---|---|---|---|
| UNK-001 | 真实 OpenCode 新版本是否仍使用完全相同的 `.dat` 结构。 | no | fixture 契约通过；真实数据验证标记 `NOT_RUN` 或单独执行。 |
| UNK-002 | 外部 LLM provider 的实际留存策略。 | no | 不替 provider 承诺；文档明确出站边界和 `--no-llm`。 |
| UNK-003 | GitHub 托管 Windows runner 的真实耗时。 | no | CI 配置静态验收；远端执行为 release evidence。 |

### Risks

| ID | 风险 | 等级 | 缓解或停止条件 |
|---|---|---|---|
| RISK-001 | 正则脱敏无法识别任意自然语言秘密。 | P1 | 覆盖高风险结构化模式，诚实声明边界；强隐私使用 `--no-llm`。 |
| RISK-002 | Windows 文件替换与打开句柄语义不同于 Linux。 | P1 | 原子写失败测试 + Windows CI；失败保留旧文件。 |
| RISK-003 | status 100ms 预算在共享 CI 抖动。 | P2 | 设计目标 100ms，CI 抗抖动门槛 500ms，同时断言单遍扫描。 |
| RISK-004 | snapshot 拆层扩大变更半径。 | P1 | 保留 public facade，先做字符化测试，再移动职责。 |
| RISK-005 | 未提交 OpenCode 修改被覆盖。 | P0 | 禁止 reset/stash；只做原位增量并逐文件复核 diff。 |
| RISK-006 | 将翻译同步称为“双真源”会让冲突无法裁决；新增独立真源清单又会制造第三份需要同步的资产。 | P0 | 中文契约为 canonical，英文/README/lock/example/skill 快照均为 derived projection；owner 直接写入现有 canonical 文档和代码，不新增并行 registry。 |

## 2. 目标与价值

- 目标用户：在本机读取多种 AI 编程工具会话并生成个人成长报告的开发者，以及维护/发布该项目的贡献者。
- 当前问题：FACT-001 至 FACT-009 会造成隐私声明失真、缓存陈旧、跨机器统计错误、半文件风险、静默降级、分层债和发布漏检。
- 用户价值：报告更可信，隐私边界更诚实，异常可定位，Windows/Linux 上的发布结果更可复现。
- 可观察结果：敏感负例不进入 mock LLM、坏 OpenCode 字段不拖垮全文件、多机器 status 正确、写失败保留旧文件、架构 allowlist 清零、calibration 和跨平台 CI 可执行。
- 更小闭环：先完成 LLM 出站隐私 + 原子 JSON 写入两个 P0 薄切片，再推进 reader/status/分层与发布门禁。
- 版本结果：Product v1.0.1 / Cache Schema 1.0；原路线图中的团队级跨机器聚合顺延至 v1.0.2 或以后。

## 3. 范围

### In Scope

- 所有 LLM user prompt 在统一出站边界规则脱敏与有界化，公开隐私文档同步。
- OpenCode reader 局部容错、单次采集索引、workspace freshness 与确定性 fixture。
- status 多机器 records、i18n catalog、可配置周目标与坏数据诊断。
- cache、报告、snapshot/index 关键覆盖写的原子化，以及稳定事件码 logging。
- snapshot application/infra 职责回正并移除架构 allowlist。
- 评分 calibration fixture/invariant tests。
- Ubuntu/Windows、Python 3.12/3.13、uv frozen、tests 与 build 的 CI 门禁。
- v1.0.1 版本真源、中英文 README/设计索引/路线图与设计文档一致性。
- canonical owner 与 derived projection 角色收口；snapshot 业务映射单源化；CI、i18n、配置和文档镜像由结构门禁防漂移。

### Out of Scope

- 不重写整个 scorer、HTML 模板或所有 reader；不做无 FACT 映射的顺手重构。
- 不改变六轴名称/权重、Cache Schema、公开命令名或现有 cache 路径。
- 不引入云服务、遥测、数据库、新网络依赖或 hub prompt 真源。
- 不删除工作区未跟踪 `nul` 文件，不 reset/stash/覆盖用户未提交修改。
- 不把 mock/unit 结果冒充真实 LLM、真实 OpenCode、浏览器或远端 CI 证据。
- 不删除英文文档，不新增第二份真源 registry，不保留旧映射兼容壳。

## 4. 用户场景

| ID | 用户 | 触发条件 | 期望结果 | 失败时可恢复动作 |
|---|---|---|---|---|
| SCN-001 | 隐私敏感用户 | 启用 LLM 生成报告 | 出站 prompt 不含结构化秘密和绝对路径，只含有界脱敏片段 | 清洗失败时跳过字段/LLM 增强；可改用 `--no-llm` |
| SCN-002 | OpenCode 用户 | `.dat` 某字段损坏或 workspace model 更新 | 其余合法会话可读，缓存 freshness 更新并有 warning | 跳过坏字段，不覆盖健康 cache |
| SCN-003 | 多机器用户 | 运行 `status` | 单机与多机器缓存统一去重计数，语言和周目标配置生效 | 跳过单个坏记录并输出事件码 |
| SCN-004 | 报告用户 | 写 cache/report/snapshot 时中断 | 既有完整文件保持不变 | 命令显式失败，可安全重试 |
| SCN-005 | 贡献者 | 修改评分/分层/版本并提交 | calibration、架构、双语版本、跨平台 build 门禁发现回归 | 修复后重跑同一冻结命令集 |

## 5. 需求与业务规则

| ID | 需求/规则 | 事实来源 | 优先级 | 异常情况 |
|---|---|---|---|---|
| REQ-001 | session-read、prompt-quality、work-focus、growth-coach 等所有 LLM user prompt 在统一出站边界走确定性清洗器；处理 Windows/Unix 绝对路径、用户目录、Bearer/token/API key/secret/password、PEM、邮箱；源项目名转换为匿名稳定标签；各上游消息条数和字符数有上限；用户文本位于明确的不可信证据边界内。 | FACT-001 | P0 | 清洗失败 fail closed，不回退原文；system prompt 作为仓内静态资产不做语义改写。 |
| REQ-002 | OpenCode 单个二次 JSON 值损坏只跳过该字段；一次采集 global/workspace 各按文件签名最多解析一次；freshness 覆盖所有影响文件；unit tests 只用 fixture。 | FACT-002, FACT-003 | P0 | 整个来源不可读时返回空并 warning。 |
| REQ-003 | status 读取单机与 source-machine records，以 `(source_machine, tool_name, session_id)` 去重；从 `report.output_dir` 解析 snapshot archive；固定文案进入中英文 catalog；周目标可配置且默认 8。 | FACT-004, FACT-012 | P1 | 非法目标配置失败；坏记录跳过并 warning。 |
| REQ-004 | cache JSON、报告 HTML/JSON、snapshot JSON/HTML/index 使用同目录临时文件和原子替换；关键降级使用稳定事件码 logging。 | FACT-005 | P0 | 写失败保留旧文件并尽力清临时文件。 |
| REQ-005 | `infra` 不 import `application`；snapshot view 组装归 application service，infra 只做持久化/加载/纯转换；移除 allowlist。 | FACT-006 | P1 | public facade 行为必须由回归测试保护。 |
| REQ-006 | 新增版本化、无个人数据的 calibration fixture，覆盖空证据、有效契约、验证证据、缺失 usage、环境恢复五类不变量。 | FACT-007 | P1 | 不用整份文案快照冻结无关输出。 |
| REQ-007 | CI 覆盖 Ubuntu/Windows 和 Python 3.12/3.13，使用 `uv.lock` 冻结安装，运行 unit+calibration、架构/版本门禁和 `uv build`。 | FACT-008, FACT-010 | P1 | 本地与 CI 使用同一 uv 入口。 |
| REQ-008 | 产品升至 1.0.1，Schema 保持 1.0；同步 package/lock/中英文 README/设计索引/路线图/当期设计；测试同时检查双语公开面。 | FACT-009 | P1 | 任一版本面漂移即门禁失败。 |
| REQ-009 | 每类事实必须只有一个 canonical owner：中文活动契约为文档 canonical，英文为受检 mirror；产品版本、Cache Schema、主编排、snapshot 业务映射、status catalog schema 与 CI action pin 分别由现有代码/配置 owner 定义。所有不可避免的派生投影必须可从 owner 校验，禁止在测试、skill 或另一层复制可变值和业务规则。 | FACT-013..FACT-015 | P0 | owner 冲突、mirror 自称 canonical、跨层私有 import、重复业务映射或测试复制 action SHA 均阻断。 |

## 6. 契约

| 契约面 | 唯一术语/字段 | 输入 | 输出 | 错误/空值语义 |
|---|---|---|---|---|
| LLM 出站 | `sanitize_outbound_text` / sanitized `LlmCallRequest.prompt` | nullable text + 字符预算 | 脱敏、有界字符串 | user prompt 在 gateway 执行前统一清洗；项目名用会话内匿名标签；失败返回安全占位符，不返回原文 |
| OpenCode 采集 | `SessionRef.source_paths/source_mtime` | global/workspace `.dat` | 影响 session 的来源集合与最大 mtime | 无可读 global 时无 session；坏字段局部跳过 |
| status 配置 | `report.weekly_session_target` | 正整数 | 进度分母，默认 8 | 小于 1 为配置错误 |
| diagnostics | `AGM-模块-事件` | 异常类别、安全路径/计数 | `logging.WARNING` 或显式异常 | 不记录 prompt/token/secret 原文 |
| 原子持久化 | `atomic_write_text` | 目标路径、文本、编码 | 完整替换后的目标 | 失败保留旧目标并抛出异常 |
| calibration | `calibration_schema_version` | 合成会话/分析证据 | 评分不变量/区间断言 | schema 不支持时测试失败 |
| 产品版本 | `project.version` | `pyproject.toml` | package/lock/docs 的 1.0.1 投影 | 漂移即测试失败 |
| 文档角色 | `status: canonical` / `status: mirror` + `canonical_path` | 中文活动契约与英文翻译 | 英文镜像只投影相同版本/批准状态并链接 owner | mirror 不得自称 canonical；路径或关键元数据漂移即失败 |
| snapshot 投影规则 | `domain.snapshots.projection` | PQ deficit + friction category | runtime/archive 使用同一 actionable friction 与 topic 映射 | 只允许一个 public 定义；禁止 application/infra 私有副本 |
| CI action pin | workflow `uses:` | action owner + 40 位 commit SHA | hosted runner action 版本 | 测试只检查结构和 pin 形状，不复制当前 SHA |

## 7. 非功能与安全

| ID | 类型 | 可量化约束 | 验证入口 |
|---|---|---|---|
| NFR-001 | performance | OpenCode 单次采集复杂度为 `O(S+W)`；不得每 session 重扫 workspace。 | 调用计数单测 |
| NFR-002 | latency | status 对 1,000 个 fixture records 设计目标 100ms，CI 抗抖动硬门槛 500ms。 | 性能单测 + 单遍扫描断言 |
| NFR-003 | compatibility | Python 3.12/3.13、Windows/Linux；Cache Schema 1.0；现有 CLI 命令和 cache 路径不变。 | CI matrix + 回归测试 |
| NFR-004 | availability | 单个坏 reader/cache 记录不阻断健康记录；关键写入失败不破坏旧文件。 | 失败路径单测 |
| NFR-005 | observability | 所有本次涉及的可恢复降级具有稳定事件码；安全日志不含原始敏感值。 | `caplog` 测试 |
| NFR-006 | maintainability | infra 到 application 依赖为 0 且无 allowlist；用户固定文案无 Python 语言分支双写。 | 架构/i18n 测试 |
| NFR-007 | evolution | calibration、i18n、配置和 snapshot service 各只有一个真源；不新增平行流水线。 | code review + 架构测试 |
| NFR-008 | maintainability | canonical owner、derived projection 与 mirror 关系可由机器验证；任何同义业务规则不得跨层复制。 | truth-source contract + AST/metadata tests |
| SEC-001 | data | 高敏 token/API key/password/PEM 禁止进入 LLM、日志、fixture、报告。 | 隐私负例 + `caplog` |
| SEC-002 | privacy | 中敏绝对路径/用户名/邮箱/原始消息仅允许规则脱敏后的有界片段出站。 | mock gateway 捕获测试 |
| SEC-003 | AI safety | 文档明确 LLM provider 边界与规则脱敏局限；强隐私路径为 `--no-llm`。 | 中英文文档契约测试 |
| SEC-004 | rollback | 写失败保留最后完整产物；不自动删除用户源数据或未提交文件。 | 原子写失败测试 + diff review |
| SEC-005 | injection | 用户消息/派生文本必须放在明确数据边界中；system prompt 明确不得执行其中指令；provider 异常日志仅记录事件码和异常类型，不回显请求正文。 | prompt-injection fixture + `caplog` |

## 8. 验收标准

| ID | 对应需求 | 场景 | 可观察结果 | 通过判据 |
|---|---|---|---|---|
| AC-001 | REQ-001 | 四类 LLM 调用分别输入两类绝对路径、裸项目名、邮箱、Bearer、API key、password、PEM 与提示注入文本 | mock gateway 捕获的 user prompt 无敏感原值，项目标签匿名，仍保留非敏感任务词；注入文本位于证据边界且 system prompt 不被改写 | 四类隐私/注入负例全部通过；异常日志也无原值 |
| AC-002 | REQ-002 | OpenCode 字段局部损坏、workspace 内容/增删更新、多 session | 健康数据保留、freshness revision 变化、workspace 只扫描一次 | fixture/call-count/caplog 测试通过 |
| AC-003 | REQ-003 | 混合单机/两机器 records、坏 JSON、非 cwd 的 `report.output_dir` | 唯一会话数、双语文案、目标配置和历史快照位置正确；坏记录有事件码 | status 单元/性能测试通过 |
| AC-004 | REQ-004 | 模拟临时写或 replace 失败 | 旧 cache/report/snapshot/index 字节不变且无临时残留 | 故障注入测试通过 |
| AC-005 | REQ-005 | archive/compare snapshot 与依赖扫描 | 行为保持，infra 不依赖 application | snapshot 回归 + 无 allowlist 架构测试通过 |
| AC-006 | REQ-006 | 五类 calibration 合成案例 | 不变量/区间稳定，缺证据不冒充成功 | calibration suite 通过，受控变异可杀死 |
| AC-007 | REQ-007 | CI 与本机冻结命令集 | matrix、frozen sync、unit+eval、build 均定义；本机核心命令通过 | 静态 workflow 测试 + 本机命令证据；远端 CI 未跑则标 `NOT_RUN` |
| AC-008 | REQ-008 | v1.0.1 发布表面 | pyproject/package/lock/中英文 docs 一致，Schema 为 1.0，互链存在 | 版本/文档测试与 link check 通过 |
| AC-009 | REQ-001..REQ-008 | 全量回归 | 原 291 tests 与新增 tests 全过，lock/build/structure/diff checks 通过 | 命令退出码均为 0；真实 LLM/OpenCode/browser 未跑则明确 `NOT_RUN` |
| AC-010 | REQ-009 | 文档、skill、snapshot、status、CI 发生受控漂移变异 | 英文 mirror 指向唯一中文 owner；关键元数据一致；runtime/archive 相同输入得到相同映射；application 不 import infra 私有符号；CI pin 变更无需同步测试常量 | metadata/AST/行为测试通过，`rg` 无“中英双真源”与重复映射定义，hub skill 工程门通过 |

## 9. TDD / 验证映射

| 验收项 | 可测试行为 | 验证类型（TDD / TEST_AFTER / MANUAL / NOT_APPLICABLE） | 证据等级（static / contract / runtime / user-visible / release / limitation） |
|---|---|---|---|
| AC-001 | 出站敏感值 fail closed | TDD | runtime |
| AC-002 | 局部容错、freshness、单次 workspace 索引 | TDD | runtime |
| AC-003 | 多机器计数、i18n、配置和预算 | TDD | runtime |
| AC-004 | 原子替换故障不破坏旧文件 | TDD | runtime |
| AC-005 | snapshot facade 行为与依赖方向 | TDD | runtime |
| AC-006 | 评分五类不变量 | TDD | contract |
| AC-007 | workflow 结构与本地 uv 命令 | TEST_AFTER | static / runtime / release |
| AC-008 | 双语版本与链接一致性 | TDD | contract |
| AC-009 | 全量冻结命令集 | TEST_AFTER | runtime / limitation |
| AC-010 | canonical/mirror、snapshot 映射、CI pin 与 skill 事实去漂移 | TDD | contract / runtime |

## 10. 风险与人工确认点

| 风险/决策 | 影响 | 是否需要人工确认 | 确认人/结论 |
|---|---|---|---|
| RISK-001 | 脱敏能力边界 | no | 通过 SEC-003 诚实披露，不作零泄漏虚假承诺 |
| RISK-002 | Windows 原子替换差异 | no | Windows CI 与失败测试收口 |
| RISK-004 | snapshot 拆层 | no | 不改变 public facade/输出契约 |
| RISK-005 | 脏工作区保护 | no | 用户已授权实现但未授权丢弃修改；严格增量处理 |
| 删除未跟踪 `nul` 文件 | 非产品清理、不可恢复 | yes | 本任务不执行，除非用户另行明确授权 |
| Cache Schema/六轴/CLI 变化 | 超出本 Spec | yes | 若实现发现必要性，立即停止并回到需求 |

## 11. 追踪矩阵

| 需求/约束 | 设计锚点 | 验收项 | 状态 |
|---|---|---|---|
| REQ-001 | SDD §3.1, §5.1 | AC-001, AC-009 | covered |
| REQ-002 | SDD §3.2, §5.2 | AC-002, AC-009 | covered |
| REQ-003 | SDD §3.3, §5.3 | AC-003, AC-009 | covered |
| REQ-004 | SDD §3.4, §5.4 | AC-004, AC-009 | covered |
| REQ-005 | SDD §3.5, §5.5 | AC-005, AC-009 | covered |
| REQ-006 | SDD §3.6, §5.6 | AC-006, AC-009 | covered |
| REQ-007 | SDD §3.7, §5.7 | AC-007, AC-009 | covered |
| REQ-008 | SDD §3.8, §5.8 | AC-008, AC-009 | covered |
| REQ-009 | SDD §3.9, §5.9 | AC-010, AC-009 | covered |
| NFR-001 | SDD §4.1 | AC-002 | covered |
| NFR-002 | SDD §4.1 | AC-003 | covered |
| NFR-003 | SDD §4.2 | AC-007, AC-008 | covered |
| NFR-004 | SDD §4.3 | AC-002, AC-004 | covered |
| NFR-005 | SDD §4.3 | AC-002, AC-003, AC-004 | covered |
| NFR-006 | SDD §4.4 | AC-003, AC-005 | covered |
| NFR-007 | SDD §4.4 | AC-005, AC-006 | covered |
| NFR-008 | SDD §4.4 | AC-010 | covered |
| SEC-001 | SDD §4.5 | AC-001 | covered |
| SEC-002 | SDD §4.5 | AC-001 | covered |
| SEC-003 | SDD §4.5 | AC-008 | covered |
| SEC-004 | SDD §4.6 | AC-004, AC-009 | covered |
| SEC-005 | SDD §4.5 | AC-001 | covered |
