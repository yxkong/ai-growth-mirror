---
title: Growth Mirror Design Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-08
---

# AI Growth Mirror 设计文档索引

> 本目录收录了 AI 成长镜（AI Growth Mirror）的核心架构与详细设计方案。

## 设计真源列表

| 文档 | 状态 (Status) | 主要用途 / 覆盖领域 |
|------|--------------|-------------------|
| **[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)** | **canonical · 架构真源** | 定义系统分层原则、指标权重逻辑、防颠簸与惰性解析等硬性稳定性规范。 |
| **[AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)** | **canonical · 详细设计** | 个人版报告的信息架构、文案禁用词边界、各模块数据映射（包含六轴雷达、Prompt教练与协作节奏等）。 |
| **[PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md)** | **canonical · 产品规划** | 产品的演进路线图，明确产品版本与缓存 Schema 版本的映射关系，定义 v0.4.2 到 v1.5.0 的技术与功能走向。 |
| **[v0.8.0-DESIGN.md](./v0.8.0-DESIGN.md)** | **canonical · 当前版本设计** | 定义 `collaboration_framing` 四维结构、`goal_locking_speed` 信号与 v0.8 评分闭环。 |
| **[v0.7.0-DESIGN.md](./v0.7.0-DESIGN.md)** | **canonical · Agentic 重构设计** | 定义六轴 Agentic 成熟度、`agentic_system` 正式轴与恢复推进修正。 |
| **[v0.6.0-DESIGN.md](./v0.6.0-DESIGN.md)** | **canonical · 训练闭环设计** | 定义 Action Contract 回看、环比 delta、CLI status 与主动澄清信号。 |
| **[AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](./AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md)** | **supporting · 根因分析** | 深度阐述为何需要 AI 成长镜这类工具，剖析用户协作习惯量化的必要性及方法论主线（四证法）。 |
| **[OPEN_SOURCE_GOVERNANCE.md](../config/OPEN_SOURCE_GOVERNANCE.md)** | **supporting · 治理说明** | 规范项目开源范围、本地缓存隐私保护规则以及代码安全敏感信息脱敏标准。 |

> [!NOTE]
> 建议阅读顺序：  
> **1. 根因分析** (了解产品痛点与四证法) → **2. 架构总纲** (对齐开发分层与硬性原则) → **3. 详细设计** (对齐报告结构与文案) → **4. 产品规划** (理解后续演进与路线)

---

## 核心演进历程与版本对齐

为规范研发版本控制，项目严格区分为：
- **产品版本 (Product Version)**：遵循 SemVer 语义化规范，代表用户端的功能及交互升级。
- **缓存协议版本 (Cache Schema Version)**：独立演进，用于控制本地/远程序列化缓存文件的格式兼容性。

### 1. 当前版本：v0.8.0 (基于 Cache Schema 1.4)
*当前版本完成 Agentic 评估底盘收口：从 Prompt 时代的任务表达，升级为多轮协作启动质量与 Agentic 系统化能力评估。*
- **协作框定重定义**：`intent_clarity` 已升级为 `collaboration_framing`，包含方向清晰、上下文注入、目标锁定速度、主动澄清率四个子项。
- **目标锁定速度**：新增 `goal_locking_speed`，以首次有效文件写入前的用户轮数作为工程会话代理信号。
- **外挂加分归并**：`tool_leverage_bonus` 与 `workflow_maturity_bonus` 已并入 `agentic_system`，主分由六轴统一承载。
- **报告闭环**：主报告、Evidence Sidecar、`*.summary.json`、分享卡与 snapshot archive 均从同一条 application 编排链生成。

### 2. 近期版本脉络
- **v0.7.0 / Schema 1.4**：六轴 Agentic 成熟度底盘、`agentic_system` 正式轴、恢复推进误判修正。
- **v0.6.0 / Schema 1.3**：训练回看、环比 delta、CLI `status` 与主动澄清信号。
- **v0.5.0 / Schema 1.2**：免部署单文件交互式报告、Scroll Spy、雷达交互和短板联动。
- **v0.4.2 / Schema 1.2**：缺失型指标归一化、防缓存颠簸、多机器隔离与惰性 Placeholder 解析。
- **v0.4.0 / Schema 1.1**：Agentic Evidence Graph、Action Contract Generator 与三段式诊断底座。

---

## 修订记录

- **2026-06-08**：同步当前版本到 **Product v0.8.0 / Cache Schema 1.4**，补齐 v0.8/v0.7/v0.6 设计入口与报告闭环说明。
- **2026-06-06**：重构文档索引，纠正 v1.2 混淆为产品版本号的问题，规范为 **Product v0.4.2 / Schema 1.2**，补充缺失文件，链接全部转为绝对 `file://` 格式。
- **2026-06-04**：补充 Agentic 架构核心机制说明与阅读入口。
- **2026-05-25**：创建第一版设计索引。
