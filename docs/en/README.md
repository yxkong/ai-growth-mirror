---
title: AI Growth Mirror Docs Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-09
---

Chinese docs index: [docs/README.md](../../README.md)

# AI Growth Mirror Documentation Entry

> This directory is the design, specification, and configuration library for AI Growth Mirror. Through structured facts and the six-axis Agentic maturity model, it helps users quantify and improve their collaboration with AI.

## Core Canonical Index

- **[ARCHITECTURE_PRINCIPLES.md](../../design/ARCHITECTURE_PRINCIPLES.md)**: The sole architecture authority; defines layered design, resource ownership, and stability hard rules.
- **[design/README.md](./design/README.md)**: Design document index with a quick-reading guide.
- **[OPEN_SOURCE_GOVERNANCE.md](./config/OPEN_SOURCE_GOVERNANCE.md)**: Repository governance; redaction rules, license, and open-source boundaries.
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** (Chinese: [CONTRIBUTING.zh.md](../../CONTRIBUTING.zh.md)): Contribution guide covering dev environment setup, branching, and commit conventions.

## Reading Rules

1. **Architecture first**: Before changing any core code, align with **[ARCHITECTURE_PRINCIPLES.md](../../design/ARCHITECTURE_PRINCIPLES.md)**, especially the four R&D architecture hard rules in Section 14.
2. **Canonical sources**: Active canonical docs live under `docs/design/` and `docs/config/`; `docs/**/bak/` is historical archive backup, not current execution authority.
3. **Stay in sync**: Every feature iteration must keep formulas and interface contracts in docs aligned with implementation; doc-implementation drift is forbidden.
4. **Bilingual parity**: User-facing design docs exist under `docs/design/` (Chinese) and `docs/en/design/` (English). Release or version bumps must update **both** trees in the same change set.
