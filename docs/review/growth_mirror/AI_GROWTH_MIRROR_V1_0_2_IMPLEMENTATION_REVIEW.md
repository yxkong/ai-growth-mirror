---
title: AI Growth Mirror v1.0.2 实现多轮 Review
domain: growth_mirror
status: canonical
document_type: review
version: 1.0.0
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/v1.0.2-DESIGN.md
    role: reviewed_design
  - path: docs/design/ADR-v1.0.2-assessment-policy-and-root-task.md
    role: reviewed_decision
---

# AI Growth Mirror v1.0.2 实现多轮 Review

## 1. 范围与完成判据

- 范围：DDD 边界、评估 policy 2.0、六轴计算、快照可比性、解释投影、reader catalog、DeepSeek Harness、ZCode、项目技能与双语发布投影。
- 不在范围：发布、commit/push、浏览器人工验收、团队聚合、未知未来 reader schema。
- PASS：不存在开放 P0/P1；评分只有一个 owner/公式；真实本机 reader 只读冒烟通过；全量 unit/eval、编译、lock、build、diff 与 skill gate 通过。

## 2. Round 1 — DDD 与唯一真源

### Findings

1. `SessionRecord` 原持有 adapter/raw ref/cache materialization，领域对象依赖基础设施生命周期。
2. capability fallback 与 snapshot 权重形成第二公式/第二权重真源。
3. reader 注册、CLI choices 与 alias 分散，新增工具会漂移。

### 修复与复核

- 延迟物化移到 `infra/readers/base.py::DeferredSessionRecord` 与 infrastructure materializer；领域模型不再含 adapter/raw ref/placeholder。
- `assessment_policy.py` 独占 policy/version/轴权重/分量权重/等级；`assessment.py` 独占计算；capability 只投影，comparison 只 import owner。
- `infra/readers/catalog.py` 独占 adapter/alias/choices，CLI 与 orchestrator 消费该投影。
- 静态架构门禁覆盖上述三项。结果：**PASS**。

## 3. Round 2 — 指标因果、反刷分与学习解释

### Findings

1. missing 曾被 0/100 或 fallback 猜测；raw token/files/commit/tool/model/subagent 数量可抬分。
2. 委派成功与恢复成功借用全局 outcome，摩擦同时来自 raw/read 时会重复计数。
3. 无恢复机会也可获得恢复分；跨 policy/缺第六轴仍可能产生伪 delta。

### 修复与复核

- `MetricObservation` 显式携带 availability/evidence/denominator/confidence/reason；available 分量/轴动态归一并公开 coverage。
- 原始 usage 和生态数量退出评分；文件覆盖只在小区间饱和且有 invariance 用例；删除 bonus/floor/第二公式。
- 委派/恢复/澄清改为 opportunity-session 绑定；恢复 ID 取并集，outcome、纠偏、验证分别按同一机会集计算。
- 无机会轴不可用；跨 policy 或六轴 schema 不完整时不输出 axis delta。
- 报告/summary 输出 policy、coverage、components、reason codes 和缺失原因。结果：**PASS**。

## 4. Round 3 — Reader 契约、安全与性能

### Findings

1. 初始 DeepSeek fixture 与真实 v0 数据不一致：usage 实际在 `assistant/message`，model 在 `request/context`，human content 是 block list；空 seed 会污染样本。
2. child 的委派 prompt 不能冒充人类消息；packed chunks 不能重复计数。
3. ZCode 必须证明 `mode=ro`、required columns 完整、call ID 跨 session 不碰撞，并禁止 model-I/O fallback。

### 修复与复核

- DeepSeek Harness 采用 raw/Zstd 流式读取、header/version/seq gate、真实 human-source 过滤、root/child roll-up、assistant usage、model context、tool error、验证、chain、Goal/Todo 与空 seed skip；reasoning/compaction raw output 从不读取。
- ZCode 使用 SQLite URI `mode=ro` + `query_only`，冻结五表 required columns，按 `(session_id, call_id)` 关联，root 聚合一次；缺 schema fail closed，rollout 永不读取。
- 诊断只输出固定计数，不含正文/headers/SQL 参数。
- 本机只读冒烟：DeepSeek 13 个 physical session 归一为 2 个有效 root task、1 个空 seed skipped；ZCode 1 个 root task；两者解析、用户事实、usage 均可用，`corrupt/schema_mismatch/unreadable=0`。结果：**PASS**。

## 5. Round 4 — 用户可见闭环、趋势与技能

### Findings

1. 用户只看到分数时无法知道证据、缺口与下一期验证方式。
2. README/架构/路线图仍描述旧版本、旧工具数和旧 fallback，会形成文档漂移。
3. 项目技能缺新 policy/reader 路由且体积初检 151/150。

### 修复与复核

- 六轴投影增加 policy/coverage/component/reason；missing 明确 unavailable；训练闭环继续由现有 Action Contract 与下期 snapshot 回看承接。
- Product v1.0.2 / Cache Schema 1.0 同步到版本 owner、lock、双语 README、设计索引、路线图、SDD/ADR；英文保持 checked mirror。
- `ai-growth-mirror-dev` 增加评估/reader reference、触发与红线，合并重复命名规则后 size 150/150；entrypoint/structure/size 全通过；工作区 junction 可见新 reference。
- 官方趋势映射落到 Goal/Plan、Skill/Subagent、持久事件、验证与状态恢复，而非原始调用次数。结果：**PASS**。

## 6. Round 5 — 最终回归与发布判定

| 层级 | 命令/证据 | 结果 |
|---|---|---|
| static | 单一 AXIS_WEIGHTS owner、领域模型无 lazy infra state、catalog 派生测试 | PASS |
| contract | policy invariance、missing、opportunity binding、raw/Zstd、schema negative、privacy canary、六轴 snapshot gate | PASS |
| runtime-local | DeepSeek Harness + ZCode 本机只读冒烟 | PASS |
| regression | `uv run pytest tests/unit tests/evals -q` | PASS |
| build | `compileall`、`uv lock --check`、`uv build`、`git diff --check` | PASS |
| skill | entrypoints、structure、multi-domain size | PASS |
| browser | 本轮无交互 UI 行为变化；未做人工浏览器验收 | NOT_RUN |
| release | 未 commit、push、tag 或发布 | NOT_RUN |

开放 P0：**NONE**。开放 P1：**NONE**。发布状态不是本 Review 的授权范围，保持 **NOT_RUN**。
