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

## Pull request checklist

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
