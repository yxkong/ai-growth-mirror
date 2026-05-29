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

- 高阶推理模型可将**机械落盘**派发给 **`composer-2.5-fast`**；**fast 模型不得再启子 Agent**。
- 典型派发条件：写入 ≥ 2 个文件；或单文件预计 > 1500 输出 token；或任务路径与内容已完全确定。
- 派发格式、子 Agent prompt、设计整合门细节 → **`delivery-workflow`**；skill 体量门禁 → **`skill-engineering`** + `scripts/check-skill-size`（分级见 `agent-hub-bootstrap` → `references/script_tiering.md`）。
