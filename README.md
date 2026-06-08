# AI Growth Mirror (AI 协作成长镜)

[![Release](https://img.shields.io/badge/Release-v0.8.1-blue.svg)](./pyproject.toml)
[![Schema Version](https://img.shields.io/badge/Schema-v1.5-blue.svg)](./ai_growth_mirror/domain/cache_schema.py)
[![Python Version](https://img.shields.io/badge/python-3.12+-green.svg)](./pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](./LICENSE)

> **你是否每天都在大量使用 Cursor、Claude Code、Trae 等 AI 编码工具，却感觉交付结果不稳定？或者经常被 AI 牵着走，不知道协作的问题到底出在哪里？**
>
> **AI Growth Mirror** 是一面**本地优先**的 **Agentic 操作成熟度评估系统**。它静默、安全地读取你本机已有的 AI 编码会话历史，通过"四证法"和"六轴底盘"算法，将你模糊的协作感觉转化为**可观察、可解释、可复盘**的可视化成长报告。它不是"好看的 AI 使用海报"，而是帮你打破协作瓶颈、沉淀高杠杆技术资产的成长产品。

---

## 🌐 AI 工具三阶段演进：你处于哪个阶段？

AI 工具的发展正在经历三个阶段转型，评估重心也在随之迁移：

```
阶段一（Copilot）          阶段二（Agentic）           阶段三（Autonomous）
─────────────────────    ─────────────────────────    ──────────────────────────
人写代码，AI 补全          人定目标，AI 执行             人做战略，AI 自主完成
intent 很重要              execution 才是核心            评估对齐与控制能力
"Prompt 写得好不好"         "能否驱动 AI 稳定交付"        "能否建立可信任的 AI 系统"
```

**AI Growth Mirror 的定位**：不是 Prompt 打分器，而是 **Agentic 操作成熟度评估**。
从 v0.7 开始，评估重心从「你的 Prompt 写得有多完整」迁移到「你能否把 AI 变成稳定可复用的生产力系统」。

---

## 🎯 评估方法论："四证法"

AI Growth Mirror 拒绝无意义的单纯统计（如消息数、敲代码行数），而是用**"四证法"**真实映射你的人机协作水平：

* 🎯 **Context Frame (上下文边界)**: 是否在协作启动与对齐阶段，为任务建立清晰的目标、约束和验收标准？（可通过单轮精准输入或多轮交互澄清完成）
* 🔗 **Flow Orchestration (连续流编排)**: 是否驱策 AI 连续解决复杂问题，而不是每一步都靠人工接管？
* 🔁 **Proof Loop (闭环验证)**: 是否把构建、测试与纠偏行为深度融入人机交互中？
* 📦 **Method Asset (方法资产化)**: 是否将有效的实践提炼为 Rule、Skill、Workflow 等高杠杆资产并产生复用？

> **四证法是方法论入口（4 个好记的协作支柱），下面的六轴雷达是它的度量展开**。映射关系：
> - Context Frame → **协作框定**
> - Flow Orchestration → **协作驱动 + 实现下潜**（既要连续推进，也要真正下潜到实现）
> - Proof Loop → **交付收口 + 恢复推进**（构建/测试收口 + 偏航后的纠偏）
> - Method Asset → **Agentic 系统化**

---

## 📈 六轴 Agentic 成熟度雷达（v0.7+）

每一期生成的评估结果都会投射到**六轴协作雷达**（协作指数由此计算），它是上方「四证法」的可度量展开：

| 协作能力轴 | v0.7 权重 | v0.8 权重 | v0.8.1 权重 | 衡量内容 |
|-----------|:---------:|:---------:|:-----------:|---------|
| **协作框定** (`collaboration_framing`) | 15% | 14% | **14%** | 协作启动质量，包含目标锁定速度与主动澄清率（v0.8.1升级） |
| **协作驱动** (`execution_driving`) | 24% | 25% | **25%** | 自主工具链长度、子代理编排与人机协作节奏（Agentic 主战场）|
| **实现下潜** (`implementation_depth`) | 20% | 20% | **19%** ↓ | 文件修改量、代码验证覆盖率与实现边界控制 |
| **交付收口** (`delivery_closure`) | 20% | 20% | **19%** ↓ | 任务完成率、验证行为率与测试用例运行表现 |
| **恢复推进** (`adaptive_recovery`) | 11% | 10% | **10%** | AI 偏航或报错时，纠偏和回到正轨的质量 |
| **Agentic 系统化** (`agentic_system`) | 10% | 11% | **13%** ↑ | Skill/Workflow/MCP/Subagent 等方法资产化能力 |

> **为什么这样调整**：见 [docs/design/v0.7.0-DESIGN.md](docs/design/v0.7.0-DESIGN.md)、[docs/design/v0.8.0-DESIGN.md](docs/design/v0.8.0-DESIGN.md) 与 [docs/design/v0.8.1-DESIGN.md](docs/design/v0.8.1-DESIGN.md)

---

## ✨ 核心亮点 (v0.8.0)

### 1. 🧭 Agentic 操作成熟度六轴评估
从 v0.7 起，系统不再围绕"Prompt 写得好不好"做单点判断，而是用 **协作框定、协作驱动、实现下潜、交付收口、恢复推进、Agentic 系统化** 六轴评估真实协作成熟度。v0.8 将 `collaboration_framing` 定稿为正式轴，并把协作启动质量从"首轮完备度"扩展到多轮目标锁定能力。

### 2. 🎯 目标锁定速度 (Goal Locking Speed)
v0.8 新增 `goal_locking_speed`：通过 `turns_until_first_file_write` 观察用户能否快速驱动 AI 锁定目标、边界与可交付路径。支持精细工具流的 reader 会记录首次写入前的用户轮数；缺少工具流的历史会话会使用明确 fallback，避免把"没有信号"伪装成深度判断。

### 3. 🕸️ Agentic Evidence Graph + Action Contract
报告底层会构建六维证据图：任务意图、方法使用、上下文、执行路径、收口状态与人工干预。训练建议不再是固定文案，而是由真实短板、纠偏模式和证据图生成 Rule / Skill / Workflow / Checklist 形式的 Action Contract。

### 4. 📊 训练闭环 + 环比追踪
- **Action Contract 回看**：自动识别上一期建议在本期的改善效果（improved / partial / unchanged）
- **成长轨迹**：六轴评分 + 摩擦变化的逐期 delta，SVG 趋势折线 + 变化箭头
- **CLI `status`**：`ai-growth-mirror status` 即时显示样本进度 + 本周练习提示（< 100ms）

### 5. 🔌 9 款主流 AI 工具一键适配
一键扫描，自动识别并聚合以下 9 款 AI 工具：
- **国际主流**：Claude Code、Codex、Cursor、Gemini、Cline、Kilo Code
- **国产先锋**：CodeBuddy、Trae、QCoder

### 6. 🔒 本地优先，隐私可控
默认使用本地规则引擎离线分析。即使在 `llm` 模式下引入 LLM 语义诊断，也仅发送脱敏后的会话摘要，而非完整代码原文。运行 `generate --redact` 会自动脱敏 HTML 报告、Sidecar、分享卡与快照中的路径和代码隐私。

---

## 📊 报告效果预览

生成 `ai-growth-mirror.html` 后双击即可本地打开，无需部署。报告按「诊断 → 训练 → 追踪」组织，侧边栏可快速跳转各区块。

### 本期协作进化报告（Hero）

首屏一眼看懂：**等级 · 协作指数  · 下一步练什么**。支持浅色 / 深色主题切换。

| 浅色主题 | 深色主题 |
|:---:|:---:|
| ![Hero 浅色主题](docs/assets/images/report-hero-light.png) | ![Hero 深色主题](docs/assets/images/report-hero-dark.png) |

### 成长信号总览

六轴协作雷达 + 协作指数趋势折线 + Top 3 短板与可执行行动建议。

![成长信号总览：六轴雷达、趋势折线与短板排行](docs/assets/images/report-growth-signals.png)

### 协作风格透镜

四维度协作画像（启动 / 推进 / 收口 / 复用），帮你看见自己的 AI 协作「打法」而非只看分数。

![协作风格透镜：四维度协作画像](docs/assets/images/report-style-lens.png)

### 工作聚焦与协作节奏

你在做什么（项目、目标类型、工具与语言）+ 双节奏切换等协作节律洞察。

![工作聚焦与协作节奏](docs/assets/images/report-work-focus-rhythm.png)

### 本期值得保留的方法

从高分会话中提炼可复用的协作范式（深度委托、工具链编排、结构化执行），直接迁移到下一类相似任务。

![本期值得保留的方法：高分会话范例](docs/assets/images/report-exemplars.png)

---

## 🚀 快速开始

### 运行环境
- Python **3.12+**

### 1. 安装项目
```bash
# 克隆仓库后在根目录运行：
pip install -e .

# 如果需要使用 Anthropic/Gemini 服务提取 LLM 语义诊断和 Coach 建议：
pip install -e ".[llm]"
```

### 2. 初始化配置 (可选，用于 API Key 与资产足迹)
```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入 LLM Provider、API Key、本地 Agent 资产扫描根目录
```

### 3. 一键生成个人成长报告
```bash
# 1. 切换至您的任意开发工作区目录（通常为项目仓库根目录）
cd /path/to/your/project-workspace

# 2. 生成进化报告与成长快照
ai-growth-mirror generate
```

运行完成后，您的当前目录下将输出：
- `ai-growth-mirror.html`: 个人 Agentic 成熟度交互式分析主报告。
- `ai-growth-mirror.json`: 结构化 Evidence Sidecar（含 Agentic Evidence Graph、覆盖率与统计证据）。
- `ai-growth-mirror.summary.json`: 面向分享卡、二次消费和自动化集成的稳定摘要契约。
- `ai-growth-mirror-share.html`: 对外分享脱敏卡片。
- `ai-growth-mirror-archive/`: 快照存档目录，第二次运行时将自动激活「成长轨迹对比」（本期 vs 上一期）。

---

## 🛠️ 进阶命令参数

* **查看本周样本进度**：`ai-growth-mirror status`
* **指定工具过滤**：`ai-growth-mirror generate --tools cursor,trae`
* **锁定时间窗口**：`ai-growth-mirror generate --since 2026-01-01 --until 2026-06-30`
* **离线规则引擎分析**（零外部网络调用与费用）：`ai-growth-mirror generate --session-read-mode heuristic`
* **过滤分析范围**（按特定 Repository、目录或关键字过滤）：`ai-growth-mirror generate --repo app-repo --dir ~/projects/app`
* **手工对比历史快照**：`ai-growth-mirror compare <left_snapshot_id> <right_snapshot_id>`
* **清理过期缓存**：`ai-growth-mirror cache prune`

---

## 📖 开发者文档索引

对于想要深度定制、贡献 Adapter 或调试算法的开发者，请详细参阅我们的 Canonical 文档：
* [分层依赖与架构总纲](./docs/design/ARCHITECTURE_PRINCIPLES.md)
* [产品路线图](./docs/design/PRODUCT_ROADMAP.md)
* [v0.8.1 协作效能公允度升级与冷启动性能优化](./docs/design/v0.8.1-DESIGN.md)
* [v0.8.0 协作框定与目标锁定速度设计](./docs/design/v0.8.0-DESIGN.md)
* [v0.7.0 Agentic 体系重构设计](./docs/design/v0.7.0-DESIGN.md)
* [v0.6.0 训练闭环设计](./docs/design/v0.6.0-DESIGN.md)
* [产品语气、命名与安全脱敏规范](./docs/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)
* [参与贡献指南](./CONTRIBUTING.md)

---

## 许可证
本项目基于 [MIT License](./LICENSE) 协议发布。
