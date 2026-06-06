---
title: Growth Mirror Design Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-06
---

# AI Growth Mirror 设计文档索引

> 本目录收录了 AI 成长镜（AI Growth Mirror）的核心架构与详细设计方案。

## 设计真源列表

| 文档 | 状态 (Status) | 主要用途 / 覆盖领域 |
|------|--------------|-------------------|
| **[ARCHITECTURE_PRINCIPLES.md](file:///Users/yxk/workspace/projects/github/ai-growth-mirror/docs/design/ARCHITECTURE_PRINCIPLES.md)** | **canonical · 架构真源** | 定义系统分层原则、指标权重逻辑、防颠簸与惰性解析等硬性稳定性规范。 |
| **[AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](file:///Users/yxk/workspace/projects/github/ai-growth-mirror/docs/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)** | **canonical · 详细设计** | 个人版报告的信息架构、文案禁用词边界、各模块数据映射（包含五轴雷达、Prompt教练与协作节奏等）。 |
| **[PRODUCT_ROADMAP.md](file:///Users/yxk/workspace/projects/github/ai-growth-mirror/docs/design/PRODUCT_ROADMAP.md)** | **canonical · 产品规划** | 产品的演进路线图，明确产品版本与缓存 Schema 版本的映射关系，定义 v0.4.2 到 v1.5.0 的技术与功能走向。 |
| **[AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](file:///Users/yxk/workspace/projects/github/ai-growth-mirror/docs/design/AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md)** | **supporting · 根因分析** | 深度阐述为何需要 AI 成长镜这类工具，剖析用户协作习惯量化的必要性及方法论主线（四证法）。 |
| **[OPEN_SOURCE_GOVERNANCE.md](file:///Users/yxk/workspace/projects/github/ai-growth-mirror/docs/config/OPEN_SOURCE_GOVERNANCE.md)** | **supporting · 治理说明** | 规范项目开源范围、本地缓存隐私保护规则以及代码安全敏感信息脱敏标准。 |

> [!NOTE]
> 建议阅读顺序：  
> **1. 根因分析** (了解产品痛点与四证法) → **2. 架构总纲** (对齐开发分层与硬性原则) → **3. 详细设计** (对齐报告结构与文案) → **4. 产品规划** (理解后续演进与路线)

---

## 核心演进历程与版本对齐

为规范研发版本控制，项目严格区分为：
- **产品版本 (Product Version)**：遵循 SemVer 语义化规范，代表用户端的功能及交互升级。
- **缓存协议版本 (Cache Schema Version)**：独立演进，用于控制本地/远程序列化缓存文件的格式兼容性。

### 1. 当前版本：v0.4.2 (基于 Schema 1.2)
*本版本重点攻克了大规模会话日志场景下的吞吐与评分准确度问题。*
- **评分动态归一化**：在 Cursor/Trae 无 Token 指标时，动态重分配权重计算 `implementation_depth`，避免零值处罚。
- **Per-Session DB Revision**：基于数据库 AI 表行特征生成 Stable Hash，防止无关 IDE UI 更新引发缓存颠簸。
- **跨机器缓存隔离**：对非 `local` 机器引入 `(source_machine, session_id)` 双重唯一键去重，并在路径中进行子目录物理隔离。
- **惰性 Placeholder 扫描**：首阶段仅极速解析项目路径，Orchestrator 过滤采样后按需调用 `ensure_parsed`，使扫描性能直升百倍。
- **Schema 升版**：升级 `CACHE_SCHEMA_VERSION` 至 `"1.2"`。

### 2. 上一版本：v0.4.0 (基于 Schema 1.1)
*奠定了 Agentic 协作成长的核心底座。*
- **三段式 LLM 诊断层**：Stage-1 规则过滤候选 -> Stage-2 LLM Grounded Synthesis 诊断 -> Stage-3 规则重排。
- **Agentic Evidence Graph**：提取任务意图、使用方法、上下文、执行路径、收口状态与人工干预六维图事实，序列化持久至 Sidecar JSON。
- **Action Contract Generator**：动态生成可落地的 Rule/Skill/Workflow 草稿契约。
- **纠偏成本趋势**：支持 `human_intervention_session_rate` 的跨快照对比（Improving/Worsening/Flat）。

---

## 修订记录

- **2026-06-06**：重构文档索引，纠正 v1.2 混淆为产品版本号的问题，规范为 **Product v0.4.2 / Schema 1.2**，补充缺失文件，链接全部转为绝对 `file://` 格式。
- **2026-06-04**：补充 Agentic 架构核心机制说明与阅读入口。
- **2026-05-25**：创建第一版设计索引。
