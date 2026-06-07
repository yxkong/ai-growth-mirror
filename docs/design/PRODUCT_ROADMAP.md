# AI Growth Mirror — 产品长期规划与路线图

> 本文档定义 AI 成长镜（AI Growth Mirror）的核心定位、当前阶段以及中长期产品演进路线图。

---

## 1. 产品定位与核心价值

**一句话定义**：帮助 AI coding 用户看见并改进与 AI 协作时的行为盲区，评估 **Agentic 操作成熟度**，提供可执行的成长训练方案。

> **核心定位（v0.7+ 明确）**：AI Growth Mirror 不是 Prompt 打分器，而是 **Agentic 操作成熟度评估系统**。它评价的不是"你的 Prompt 写得有多完整"，而是"你能否把 AI 变成稳定可复用的生产力系统"。

* **诊断**：我的协作模式哪里弱？（从 Prompt 完备度扩展到 Agentic 系统化能力全链路）
* **训练**：如何改进？（每次生成给出 2 项清晰、可落地的两周训练计划与 Action Contract 契约）
* **追踪**：我有进步吗？（自动追踪 30 天成长轨迹，显示对比分析与人工纠偏成本趋势）

**产品设计六大原则**：
1. **诊断先于评分**：用户最关心的是“我如何提升”，而非抽象的 65 分还是 70 分。
2. **可执行先于全面**：每次仅建议 2 个核心训练点，避免信息轰炸。
3. **如实披露**：清晰标识分析的置信度边界，弱化代理分析，不伪装 LLM 深度智能。
4. **程序员审美**：高信息密度，去除花哨的视觉光晕，倡导精致、紧凑的数据呈现。
5. **数据自主**：所有数据全本地运行解析，不上传至任何中心化服务器，保障隐私安全。
6. **增量演进**：核心版本专注解决 1-2 个使用与协作体验缺口。

---

## 2. 版本管理体系

为保障核心业务的持续迭代与数据库/缓存的稳定性，项目采用解耦的版本架构：

* **产品版本 (Product Version)**：遵循 SemVer 语义化规范。代表用户直接体验到的功能、交互及 CLI 命令升级。
* **缓存 Schema 版本 (Cache Schema Version)**：指示 `SessionRead` / `CoreEvidence` 序列化在缓存底座中的兼容性，独立版本升级会触发旧缓存的自动迁移与重新解析。

| 产品版本 (Product Version) | 缓存 Schema 版本 | 核心关注点 | 状态 |
|----------------------------|-----------------|-----------|------|
| **v0.4.0** | 1.1 | Agentic 核心诊断架构与证据事实图 | ✅ 已发布 |
| **v0.4.2** | 1.2 | 缺失型指标归一化、防颠簸缓存与多端隔离 | ✅ 已发布 |
| **v0.5.0** | 1.2 | 免部署单文件交互式报告 (Scroll Spy / Deficit 联动) | ✅ 已发布 |
| **v0.6.0** | 1.3 | 训练回看与环比增量闭环 (Practice Feedback Loop) | ✅ 已发布 |
| **v0.7.0** | 1.4 | **Agentic 操作成熟度体系重构**（六轴 + 三层模型 + environmental-recovery） | ✅ 已发布 |
| **v0.8.0** | 1.4 | `collaboration_framing` 重定义 + `goal_locking_speed` 新信号 | ✅ 已发布 |
| **v0.9.0** | 1.4 | 多设备快照聚合与团队聚合看板 | 📅 规划中 |
| **v1.0.0+** | 2.0 | 插件市场与开放平台 API | 📅 长期规划 |

---

## 3. 已完成里程碑

### 3.1 v0.4.0 (基于 Schema 1.1) — Agentic 诊断底座
* **三段式 LLM 诊断层**：Stage-1 候选生成 -> Stage-2 LLM 深度诊断与反例校验 -> Stage-3 规则重排过滤。
* **Agentic Evidence Graph**：六维会话事实图（任务意图、使用方法、上下文、执行路径、收口状态、人工干预）落地，并写入 Sidecar 归档。
* **Action Contract Generator**：动态规则产出个性化 Rule/Skill/Workflow 起草建议，替代原有的固定文字卡片。
* **人工纠偏成本趋势**：追踪快照中 `human_intervention_session_rate` 的 Improving/Worsening/Flat 趋势并对比。

### 3.2 v0.4.2 (基于 Schema 1.2) — 性能与评分规范重构
* **指标动态归一化**：在 Cursor/Trae 无 Token 指标时，在 [scorer.py](./ai_growth_mirror/domain/growth/scorer.py) 中动态剔除 Token 权重，并重分配其余指标权重，解决零值惩罚的缺口。
* **Per-Session DB Revision**：利用 AI 聊天核心行哈希，防止因无关的 IDE 状态修改导致缓存颠簸失效。
* **多机器物理隔离**：支持 `(source_machine, session_id)` 双重唯一去重，并在缓存中按机器子目录物理隔离。
* **惰性 Placeholder 解析**：初扫描阶段仅提取 project_path 构建 Placeholder 会话，过滤采样后再深度解析，吞吐率提升百倍。
---

## 4. 中期规划 (v0.5.0 ~ v0.8.0)

> **演进逻辑**：诊断（v0.4）→ 可读交互（v0.5）→ 训练闭环（v0.6）→ **Agentic 评估重构（v0.7）** → 协作框定重定义（v0.8）→ 跨端聚合（v0.9）→ 平台化（v1.0）。每一版只解决 1–2 个核心缺口，避免功能堆砌；后一版依赖前一版的 snapshot/sidecar 契约，不推翻主链。

### 报告内容版本闭环规划

> 每个版本的报告必须从「用户能在报告里看到什么」视角做闭环设计，而非只有功能特性描述。

| 版本 | 报告新增/变化内容 | 用户能看到什么 | 闭环依据 |
|------|-----------------|--------------|---------|
| **v0.5** ✅ | 五轴雷达交互 + Scroll Spy + Deficit 联动跳转 | 点击短板即跳至改写建议卡片；雷达 hover 显示子维度事实 | 报告交互可用性 |
| **v0.6** ✅ | 训练回看折叠区块 + 环比 delta 卡片 + CLI status | 上期建议是否落地（improved/partial/unchanged）；六轴分趋势折线 | 教练建议可追踪 |
| **v0.7** ✅ | **六边形雷达**（加 agentic_system 轴）+ environmental-recovery 修复 | 第六轴「Agentic 系统化」独立展示；恢复推进不再被误判为用户失误 | Agentic 评估完整性 |
| **v0.8** ✅ | `collaboration_framing` 重命名 + goal_locking_speed 信号 | 雷达轴标签从「任务表达」改为「协作框定」；tooltip 展示目标锁定速度 | 多轮协作模式识别 |
| **v0.9** 📅 | 跨机器合并视图 | 多台电脑的会话合并进同一报告；不同设备的能力分布对比 | 多端工作者需求 |
| **v1.0** 📅 | 社区基准对标 + 插件扩展轴 | "您的 Agentic 系统化能力处于全球前 30%"；第三方自定义轴 | 平台化开放 |

### 4.1 v0.5.0 — 免部署交互式报告 (SPA-like Single-File HTML) ✅
* **核心目标**：在不破坏“本地双击即用”的零服务器前提下，大幅增强数据报告的交互体验。
* **技术路线**：避开复杂的 React/Vue SSR 本地打包（防止本地文件的 CORS 错误），采用 **纯前端原生 JS 与精致 CSS 实现的单文件交互方案**。
* **主要特性**：
  - **Scroll Spy & Sidebar Sticky**：侧边栏滚动跟随，章节视口高亮。
  - **Deficit-to-Card Linking**：点击首屏的“短板诊断 (Deficit)”直接跳转至对应的“改写建议卡片 (Rewrite Card)”。
  - **雷达图悬停交互**：五轴雷达图 Hover 显示各轴评分因子与子维度事实。
  - **原生暗黑模式 (Dark Mode)**：支持系统级暗色主题适配及手动切换。

### 4.2 v0.6.0 — 训练环比增量闭环 (Practice Feedback Loop) ✅

> 详细设计见 [v0.6.0-DESIGN.md](v0.6.0-DESIGN.md)

**当前落地进度**（截至 2026-06-07）：
- ✅ 主动澄清信号检测 + `intent_clarity` 加成（heuristic + scorer，单源 `_intent_clarity_boost`）
- ✅ Action Contract 环比评估 + 报告内「上期训练回看」折叠区块
- ✅ 雷达区协作指数趋势折线 + delta 徽章
- ✅ CLI `status` 命令（本周样本进度 + 上期契约提示），含 `test_cli_status.py` 有/无历史两路
- ✅ Schema 升至 1.3；LLM 与 heuristic 两路共用 `detect_active_clarification`，`active_clarification` 字段对齐
- ✅ 加成在报告五轴雷达 tooltip 透明展示；`summary.json` 输出 `active_clarification_rate` / `intent_clarity_boost`

* **核心目标**：让"教练建议"可追踪、可评估，杜绝一次性建议的堆砌；修正多轮交互协作的评分悖论。
* **主要特性**：
  - **Action Contract 追踪**：生成报告时自动识别上一期 `action_contracts` 在本期的改善效果（improved / partial / unchanged），带置信度修正；无前序数据时显示"暂无前序数据"，不强行渲染空卡片。
  - **环比增量分析**：五轴评分 + 摩擦变化的逐期 delta 分析，SVG 趋势折线 + 变化箭头卡片在报告内展示；只有一份快照时环比分部自动隐藏。
  - **主动澄清信号修正**：识别用户通过多轮交互完成高质量任务的协作模式（`active_clarification`），对 `intent_clarity` 给予最高 +8 分加成，解决"多轮交互被低分惩罚"的悖论；加成在报告 tooltip 中透明展示。
  - **CLI `status` 命令**：`ai-growth-mirror status` 即时显示样本收集进度（< 100ms，不触发完整重算）+ 本周来自上期 Action Contract 的练习提示。
  - **报告内训练回看区块**：`#section-growth-plan` 下方新增可折叠"上期训练回看"，展示 contract 执行效果列表。

### 4.3 v0.7.0 — Agentic 操作成熟度体系重构 ✅

> 详细设计见 [v0.7.0-DESIGN.md](v0.7.0-DESIGN.md)

**核心判断**：`intent_clarity` 对 Agentic 成熟度偏高；`agentic_system` 是门槛触发器而非连续贡献项；「继续/恢复推进」被误归为用户问题——三个缺陷合一并修。

**三层成熟度模型**（取代隐性的单层评分观）：

```
第三层：能否沉淀成可复用 AI 工作系统  → agentic_system（新增正式轴，10%）
第二层：AI 能否被驱动完成真实工作    → execution + impl + delivery + recovery
第一层：人能否启动协作               → intent_clarity（降权到 15%）
```

**主要变更**：
- **六轴体系**：`agentic_system` 升格为第六个正式评分轴（10%），进入雷达图与 gap_rankings
- **权重重分配**：`intent_clarity` 20%→15%，`execution_driving` 22%→24%，`agentic_system` 门槛触发→10%
- **environmental-recovery 修复**：「继续/重试/恢复推进」类消息归入 `environmental`，不再误生成 `off-track`
- **六边形雷达图**：SVG 从五边形升级为六边形

### 4.4 v0.8.0 — `collaboration_framing` 重定义 ✅

* **核心目标**：`intent_clarity`（任务表达）重定义为 `collaboration_framing`（协作框定能力），内涵从「首轮完备度」扩展为「多轮协作启动质量」。
* **主要变更**：
  - `active_clarification_rate` 从补丁加成变为 `collaboration_framing` 最大权重子项（0.34）
  - 新增 `goal_locking_speed` 信号：前期对齐目标、边界与可交付产出路径的速度；工程会话可用首次文件写入作为可观测代理
  - `tool_leverage_bonus` 和 `workflow_maturity_bonus` 并入 `agentic_system`，消除外挂加分

---

## 5. 长期规划 (v0.9.0+)

### 5.1 v0.9.0 — 跨机器快照聚合与团队聚合
* **核心目标**：打通多设备使用壁垒，为多端工作的程序员和团队提供无摩擦的聚合视图。
* **主要特性**：
  - **Cross-Machine CLI Aggregator**：在 CLI 中支持 `--sources` 传递多机器缓存路径，合并生成跨设备统一画像。
  - **团队脱敏看板 (Manager Dashboard)**：支持在完全本地化、匿名且脱敏的原则下，合并多个用户的快照 Sidecar，生成团队/部门的常见协作痛点 Top 3 与能力平均基线。

### 5.2 v1.0.0 — AI Coding 教练平台
* **开放平台 API**：允许第三方 AI 工具（如自定义 IDE 脚本、VS Code 插件）通过 API 输入会话包。
* **插件市场 (Plugin Market)**：支持开发者基于 `Agentic Evidence Graph` 的六维事实，自定义编写规则/LLM 评估插件，扩展六轴评分。
* **匿名社区基准 (Community Benchmark)**：在用户完全自愿的前提下，允许上传无敏感数据的匿名 sidecar。平台提供对标服务（例如："您的 Agentic 系统化能力处于全球前 30%"）。

### 5.3 v1.5.0 — IDE 实时自检插件
* **实时自检**：在 IDE 的 Chat 面板增加"发送前自检 (Preflight Check)"悬浮提示，在用户点击发送 Prompt 前进行拦截诊断。
* **偏航预测**：基于用户最近的成长短板，实时预判当前 Prompts 是否存在上下文缺失或偏航风险。

---

## 6. 修订记录

| 日期 | 产品版本 | 缓存 Schema | 变更概要 |
|------|---------|-------------|---------|
| 2026-06-07 | v0.8.0（发布收口） | 1.4 | **v0.7.0 / v0.8.0 发布状态对齐**：版本总表与报告内容表中 v0.7/v0.8 由「📅 规划中」转 ✅ 已发布；六轴权重定稿 `14/25/20/20/10/11`；与 README、ARCHITECTURE_PRINCIPLES、DETAILED_DESIGN 同步六轴口径。 |
| 2026-06-07 | v0.7.0（规划） | 1.4 | **Agentic 操作成熟度体系重构规划**：产品定位更新为"Agentic 操作成熟度评估"；三层成熟度模型；`agentic_system` 升格第六轴（10%）；`intent_clarity` 降权 20%→15%；`execution_driving` 升权 22%→24%；`environmental-recovery` 修复方案；v0.8.0 `collaboration_framing` 预留；新增 [v0.7.0-DESIGN.md](v0.7.0-DESIGN.md)。 |
| 2026-06-07 | v0.6.0（收口） | 1.3 | **v0.6.0 发布收口对齐**：主动澄清加成在雷达 tooltip 透明展示；`summary.json` 补 `active_clarification_rate`/`intent_clarity_boost`；LLM 与 heuristic 共用 `detect_active_clarification`；Schema 1.3；新增 `test_cli_status.py`。落地进度清单全部转 ✅。 |
| 2026-06-06 | v0.5.0 | 1.2 | **v0.5.0 发布收口**：标记免部署交互式报告为已发布；明确 v0.5→v0.6→v0.7 演进逻辑；补充 v0.6.0 落地进度清单。 |
| 2026-06-06 | v0.6.0（规划） | 1.3 | **v0.6.0 详细设计落地**：补充 Action Contract 追踪、环比 delta 卡片、主动澄清信号修正（解决多轮交互评分悖论）、CLI status 命令完整设计；新增 [v0.6.0-DESIGN.md](v0.6.0-DESIGN.md)；更新路线图特性描述。 |
| 2026-06-06 | v0.4.2 | 1.2 | **重构路线图**：解耦产品版本与缓存版本，厘清 v0.4.2/v0.4.0 里程碑；修正 v0.5.0 技术方案为"单文件免部署交互"；细化 v0.6.0/v0.7.0 规划。 |
| 2026-06-03 | v0.4.0 | 1.1 | 引入导航/DOM 对齐、滚动高亮同步、Scope 配置化、五轴比例与评估状态等功能。 |
| 2026-06-02 | v0.1.0 | 1.0 | 初版产品规划设立。 |
