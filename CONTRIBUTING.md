# Contributing to AI Growth Mirror

Thank you for your interest in contributing. This project is a **local-first** personal growth report tool; contributions should preserve privacy and keep the personal report chain simple.

## Before you start

1. Read [`docs/design/ARCHITECTURE_PRINCIPLES.md`](docs/design/ARCHITECTURE_PRINCIPLES.md) — layering and dependency direction are non-negotiable.
2. Read [`docs/config/OPEN_SOURCE_GOVERNANCE.md`](docs/config/OPEN_SOURCE_GOVERNANCE.md) — docs placement, prompts, and what must not be committed.
3. For report assembly changes, read ARCHITECTURE §12（反模式）; if the project skill is mounted, also read `.claude/skills/ai-growth-mirror-dev/references/anti_patterns.md`.

## Development setup

```bash
git clone <your-fork-url>
cd ai-growth-mirror
pip install -e ".[dev]"
```

Optional: copy `config.example.yaml` to `config.yaml` for local LLM keys. **Never commit** `config.yaml`, `.env`, generated HTML/JSON, or session exports.

## Running tests

```bash
pytest tests/unit -q --tb=no
```

Focused report pipeline:

```bash
pytest tests/unit/test_personal_growth_report.py tests/unit/test_report_generation_service.py tests/unit/test_cli_generate.py -q --tb=no
```

## Architecture rules (short)

| Layer | May do | Must not |
|-------|--------|----------|
| `domain/` | Pure models, scoring, enums | I/O, LLM, user-facing copy hardcoding |
| `application/` | Orchestration, view DTOs, i18n mapping, HTML render (`html_render.py`) | I/O in html_render; duplicate pipeline in cli |
| `infra/` | Readers, cache, LLM, snapshots | Business enums |
| `cli.py` | Parse args, call orchestrator, UX (progress) | Duplicate collect/extract/aggregate pipeline |

**Single orchestration entry for report generation:** `application/orchestrator.generate_report_artifacts`.

## What to contribute

- New **tool adapters** under `ai_growth_mirror/infra/readers/`
- Report sections: `application/report_view.py` + `assets/templates/report.html.j2` + i18n YAML
- Bug fixes with unit tests
- Docs that use **generic paths** (no machine-specific `D:\...` or personal project names)

## Pull request 规范

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

## Pull request checklist

- [ ] PR 标题符合 `type(scope): 动机` 格式
- [ ] PR 正文已填模板中的背景 / 问题 / 方案 / 范围 / 非目标 / 验证 / 风险
- [ ] `pytest tests/unit -q --tb=no` passes locally
- [ ] No secrets, API keys, or personal report artifacts in the diff
- [ ] No duplicate pipeline logic in `cli.py` (see anti-pattern doc)
- [ ] User-facing strings go in `assets/i18n/`, not hardcoded in domain
- [ ] If you change canonical docs under `docs/`, update frontmatter `updated_at`

## Privacy and redaction

- Generated reports contain personal session metadata. Do not attach real HTML/JSON to issues or PRs.
- Use `--redact` when sharing sample output.
- Put synthetic fixtures in `tests/fixtures/` only.

## Code style

- Match surrounding module conventions (types, naming, minimal diff).
- Python 3.12+.
- Prefer the smallest change that solves the problem.

## Questions

Open a GitHub issue with context: tool (Cursor/Codex/etc.), session read mode, and what you expected vs. what happened. Omit local paths and API keys.
