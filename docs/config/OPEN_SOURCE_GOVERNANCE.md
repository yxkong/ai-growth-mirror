---
title: AI Growth Mirror Repository Governance
domain: growth_mirror
status: canonical
updated_at: 2026-05-29
---

# AI 成长镜 · 仓库治理说明

## 0. 运行环境

- Python **3.12+**（`pyproject.toml` `requires-python`、CI、README 一致）
- 开发验证：`pytest tests/unit -q --tb=no`

## 1. 文档放置

| 内容 | 目录 |
|------|------|
| 产品设计、ADR | `docs/design/` |
| 本文件、脱敏、配置说明 | `docs/config/` |
| 历史材料 | 不保留在当前活动工作区；`docs/**/bak/` 仅本地备份，**不是**发布真源 |

禁止：在 `ai_growth_mirror/` 包内写长期设计文档；禁止在活动区保留并行 plan / review 真源。

## 2. 文档 frontmatter

每份 canonical 文档必须包含：

```yaml
---
title: ...
domain: growth_mirror
status: canonical | draft | archived | superseded
updated_at: YYYY-MM-DD
---
```

## 3. 代码与提示词

| 类型 | 真源位置 |
|------|----------|
| LLM 提示词 | `ai_growth_mirror/assets/prompts/**` |
| HTML 模板 | `ai_growth_mirror/assets/templates/**` |
| UI 标签 YAML | `ai_growth_mirror/assets/i18n/**` |
| i18n 加载入口 | `ai_growth_mirror/infra/i18n/catalog.py` |
| Prompt / LLM DTO 与网关契约 | `ai_growth_mirror/domain/common/contracts.py`（`LlmGateway`、`PromptTemplateGateway`） |
| Personal report 编排 | `ai_growth_mirror/application/orchestrator.py` |
| Domain 模型与纯逻辑 | `ai_growth_mirror/domain/**` |
| Readers / extractors / LLM / cache / snapshots | `ai_growth_mirror/infra/**` |
| Report ViewModel 与 HTML 渲染 | `ai_growth_mirror/application/report_view.py` + `application/html_render.py`（禁止 I/O 与 LLM） |
| CLI 入口 | `ai_growth_mirror/cli.py`：`generate`（主链）、`compare`（快照对比）、`cache prune`（过期缓存清理） |
| 配置加载 | `./config.yaml` 优先，否则 `~/.ai-growth-mirror/config.yaml`（`config.resolve_config_path`） |
| 程序化入口 | `ai_growth_mirror/application/orchestrator.py`（`GenerateReportRequest` / `generate_report_artifacts`） |

当前主链：

- 主链：`collect → session_reads → aggregate → coaching → personal report → write`
- 新增 prompt 或 JSON 结构时，必须先定义明确 DTO / parser（`domain/**`），再进入 application 渲染层
- `html_render.py` 不得直接读取 YAML 或调用 LLM；i18n catalog 由 application 经 `label_catalogs.py` / `infra/i18n/catalog.py` 预加载后注入

### 3.1 Prompt 真源约束

- 当前发布真源只保留三组提示词：`session_read/`、`prompt_lens/`、`growth_coach/`，以及共享 partial `assets/prompts/_partials/output_language.md.j2`
- Prompt 的 JSON schema、taxonomy 与 parser 契约由 `domain/signals/payloads.py`、`domain/growth/coaching.py` 等 Python 真源约束；提示词正文允许重写，但不得绕开这些契约
- 面向仓库文档和提示词的文案必须使用中性产品口径，如 `evidence packet`、`reflection report`、`prompt lens`；禁止回流旧品牌、组织评价、绩效化或私域工作流包装语气
- `assets/prompts/**/bak/` 仅保存本地备份，不属于发布真源

### 3.1 非公开扩展（不提交）

组织版等内部-only 代码放在仓库根 **`private/org/`**（整棵 `private/` 已 `.gitignore`）。不得并入 `ai_growth_mirror/` 提交。约定见项目技能 `ai-growth-mirror-dev` → `references/private_overlay.md`。

## 4. 脱敏与禁止入库

- 真实用户 `ai_growth_mirror.json` / HTML 报告  
- `bak/compare/` 类快照目录（提取代码后删除）  
- ChatGPT / 内部对话导出  

脱敏样本放 `tests/fixtures/`。

## 5. 生成物

以下默认 **不提交**（`.gitignore`）：

- `ai-growth-mirror.html`、`ai-growth-mirror.json`、`ai-growth-mirror.summary.json`  
- `ai-growth-mirror-archive/`、`.ai-growth-mirror-runtime/`（含默认 `cache/`）、`source/`  
- `.cursor/`、`.vscode/` 等 IDE / Agent 本地目录  
- 任何本地运行产物与 IDE / Agent 缓存（见 §5）  

### 5.1 Usage 指标覆盖（文档层说明）

Token / 成本 / 缓存相关指标**只统计 reader 能解析 usage 明细的会话**；无 usage 字段的工具仍参与成长评分，但不进入 Token / 成本 / 缓存汇总。报告对缺失项显示 `--`，`memory` 当前未采集须显式标注。实现边界见 `docs/design/ARCHITECTURE_PRINCIPLES.md` 的「Usage / Asset 边界」一节。

## 6. 备份

改文档 / 技能 / 大文件前使用 hub `backup-file` 脚本，禁止手工 `cp` 到随意 dated 目录。

## 6.1 仓库根文件

| 文件 | 用途 |
|------|------|
| `LICENSE` | MIT 许可证全文 |
| `CONTRIBUTING.md` | PR 流程、分层约束、隐私与验证命令 |

## 7. 真源索引

见 `docs/design/README.md`、`docs/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md` 与 `docs/design/ARCHITECTURE_PRINCIPLES.md`。
