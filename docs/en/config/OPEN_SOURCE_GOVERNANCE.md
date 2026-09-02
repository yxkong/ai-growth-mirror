---
title: AI Growth Mirror Repository Governance
domain: growth_mirror
status: mirror
canonical_path: docs/config/OPEN_SOURCE_GOVERNANCE.md
updated_at: 2026-09-02
---

Chinese version: [OPEN_SOURCE_GOVERNANCE.md](../../config/OPEN_SOURCE_GOVERNANCE.md)

# AI Growth Mirror - Repository Governance

## 0. Runtime Environment

- Python **3.12+** (aligned with `pyproject.toml` `requires-python`, CI, README)
- Dev verification: `pytest tests/unit -q --tb=no`

## 1. Document Placement

| Content | Directory |
|------|------|
| Product design, ADR | `docs/design/` |
| This file, redaction, config notes | `docs/config/` |
| Historical material | Not kept in active workspace; `docs/**/bak/` is local backup only, **not** release authority |

Forbidden: long-term design docs inside `ai_growth_mirror/` package; parallel plan/review authorities in active areas.

## 2. Document Frontmatter

Every Chinese canonical document must include:

```yaml
---
title: ...
domain: growth_mirror
status: canonical | draft | archived | superseded
updated_at: YYYY-MM-DD
---
```

English translations are not a second authority. They use `status: mirror` and a repository-relative `canonical_path` that points to the Chinese owner; automated gates compare version and approval metadata.

## 3. Code and Prompts

| Type | Canonical Location |
|------|----------|
| LLM prompts | `ai_growth_mirror/assets/prompts/**` |
| HTML templates | `ai_growth_mirror/assets/templates/**` |
| UI label YAML | `ai_growth_mirror/assets/i18n/**` |
| i18n load entry | `ai_growth_mirror/infra/i18n/catalog.py` |
| Prompt / LLM DTO and gateway contracts | `ai_growth_mirror/domain/common/contracts.py` (`LlmGateway`, `PromptTemplateGateway`) |
| Personal report orchestration | `ai_growth_mirror/application/orchestrator.py` |
| Domain models and pure logic | `ai_growth_mirror/domain/**` |
| Readers / extractors / LLM / cache / snapshots | `ai_growth_mirror/infra/**` |
| Report ViewModel and HTML render | `ai_growth_mirror/application/report_view.py` + `application/html_render.py` (no I/O or LLM) |
| CLI entry | `ai_growth_mirror/cli.py`: `generate` (main chain), `compare` (snapshot compare), `cache prune` (expired cache cleanup) |
| Config load | `./config.yaml` first, else `~/.ai-growth-mirror/config.yaml` (`config.resolve_config_path`) |
| Programmatic entry | `ai_growth_mirror/application/orchestrator.py` (`GenerateReportRequest` / `generate_report_artifacts`) |

Current main chain:

- Main chain: `collect -> session_reads -> aggregate -> coaching -> personal report -> write`
- New prompts or JSON structures must define explicit DTO / parser (`domain/**`) before application render layer
- `html_render.py` must not read YAML or call LLM directly; i18n catalog is preloaded by application via `label_catalogs.py` / `infra/i18n/catalog.py`

### 3.1 Prompt Canonical Constraints

- Release authority keeps three prompt groups: `session_read/`, `prompt_lens/`, `growth_coach/`, plus shared partial `assets/prompts/_partials/output_language.md.j2`
- Prompt JSON schema, taxonomy, and parser contracts are constrained by Python authority in `domain/signals/payloads.py`, `domain/growth/coaching.py`, etc.; prompt body may be rewritten but must not bypass these contracts
- Docs and prompts for the public repo must use neutral product tone such as `evidence packet`, `reflection report`, `prompt lens`; forbid old brand, org evaluation, performance, or private workflow packaging tone
- `assets/prompts/**/bak/` is local backup only, not release authority

### 3.1 Non-Public Extensions (not committed)

Org edition and other internal-only code lives at repo root **`private/org/` (entire `private/` is `.gitignore`). Must not merge into `ai_growth_mirror/` for commit. See project skill `ai-growth-mirror-dev` -> `references/private_overlay.md`.

## 4. Redaction and Forbidden Commits

- Real user `ai_growth_mirror.json` / HTML reports
- `bak/compare/` snapshot directories (delete after code extraction)
- ChatGPT / internal conversation exports

Redacted samples go in `tests/fixtures/`.

## 5. Generated Artifacts

The following are **not committed** by default (`.gitignore`):

- `ai-growth-mirror.html`, `ai-growth-mirror.json`, `ai-growth-mirror.summary.json`
- `ai-growth-mirror-archive/`, `.ai-growth-mirror-runtime/` (includes default `cache/`), `source/`
- `.cursor/`, `.vscode/`, and other IDE / Agent local directories
- Any local run artifacts and IDE / Agent cache (see Section 5)

### 5.1 Usage Metric Coverage (documentation layer)

Token / cost / cache metrics **only count sessions where readers can parse usage detail**; tools without usage fields still participate in growth scoring but not Token / cost / cache aggregation. Report shows `--` for missing items; `memory` is not collected and must be explicitly labeled. Implementation boundary: see `docs/design/ARCHITECTURE_PRINCIPLES.md` "Usage / Asset Boundary" section.

## 6. Backup

Before editing docs / skills / large files, use hub `backup-file` script; do not manually `cp` to arbitrary dated directories.

## 6.1 Repo Root Files

| File | Purpose |
|------|------|
| `LICENSE` | Full MIT license text |
| `CONTRIBUTING.md` | PR flow, layering constraints, privacy and verification commands |

## 7. Canonical Index

See `docs/design/README.md`, `docs/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md`, and `docs/design/ARCHITECTURE_PRINCIPLES.md`.
