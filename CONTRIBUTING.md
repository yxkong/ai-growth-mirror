# Contributing to AI Growth Mirror

Chinese version: [CONTRIBUTING.zh.md](./CONTRIBUTING.zh.md)

Thank you for your interest in contributing. This project is a **local-first** personal growth report tool; contributions should preserve privacy and keep the personal report chain simple.

## Before you start

1. Read [`docs/en/design/ARCHITECTURE_PRINCIPLES.md`](docs/en/design/ARCHITECTURE_PRINCIPLES.md) — layering and dependency direction are non-negotiable.
2. Read [`docs/en/config/OPEN_SOURCE_GOVERNANCE.md`](docs/en/config/OPEN_SOURCE_GOVERNANCE.md) — docs placement, prompts, and what must not be committed.
3. For report assembly changes, read ARCHITECTURE Section 12 (anti-patterns); if the project skill is mounted, also read `.claude/skills/ai-growth-mirror-dev/references/anti_patterns.md`.

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

## Pull request guidelines

This repo uses [`.github/pull_request_template.md`](.github/pull_request_template.md). The goal is for reviewers to see **context, problem, approach, scope, and verification** within about two minutes — not just a commit list.

### Title format

```
type(scope): one-line motivation (why)
```

| type | Use for |
|------|---------|
| `feat` | New capability / section / reader |
| `fix` | Incorrect behavior, report loop, data semantics |
| `refactor` | Structure cleanup without external behavior change |
| `docs` | Design, README, contribution docs |
| `test` | Tests only |
| `chore` | Build, dependencies, CI |

Example `scope`: `report`, `reader`, `cli`, `domain`, `i18n`, `docs`.

**Good**: `fix(report): drive work focus from SessionRead semantic source`  
**Bad**: `update report`, `fix bugs`, `v0.8 changes`

### Required PR body sections

1. **Context** — why now
2. **Problem** — what is wrong or missing (verifiable)
3. **Approach** — source of truth, boundaries, trade-offs (not an implementation diary)
4. **Scope** — allowlisted modules for review
5. **Non-goals** — what this PR explicitly does not do
6. **Verification** — commands + results; for report changes, HTML/summary scan points
7. **Risk and rollback** — user-visible changes, compatibility, revert path

### Scope and granularity

- **One PR, one main goal**: a reviewer should summarize the PR in one sentence.
- **Avoid kitchen-sink PRs**: do not mix unrelated reader fixes, doc churn, or i18n drift unless they share one contract and cannot be validated separately.
- **Report changes**: state truth-source files (`report_view.py` / `summary_payload.py` / templates / i18n) and whether "no data, no render" is affected.

### Minimum verification

```bash
pytest tests/unit -q --tb=no
```

For report main-chain changes, also run:

```bash
pytest tests/unit/test_personal_growth_report.py \
  tests/unit/test_report_generation_service.py \
  tests/unit/test_cli_generate.py -q --tb=no
```

## Pull request checklist

- [ ] PR title follows `type(scope): motivation`
- [ ] PR body fills context / problem / approach / scope / non-goals / verification / risk
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
