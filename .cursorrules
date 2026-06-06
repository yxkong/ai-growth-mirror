# Common Agent Rules (core)

High-signal defaults only. Procedures and details belong in skills—see §技能路由。

**本文档是 Agent 全局必遵规则**（同步到各仓库 `AGENTS.md`、`.cursor/rules/00-common.mdc` 等）。`skills/share/README.md` 供**人**查阅技能目录，**不是** Agent 入口。

## Goals

- Hard constraints first: no garbled text, no broken structure, no unsafe shortcuts.
- Reduce detours: prefer the shortest correct path, avoid rework, avoid duplicate investigation.
- Save tokens: read the minimum useful context; prefer canonical sources over scattered history.
- Design before implementation: non-trivial work should be designed and aligned before code lands.
- Learn after failure: when a change fails or causes rework, extract the lesson in reusable form.

## Output

- Default to **Simplified Chinese** and **Markdown** unless the user asks otherwise.
- Keep answers **concise** and **actionable**.
- Separate **fact / assumption / unknown / risk** when that affects the next action.
- Put **executable commands** in fenced code blocks matching the shell environment.

## Hard Constraints

- **Preserve existing encoding** when editing; new files prefer **UTF-8 without BOM + LF**.
- Prefer the **smallest effective change**; avoid scope creep; reuse before inventing.
- For **non-trivial work**, align on goals, constraints, and acceptance before implementation.
- Validate with the **smallest safe check**; no remote/deploy/production commands unless explicitly asked.
- **Windows shell 强规则**：在 Windows 上执行命令时，默认**显式使用 `pwsh`（PowerShell 7+）**；只有在**刻意验证 `powershell.exe` / Windows PowerShell 5.1 兼容性**时，才允许退回旧宿主。不得因为本机终端默认配置与工具宿主不一致，就默认假设自己跑在 `pwsh` 上。
- Do not fabricate tool output, private state, dates, or unavailable facts.
- Pause before irreversible, expensive, destructive, or production-impacting actions.
- When a change fails, find the root cause and land the lesson in reusable form.

## 研发全流程（Agent 全局必遵）

真实研发任务的 **节奏** 与 **文档/SQL 资产** 由 **`delivery-workflow`** + **`doc-script-governance`** 固定搭配；**端到端治理总线**（Spec / ADR / 门禁 / scorecard）由 **`ai-development-governance`** 承担（不合并为一个 skill；**不得**在各仓库 `docs/guide/` 复制本段全文）。

### 固定顺序

1. 研发任务进场 → **`delivery-workflow`**（阶段门；Full Path 先设计收敛；前置可读 **`ai-development-governance`**）。
2. 规范 / Spec / ADR / Security / Release 门禁 / 9.8 评分 → **`ai-development-governance`**（不替代 delivery 执行）。
3. 要写/改 `docs/`、SQL、合并 plan → **`doc-script-governance`**。
4. 写代码/页面/接口 → **项目领域技能**（`rules/projects/<key>/PROJECT_RULES.md` + `skills/projects/<key>/`）。
5. 上线前 → **`ai-development-governance`** Release / Security Gate（Fast Path 开发环境可轻量化）。
6. 找某仓库已有终版 → 该仓库 `docs/README.md`、`docs/design/<domain>/README.md`（各项目自建）。

### 分工（禁止混淆）

| | ai-development-governance | delivery-workflow | doc-script-governance |
|--|---------------------------|-------------------|------------------------|
| **管** | G0–G8、Spec/ADR/Task Contract 模板、Security/Release/Quality 门禁、scorecard | 阶段门、契约、验证、失败沉淀 R3 | 类型 ID、目录、模板、备份、项目 docs 元数据 |
| **不管** | 具体代码实现；docs 备份 SOP 细则 | 文档放哪个文件夹 | 业务方案、排期、代码实现 |

**设计整合门**（delivery §5.1）：plan 并入 `docs/design` 终版；可执行契约与终版一致；**项目 docs** 按 doc-script 更新 YAML + §修订记录（share 技能 `references/` **不写**修订表）。

**冲突**：研发 + 文档落点并存时 → **`delivery-workflow` 主导**，文档细则转 **`doc-script-governance`**。研发 + 规范/门禁/评分 → **`ai-development-governance` 主导**，执行转 **`delivery-workflow`**。

## 改动前置

**代码文件**：进入实现阶段前遵循 `delivery-workflow` **checkpoint 协议**（优先 `git status`；必要时经同意的 `git commit` / `stash` / 分支；否则记录 `risk`）。

**文档 / 脚本 / 技能主文件**：改前按 `doc-script-governance` 调用 **`skills/share/doc-script-governance/scripts/backup-file`**（或 hub 兼容入口 `scripts/backup-file`）。

**已有文档 / SQL**：未经负责人明确确认，不得删除、清空或替换为占位。

### 还原与撤回（Git / 工作区）

凡执行 **任一可能覆盖、丢弃或未提交就先抹掉本地状态** 的操作（例如 `git restore`、`git reset`、`git clean` 等），必须先：

1. **列出复原范围**（逐条路径；必要时附 `git status` / `git diff` 摘要）。
2. **给出拟执行命令原文**，并说明会不会丢掉未提交修改、是否与用户意图一致。
3. **经用户明示确认后再执行**。

**禁止**：未经确认对整块目录一键 `git restore`。

## 技能路由

| 场景 | 先读 |
|------|------|
| 研发任务（节奏） | **`delivery-workflow`**（顺序见 §研发全流程） |
| AI 开发规范 / 体系 / Spec·ADR / 上线门禁 / 9.8 评分 | **`ai-development-governance`** |
| 文档 / SQL / 脚本放置、模板、备份 | **`doc-script-governance`** |
| SKILL 新建 / 审查 / 目录布局 | `skill-engineering` |
| Hub 安装、注册、挂载、脚本分级 | `agent-hub-bootstrap` |
| 目标产物不明（skill / prompt / docs 混在一起） | `agent-asset-router` |
| 浏览器黑盒验证 | `webapp-testing`（验证阶段，delivery 主导） |

**项目领域实现** → 各项目 `rules/projects/<project-key>/PROJECT_RULES.md`（**仅写项目增量**，不重复本文）与 `skills/projects/<project-key>/`。

## Agent 协作模型（摘要）

**两档分工（不写死模型版本号）**

| 档位 | 职责 | 子 Agent（`Task`） |
|------|------|-------------------|
| **编排档** | 阶段门、方案、范围白名单、验收、汇总 | **默认禁止**；见下「仅编排档允许的派发」 |
| **执行档** | 已锁定的机械落盘（多文件写入、大段生成、跑固定验证命令） | **禁止再启**子 Agent |

- **执行档识别（随 Composer / Cursor 升级自动适用）**：派发 `Task` 时 `model` 的 slug **以 `-fast` 结尾**，或产品文档标明为 fast/执行档；**禁止**在规则正文绑定 `composer-2.x-fast` 等具体版本号。
- **编排档识别**：当前主会话模型；若 slug 含 `-fast` 或用户选定执行档，则本段「编排档」约束不适用（且不得再派子 Agent）。

**默认（编排档）**

- 调查、读代码、单文件修改、评分/文档归纳、用户问答 → 在本会话用 Read/Grep/Glob/Shell **直接完成**。
- **不得**为「看看目录结构」「找某文件」「通读 SKILL 列表」等可一次工具链完成的任务启 `explore` / `generalPurpose` 子 Agent。
- 用户写明「不要子 Agent / 直接做 / 别后台跑」→ **零** `Task` 调用。

**仅编排档允许的派发（执行档子任务）**

同时满足方可 `Task`：

1. 任务类型 = **机械落盘**（非探索、非方案权衡）；
2. 路径/内容/验收已写清（或已有 Hub `prompts/share/agent-task/*.prompt.md`）；
3. 命中硬触发之一：写入 **≥ 2** 个文件；或单文件预计 **> 1500** 输出 token；或 delivery 规定的批量机械任务。

未齐清单或边界 → 编排档先澄清或自行摸底，**禁止**先派子 Agent。

**与 `delivery-workflow` 的关系**

- 硬触发、7 要素、Hub 任务 prompt → **`delivery-workflow`**（其 R2 要求执行档 slug 以 `-fast` 结尾，与上文一致）。
- `delivery-workflow` 的「必须派发」**仅指执行档机械任务**，**不**授权用子 Agent 替代编排档调查。
- skill 体量门禁 → **`skill-engineering`** + `scripts/check-skill-size`（分级见 `agent-hub-bootstrap` → `references/script_tiering.md`）。

# AI Growth Mirror — 项目增量规则

> 全局规则见 hub `rules/common/`（同步到仓内 `AGENTS.md`）。**本文仅写 ai-growth-mirror 增量。**

## 技能路由

| 场景 | 先读 |
|------|------|
| 本仓库功能 / 报告 / reader / CLI | hub `skills/projects/ai-growth-mirror/ai-growth-mirror-dev/SKILL.md` |
| 研发节奏 | `delivery-workflow` |
| 架构权威 | 仓内 `docs/design/ARCHITECTURE_PRINCIPLES.md` |

## 增量硬约束

- 报告主编排真源：`application/orchestrator.generate_report_artifacts`；禁止 CLI 双流水线。
- 禁止未经用户确认删除 `docs/review/growth_mirror/REPORT_VALUE_RECOVERY_INVENTORY.md` 冻结能力。
- **禁止**对 `ai-growth-mirror` 工作区执行 hub `sync-prompts`；不在仓内挂载 hub prompt 真源。
- 开源：不提交个人 HTML/JSON、`config.yaml`、本机路径。
