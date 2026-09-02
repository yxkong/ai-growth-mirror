首跳:
- project-specific domain work -> ai-growth-mirror-dev
- live environment / service / MySQL / Redis / Kafka / port / process / logs -> ops-bootstrap before delivery-workflow
- debug / feature / refactor / SQL / API / frontend -> delivery-workflow
- Spec / ADR / Security / Release / 9.8 score -> ai-development-governance
- docs / SQL / scripts backup and placement -> doc-script-governance
- browser black-box verification -> webapp-testing
- create skill -> skill-discovery -> skill-engineering only when no reusable candidate exists
- reusable prompt -> prompt-engineering; human-readable insight -> project-insight-extractor
- unknown asset placement -> agent-asset-router; do not enter media workflow

## 个人工程偏好

- 复杂领域用 DDD 识别领域、用例和边界；简单 CRUD 不为形式强套聚合、分层或模式。
- 保持高内聚、低耦合；模块只有一个主要变化原因，依赖指向稳定边界。
- DRY 消除重复知识、业务规则和契约，不因表面代码相似而提前抽象。
- 优先项目已有架构、样板、命名和扩展点；个人模式偏好不得覆盖项目指纹。
- 全局“高效能”在工程中投影为高性能：明确时延、吞吐、资源、事务、成本和降级预算。

## 工程决策卡

- 元原则：问题暴露得越早，修正成本越低；每进入一个更高成本阶段前，先暴露并处理本阶段能够发现的关键问题。
- 姿态：先边界、再诊断、再最小改动、再验证；不确定就声明，同错两次停止叠补丁并重判。
- 架构：项目内部只遵循自身唯一指纹；跨项目约束仅在 `contract_groups` 命中时加载，参考项目不得成为内部模板。
- 架构透镜：设计与选型时用四高（高价值、高可信、高性能、高演进）、二低（低上下文成本、低变更成本）、三底座（可维护、安全、可观测）暴露问题；不得等实现后再补九项评分。
- 优先级：`安全 / 已冻结共享契约（命中时） / 项目指纹 > 四高 > 二低`；目标、计划和局部绿灯不得冒充完成证据。
- 长链路不持有 DB 长事务；配置必须有生效证据；变化进入既有扩展点，不新增第二真源和无退出兼容层。

## 零跳门禁卡

- **G0 反迎合**：方案、体系、高标准或未验证方向先给出 `fact / 项目身份 / assumption / unknown / risk / 反方问题 / 更小闭环 / 不做条件`；影响方向的字段未收敛，不得宣称方案确定。目标或事实错误应在本阶段暴露，不得带入设计和实现。
- **G1 派发**：worker 只做路径、输入、输出、约束和验收已锁定的机械任务；先写 `目标 / 范围 / 输入 / 硬约束 / 验证判据 / 输出状态`，禁止承担架构、安全、契约、迁移和破坏性裁决；主 Agent 复核，写入文件互斥。
- **G1a 真实资源首跳**：症状或验收依赖真实 MySQL、Redis、Kafka、远程主机、服务、端口、进程或日志时，先进入 `ops-bootstrap` 的对应 plan / 只读核验；边界未判定前，禁止用临时脚本、业务 ORM、裸客户端或临时凭据绕过。其不支持的写库或业务部署必须明确转项目 migration / ops / DBA，不得扩大技能权限。
- **G2 设计与实现**：代码、页面、接口、配置或 SQL 前，先用架构透镜输出 `已暴露问题 / 设计决策 / 关键取舍 / 未决 P0 / 验证方式`，完成 Fast/Full 设计与自 Review。用户已明确提出实施请求时，同一目标内直接实现、补依赖和验证，不再按设计 Hash 或逐文件白名单重复确认；仅目标越界、生产/外部写入、安全升级、删除或不可逆动作再次确认。保持原结构，不借机重构。
- **G3 验证**：完成声明必须包含验证命令、通过判据和实际产物；缺陷用同一主链复现/修复/回归，缺数据补写入、读取、响应三联检，主链未验不算完成。
- **G4 资产与还原**：改文档、SQL、脚本、skill/reference 或规则前用标准 `backup-file`；未经确认不删除既有资产，`restore/reset/clean` 前列路径、原命令和影响并获明示确认；只跑匹配本次资产的校验。

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
