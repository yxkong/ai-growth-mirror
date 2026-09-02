---
title: AI Growth Mirror Docs Index
domain: growth_mirror
status: mirror
canonical_path: docs/README.md
updated_at: 2026-09-02
---

Chinese canonical docs index: [docs/README.md](../README.md)

# AI Growth Mirror Documentation Entry

> This directory is the design, specification, and configuration library for AI Growth Mirror. Through structured facts and the six-axis Agentic maturity model, it helps users quantify and improve their collaboration with AI.

## Core Canonical Index

- **[ARCHITECTURE_PRINCIPLES.md](../../design/ARCHITECTURE_PRINCIPLES.md)**: The sole architecture authority; defines layered design, resource ownership, and stability hard rules.
- **[design/README.md](./design/README.md)**: Design document index with a quick-reading guide.
- **[OPEN_SOURCE_GOVERNANCE.md](./config/OPEN_SOURCE_GOVERNANCE.md)**: Repository governance; redaction rules, license, and open-source boundaries.
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** (Chinese: [CONTRIBUTING.zh.md](../../CONTRIBUTING.zh.md)): Contribution guide covering dev environment setup, branching, and commit conventions.

## Reading Rules

1. **Architecture first**: Before changing any core code, align with **[ARCHITECTURE_PRINCIPLES.md](../../design/ARCHITECTURE_PRINCIPLES.md)**, especially the four R&D architecture hard rules in Section 14.
2. **Canonical sources**: Active Chinese contracts under `docs/design/` and `docs/config/` are canonical; `docs/**/bak/` is historical archive backup, not current execution authority.
3. **Checked mirrors**: English documents are derived mirrors with a `canonical_path`; conflicts are resolved only at the Chinese canonical owner.
4. **Bilingual parity**: Release or version bumps update canonical and mirror in the same change set, and automated metadata/version checks block drift.
