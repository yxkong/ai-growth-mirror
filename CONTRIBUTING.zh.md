# 参与贡献 AI Growth Mirror

English version: [CONTRIBUTING.md](./CONTRIBUTING.md)

感谢你有兴趣参与贡献。本项目是**本地优先**的个人成长报告工具；贡献应保护隐私，并保持个人报告主链简洁。

## 开始之前

1. 阅读 [`docs/design/ARCHITECTURE_PRINCIPLES.md`](docs/design/ARCHITECTURE_PRINCIPLES.md) — 分层与依赖方向不可妥协。
2. 阅读 [`docs/config/OPEN_SOURCE_GOVERNANCE.md`](docs/config/OPEN_SOURCE_GOVERNANCE.md) — 文档放置、提示词与禁止提交项。
3. 若改动报告组装，阅读架构文档第 12 节（反模式）；若已挂载项目技能，另读 `.claude/skills/ai-growth-mirror-dev/references/anti_patterns.md`。

## 开发环境

```bash
git clone <your-fork-url>
cd ai-growth-mirror
pip install -e ".[dev]"
```

可选：将 `config.example.yaml` 复制为 `config.yaml` 以配置本地 LLM Key。**切勿提交** `config.yaml`、`.env`、生成的 HTML/JSON 或会话导出文件。

## 运行测试

```bash
pytest tests/unit -q --tb=no
```

报告主链聚焦测试：

```bash
pytest tests/unit/test_personal_growth_report.py tests/unit/test_report_generation_service.py tests/unit/test_cli_generate.py -q --tb=no
```

## 架构规则（简表）

| 层 | 允许 | 禁止 |
|----|------|------|
| `domain/` | 纯模型、评分、枚举 | I/O、LLM、硬编码用户可见文案 |
| `application/` | 编排、视图 DTO、i18n 映射、HTML 渲染（`html_render.py`） | `html_render` 中做 I/O；`cli` 中重复流水线 |
| `infra/` | Readers、缓存、LLM、快照 | 业务枚举 |
| `cli.py` | 解析参数、调用 orchestrator、UX（进度） | 重复 collect/extract/aggregate 流水线 |

**报告生成唯一编排入口：** `application/orchestrator.generate_report_artifacts`。

## 欢迎的贡献类型

- `ai_growth_mirror/infra/readers/` 下新增 **工具 Adapter**
- 报告区块：`application/report_view.py` + `assets/templates/report.html.j2` + i18n YAML
- 带单元测试的 Bug 修复
- 使用**通用路径**的文档（勿写本机 `D:\...` 或个人项目名）

## Pull Request 规范

本仓库 PR 默认使用 [`.github/pull_request_template.md`](.github/pull_request_template.md)。目标是让 reviewer 在 2 分钟内看清 **背景、问题、方案、范围、验证**，而不是只看 commit 列表。

### 标题格式

```
type(scope): 一句话说明动机（why）
```

| type | 用途 |
|------|------|
| `feat` | 新能力 / 新区块 / 新 reader |
| `fix` | 修复错误行为、报告闭环、数据口径 |
| `refactor` | 不改外部行为的结构整理 |
| `docs` | 设计、README、贡献规范 |
| `test` | 仅补测试 |
| `chore` | 构建、依赖、CI |

`scope` 示例：`report`、`reader`、`cli`、`domain`、`i18n`、`docs`。

**好标题**：`fix(report): 工作焦点改由 SessionRead 语义真源驱动`  
**差标题**：`update report`、`fix bugs`、`v0.8 changes`

### 正文必填块

1. **背景** — 为什么现在要做
2. **问题定义** — 错在哪 / 缺什么（可验证）
3. **方案** — 真源、边界、取舍（不写实现流水账）
4. **改动范围** — 白名单模块；便于 scope review
5. **非目标** — 明确这次不做什么
6. **验证** — 贴命令 + 结果；报告类补充 HTML/summary 扫描点
7. **风险与回滚** — 用户可见变化、兼容性、revert 路径

### 范围与粒度

- **一个 PR 一个主目标**： reviewer 应能一句话概括「这个 PR 解决什么问题」。
- **避免「大杂烩 PR」**：不要把无关 reader 修复、文档整理、i18n 漂移塞进同一 PR，除非它们共享同一契约且无法拆分验证。
- **报告类改动**：必须说明真源文件（`report_view.py` / `summary_payload.py` / 模板 / i18n）和「无数据不渲染」是否受影响。

### 验证最低要求

```bash
pytest tests/unit -q --tb=no
```

报告主链改动额外跑：

```bash
pytest tests/unit/test_personal_growth_report.py \
  tests/unit/test_report_generation_service.py \
  tests/unit/test_cli_generate.py -q --tb=no
```

## PR 检查清单

- [ ] PR 标题符合 `type(scope): 动机` 格式
- [ ] PR 正文已填模板中的背景 / 问题 / 方案 / 范围 / 非目标 / 验证 / 风险
- [ ] 本地 `pytest tests/unit -q --tb=no` 通过
- [ ] diff 中无密钥、API Key 或个人报告产物
- [ ] `cli.py` 无重复流水线逻辑（见反模式文档）
- [ ] 用户可见文案在 `assets/i18n/`，不在 domain 硬编码
- [ ] 若改动 `docs/` 下 canonical 文档，更新 frontmatter `updated_at`

## 隐私与脱敏

- 生成的报告含个人会话元数据。勿在 Issue 或 PR 中附带真实 HTML/JSON。
- 分享样例输出时使用 `--redact`。
- 合成测试数据仅放在 `tests/fixtures/`。

## 代码风格

- 与周边模块约定一致（类型、命名、最小 diff）。
- Python 3.12+。
- 优先用最小改动解决问题。

## 提问

在 GitHub Issue 中说明：工具（Cursor/Codex 等）、session read 模式、预期与实际结果。省略本地路径与 API Key。
