# AI Growth Mirror

**AI Growth Mirror** 是一个本地优先的 AI 协作能力分析工具。在**当前工作目录**扫描 Cursor、Codex、Claude Code等工具的历史会话，生成个人成长报告。

> 核心目标：帮助 AI 工具用户看清自己的协作模式，找到下一步最值得投入的成长方向。

**工作区模型**：在你要放报告的目录执行 CLI（通常是仓库根或项目根）。报告、快照、分析缓存都写在**该目录**，不会默认写到用户 home；本地产物已 `.gitignore`，不提交 git。

---

## 快速开始

### 环境

- Python **3.12+**

### 安装

```bash
pip install -e .
# 开发 / 跑单测：
pip install -e ".[dev]"
# 使用 Anthropic / Gemini provider 时额外安装：
pip install -e ".[llm]"
```

（仓库含 `uv.lock`，亦可用 `uv sync --extra dev`。）

### 配置（推荐）

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml：LLM Key、asset_roots 等
```

- 优先读取当前目录 `./config.yaml`（无需 `-c`）
- 否则回退 `~/.ai-growth-mirror/config.yaml`
- **`config.yaml` 含 API Key，勿提交 git**

### 生成报告

```bash
cd /path/to/your/workspace
ai-growth-mirror generate
# 或未安装 console script 时：
python -m ai_growth_mirror.cli generate
```

默认输出到**当前目录**：

| 路径 | 说明 |
|------|------|
| `ai-growth-mirror.html` | 主报告 |
| `ai-growth-mirror.json` | 结构化 sidecar（`--no-sidecar` 可跳过） |
| `ai-growth-mirror.summary.json` | 分享 / 集成用摘要 |
| `ai-growth-mirror-share.html` | 对外精简结论卡 |
| `ai-growth-mirror-archive/` | 快照归档（成长轨迹对比） |
| `.ai-growth-mirror-runtime/cache/` | session read / 会话分析缓存（同工作区，已 gitignore） |

`ai-growth-mirror-archive/` 的行为约束：

- 第 1 次 `generate`：只写入首个 snapshot，报告内**不会**出现“成长轨迹对比”
- 第 2 次及之后：生成当前报告前，先读取 `ai-growth-mirror-archive/index.json` 中**最近一份历史 snapshot**
- 当前报告里的“成长轨迹对比”固定表示 **本期 vs 当前生成前的上一期**，不是任意两次手工挑选的结果
- 如果要比较任意两个历史快照，使用 `ai-growth-mirror compare <left_snapshot_id> <right_snapshot_id>`

**常用参数：**

```bash
# 默认 --tools all；也可指定单个或多个
ai-growth-mirror generate --tools cursor
ai-growth-mirror generate -t codex -t cursor

# 时间窗
ai-growth-mirror generate --since 2026-01-01 --until 2026-05-31

# 分析模式（默认 auto：有 Key 走 LLM session read，无 Key 走 heuristic）
ai-growth-mirror generate --session-read-mode heuristic
ai-growth-mirror generate --session-read-mode llm

# Agent 资产足迹（hub 或 skills 目录）
ai-growth-mirror generate --hub-root /path/to/your/hub
ai-growth-mirror generate --asset-root ~/.cursor/skills

# 脱敏分享
ai-growth-mirror generate --redact

# 流水线日志
ai-growth-mirror generate -v
```

**快照对比**（需至少两次 generate 产生的 `ai-growth-mirror-archive/`）：

```bash
ai-growth-mirror compare <left_snapshot_id> <right_snapshot_id>
```

**清理过期缓存**：

```bash
ai-growth-mirror cache prune
ai-growth-mirror cache prune --dry-run
```

需要 PDF 时：浏览器打开 HTML → **打印 → 另存为 PDF**（仓库无内置导出 CLI）。

---

## 程序化 API

入口：`ai_growth_mirror.application.orchestrator.generate_report_artifacts`

```python
from pathlib import Path

from ai_growth_mirror.application.orchestrator import (
    GenerateReportRequest,
    generate_report_artifacts,
)

result = generate_report_artifacts(
    GenerateReportRequest(
        tools=["cursor", "codex"],
        session_read_mode="auto",
        output_path=Path("ai-growth-mirror.html"),
        asset_roots=[Path.home() / ".cursor" / "skills"],
    )
)
print(result.output_path, result.session_count, result.growth_level)
```

---

## 报告区块（主导航顺序）

与 `application/report_view.py` → `_build_report_sections` 一致。

| 顺序 | 区块 | 显示条件 |
|:---:|---|---|
| — | **首屏摘要**（Hero + Usage 卡片） | 始终 |
| 1 | **成长信号总览**（含五轴雷达与「协作能力地图」） | 始终 |
| 2 | **阶段评估** | 始终 |
| 3 | **协作等级说明**（L1–L5） | 始终 |
| 4 | **Prompt 成长教练** | 有 PQ 信号时 |
| 5 | **摩擦根因地图** | 始终 |
| 6 | **本期值得保留的方法** | 有样例时 |
| 7 | **下一阶段训练冲刺**（2 项） | 始终 |
| 8 | **你在做什么** | 始终 |
| 9 | **协作节奏** | 始终 |
| 10 | **本期亮点** | 有亮点时 |
| 11 | **AI 资产足迹** | 配置了 hub / asset_root 且有数据 |
| 12 | **成长轨迹对比** | 当前生成前已存在至少 1 份历史 snapshot（通常从第 2 次 generate 开始出现） |
| 附录 | **协作风格透镜** | 始终（不在主导航） |

架构与 Usage 边界：[`docs/design/ARCHITECTURE_PRINCIPLES.md`](./docs/design/ARCHITECTURE_PRINCIPLES.md)

---

## 分析模式

| 模式 | 说明 | API Key |
|------|------|---------|
| `auto` | 有 Key → LLM session read + coaching；无 Key → heuristic（**CLI 默认**） | 可选 |
| `heuristic` | 规则 session read；coaching 仍可在有 Key 时调 LLM | session read 不需要 |
| `llm` | 每会话 LLM 语义 session read | 需要 |

建议先用 `heuristic` 或 `auto`（无 Key）验证 reader 接入，再开 `llm`。

---

## 支持的 AI 工具

CLI `--tools` 可选：`all` | `cursor` | `codex` | `claude` | `trae` | `qcoder`（`claude` 为 `claude_code` 别名）。

| 工具 | 配置键 `tools.*` | 典型数据源 | 备注 |
|------|------------------|------------|------|
| Cursor | `cursor` | `~/.cursor/` | 默认启用 |
| Codex | `codex` | `~/.codex/` | 默认启用 |
| Claude Code | `claude_code` | `~/.claude/` | 需在 config 中 `enabled: true` |
| Trae | `trae` | `~/.trae-cn/` 或 Windows workspaceStorage | 默认随 `all` |
| QCoder | `qcoder` | `~/.qoder/` 或 Windows workspaceStorage | 默认随 `all` |

---

## Token / 成本 / 缓存（报告内）

- 只统计 reader 能解析 **usage 字段**的会话（以 **Codex、Claude Code** 为主）
- Cursor / Trae / QCoder 仍参与成长评分；无 usage 时 Hero 显示 `--`，不填 0
- `memory` 当前未采集，报告会标注

---

## 配置说明

见 [`config.example.yaml`](./config.example.yaml)。要点：

```yaml
cache:
  # 默认 .ai-growth-mirror-runtime/cache（相对 cwd，已 gitignore）
report:
  asset_roots:
    - /path/to/your/agent-hub   # 可选
tools:
  claude_code:
    enabled: true               # 需要 Claude Code 会话时打开
```

---

## 数据隐私

- 本地处理；`heuristic` 不调外部 LLM
- `llm` / `auto` 会发送**会话摘要级**文本做 session read / coaching（非完整原文）
- `--redact` 脱敏 HTML、sidecar、summary、share-card

---

## 开源提交前

| 勿提交 | 示例 |
|--------|------|
| 个人报告 | `*.html`、`ai-growth-mirror*.json` |
| 密钥配置 | `config.yaml`、`.env` |
| 运行时 | `.ai-growth-mirror-runtime/`、`ai-growth-mirror-archive/`、`source/` |
| IDE / Agent | `.cursor/`、`.vscode/` |

详见 [`docs/config/OPEN_SOURCE_GOVERNANCE.md`](./docs/config/OPEN_SOURCE_GOVERNANCE.md)。

---

## 许可证与贡献

- [MIT LICENSE](./LICENSE)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- 设计文档：[`docs/design/README.md`](./docs/design/README.md)
