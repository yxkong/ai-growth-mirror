---
title: Growth Mirror Design Index
domain: growth_mirror
status: canonical
updated_at: 2026-09-02
---

# AI Growth Mirror 设计文档索引

English design index: [README.md](../en/design/README.md)

> 本目录收录了 AI 成长镜（AI Growth Mirror）的核心架构与详细设计方案。

## 设计真源列表

| 文档 | 状态 (Status) | 主要用途 / 覆盖领域 |
|------|--------------|-------------------|
| **[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)** | **canonical · 架构真源** | 定义系统分层原则、指标权重逻辑、防颠簸与惰性解析等硬性稳定性规范。 |
| **[AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)** | **canonical · 详细设计** | 个人版报告的信息架构、文案禁用词边界、各模块数据映射（包含六轴雷达、Prompt教练与协作节奏等）。 |
| **[PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md)** | **canonical · 产品规划** | 产品的演进路线图，明确产品版本与缓存 Schema 版本的映射关系，定义 v0.4.2 到 v1.5.0 的技术与功能走向。 |
| **[v1.0.2-DESIGN.md](./v1.0.2-DESIGN.md)** | **canonical · 当前版本设计** | 定义 DDD 边界、可解释评估 policy 2.0、根任务口径与 DeepSeek Harness/ZCode ACL。 |
| **[ADR-v1.0.2-assessment-policy-and-root-task.md](./ADR-v1.0.2-assessment-policy-and-root-task.md)** | **accepted · 架构决策** | 冻结单一评分政策、缺失证据、根任务和隐私拒绝策略。 |
| **[v1.0.1-DESIGN.md](./v1.0.1-DESIGN.md)** | **canonical · 历史版本设计** | 定义 LLM 出站隐私边界、OpenCode 快照解析、原子持久化、status/i18n、评分校准与跨平台发布门。 |
| **[ADR-v1.0.1-trust-resilience.md](./ADR-v1.0.1-trust-resilience.md)** | **accepted · 历史架构决策** | 冻结隐私边界、内容 revision、原子写与 snapshot 分层的关键取舍。 |
| **[v1.0.0-DESIGN.md](./v1.0.0-DESIGN.md)** | **canonical · 历史版本设计** | 定义 Effective Task Contract、验证命令关键词识别、只读侦察豁免与版本/PowerShell 协作规则。 |
| **[v0.8.0-DESIGN.md](./v0.8.0-DESIGN.md)** | **canonical · 历史版本设计** | 定义 `collaboration_framing` 四维结构、`goal_locking_speed` 信号与 v0.8 评分闭环。 |
| **[v0.7.0-DESIGN.md](./v0.7.0-DESIGN.md)** | **canonical · Agentic 重构设计** | 定义六轴 Agentic 成熟度、`agentic_system` 正式轴与恢复推进修正。 |
| **[v0.6.0-DESIGN.md](./v0.6.0-DESIGN.md)** | **canonical · 训练闭环设计** | 定义 Action Contract 回看、环比 delta、CLI status 与主动澄清信号。 |
| **[AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](./AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md)** | **supporting · 根因分析** | 深度阐述为何需要 AI 成长镜这类工具，剖析用户协作习惯量化的必要性及方法论主线（四证法）。 |
| **[OPEN_SOURCE_GOVERNANCE.md](../config/OPEN_SOURCE_GOVERNANCE.md)** | **supporting · 治理说明** | 规范项目开源范围、本地缓存隐私保护规则以及代码安全敏感信息脱敏标准。 |

英文对照版见 [README.md](../en/design/README.md) 中的受检镜像索引；各英文文档以 `canonical_path` 指向本目录 owner，并保留互链。

> [!NOTE]
> 建议阅读顺序：  
> **1. 根因分析** (了解产品痛点与四证法) → **2. 架构总纲** (对齐开发分层与硬性原则) → **3. 详细设计** (对齐报告结构与文案) → **4. 产品规划** (理解后续演进与路线)

---

## 核心演进历程与版本对齐

为规范研发版本控制，项目严格区分为：
- **产品版本 (Product Version)**：遵循 SemVer 语义化规范，代表用户端的功能及交互升级。
- **缓存协议版本 (Cache Schema Version)**：独立演进，用于控制本地/远程序列化缓存文件的格式兼容性。

### 1. 当前版本：v1.0.2 (基于 Cache Schema 1.0)
*当前版本以 DDD 收敛 Session Observation、Growth Assessment 与 Learning Loop，并将评分语义升级为受版本控制的可解释 policy 2.0。*
- **单一真源**：评分政策、计算、reader catalog 和报告编排分别只有一个 owner，消费方只投影。
- **指标可信**：缺失证据不可用并显示 coverage；原始 token/files/commit/tool/model/subagent 数量不直接奖励成熟度。
- **根任务口径**：DeepSeek Harness、ZCode 子会话证据向用户可见根任务汇总一次，防止重复计分。
- **隐私与可观测**：外部 schema 不支持时 fail closed；ZCode 不回退读取 model-I/O，reader 仅输出结构化诊断。
- **学习闭环**：报告解释分数、证据、缺口和下期验证动作；跨 policy 快照不产生伪精确 delta。

### 2. 近期版本脉络
- **v1.0.2 / Schema 1.0**：DDD 可解释评估 policy 2.0、根任务聚合、DeepSeek Harness/ZCode reader。
- **v1.0.1 / Schema 1.0**：可信与韧性加固。
- **v1.0.0 / Schema 1.0**：Effective Task Contract、关键词验证识别、只读侦察豁免、版本与 PowerShell 协作规则。
- **v0.7.0 / Schema 1.4**：六轴 Agentic 成熟度底盘、`agentic_system` 正式轴、恢复推进误判修正。
- **v0.6.0 / Schema 1.3**：训练回看、环比 delta、CLI `status` 与主动澄清信号。
- **v0.5.0 / Schema 1.2**：免部署单文件交互式报告、Scroll Spy、雷达交互和短板联动。
- **v0.4.2 / Schema 1.2**：缺失型指标归一化、防缓存颠簸、多机器隔离与惰性 Placeholder 解析。
- **v0.4.0 / Schema 1.1**：Agentic Evidence Graph、Action Contract Generator 与三段式诊断底座。

---

## 修订记录

- **2026-09-02**：实现候选 **Product v1.0.2 / Cache Schema 1.0**，增加 DDD 评估边界、policy 2.0、根任务归一、DeepSeek Harness/ZCode reader 与可解释证据覆盖。
- **2026-09-02**：发布候选 **Product v1.0.1 / Cache Schema 1.0**，增加可信边界、OpenCode/status 正确性、原子持久化、分层硬门、评分校准与跨平台 CI。
- **2026-06-09**：发布 **Product v1.0.0 / Cache Schema 1.0**，补齐 Effective Task Contract、work_focus LLM 综合、Prompt Coach 证据化、关键词验证识别、只读侦察豁免与版本联动。
- **2026-06-08**：同步当前版本到 **Product v0.8.0 / Cache Schema 1.4**，补齐 v0.8/v0.7/v0.6 设计入口与报告闭环说明。
- **2026-06-06**：重构文档索引，纠正 v1.2 混淆为产品版本号的问题，规范为 **Product v0.4.2 / Schema 1.2**，补充缺失文件，链接全部转为绝对 `file://` 格式。
- **2026-06-04**：补充 Agentic 架构核心机制说明与阅读入口。
- **2026-05-25**：创建第一版设计索引。
