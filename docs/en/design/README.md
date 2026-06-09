---
title: Growth Mirror Design Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-09
---

Chinese design index: [docs/design/README.md](../../design/README.md)

# AI Growth Mirror Design Document Index

> This directory collects core architecture and detailed design documents for AI Growth Mirror.

## Design Canonical List

| Document | Status | Primary Use / Coverage |
|------|--------------|-------------------|
| **[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)** | **canonical - architecture authority** | System layering principles, metric weight logic, anti-jitter and lazy-parse stability hard rules. |
| **[AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)** | **canonical - detailed design** | Personal report information architecture, copy forbidden-word boundaries, module data mapping (six-axis radar, Prompt coach, collaboration rhythm, etc.). |
| **[PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md)** | **canonical - product roadmap** | Product evolution roadmap; product version to cache Schema version mapping; technical and feature direction from v0.4.2 to v1.5.0. |
| **[v1.0.0-DESIGN.md](./v1.0.0-DESIGN.md)** | **canonical - current version design** | Effective Task Contract, verification command keyword recognition, read-only reconnaissance exemption, version and PowerShell collaboration rules. |
| **[v0.8.0-DESIGN.md](./v0.8.0-DESIGN.md)** | **canonical - historical version design** | `collaboration_framing` four-dimensional structure, `goal_locking_speed` signal, and v0.8 scoring loop. |
| **[v0.7.0-DESIGN.md](./v0.7.0-DESIGN.md)** | **canonical - Agentic refactor design** | Six-axis Agentic maturity, `agentic_system` as a formal axis, recovery advancement correction. |
| **[v0.6.0-DESIGN.md](./v0.6.0-DESIGN.md)** | **canonical - training loop design** | Action Contract lookback, period-over-period delta, CLI status, and active clarification signals. |
| **[AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](./AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md)** | **supporting - root cause analysis** | Why tools like AI Growth Mirror are needed; necessity of quantifying collaboration habits; Four-Evidence Method main line. |
| **[OPEN_SOURCE_GOVERNANCE.md](../config/OPEN_SOURCE_GOVERNANCE.md)** | **supporting - governance** | Open-source scope, local cache privacy rules, and code security redaction standards. |

> [!NOTE]
> Suggested reading order:
> **1. Root cause analysis** (product pain points and Four-Evidence Method) -> **2. Architecture principles** (dev layering and hard rules) -> **3. Detailed design** (report structure and copy) -> **4. Product roadmap** (evolution and roadmap)

---

## Core Evolution and Version Alignment

For R&D version control, the project strictly separates:
- **Product Version**: Follows SemVer; represents user-facing feature and interaction upgrades.
- **Cache Schema Version**: Evolves independently; controls local/remote serialized cache file format compatibility.

### 1. Current Version: v1.0.0 (Cache Schema 1.0)
*Current version completes general Agentic report calibration: from "hand-written acceptance on first turn" to "whether an Effective Task Contract exists and is fulfilled by the Agent".*
- **Effective Task Contract**: Distinguishes user-explicit contracts, Skill/Rule/Workflow contracts, Agent-derived contracts, and post-hoc correction contracts.
- **Verification command recognition**: From full command enumeration to keyword/script-suffix matching; covers build, compile, test, and common Windows scripts.
- **Goal locking speed calibration**: When all turns before first write are read-only reconnaissance, no ordinary delay penalty on `goal_locking_speed`.
- **Version strategy reset**: Product version and cache schema start from `1.0`; unchanged schema uses `v1.0.x` patch iteration.
- **Report loop**: Main report, Evidence Sidecar, `*.summary.json`, share card, and snapshot archive all from the same application orchestration chain.
- **What you are doing**: `work_focus/` LLM cross-session theme synthesis; tool/language/goal mix stats remain rule-based.
- **Evidence-based content**: Prompt Coach and coaching prompts drop canned training templates; personalized conclusions are LLM-generated from packet evidence.

### 2. Recent Version Timeline
- **v1.0.0 / Schema 1.0**: Effective Task Contract, keyword verification recognition, read-only reconnaissance exemption, version and PowerShell collaboration rules.
- **v0.7.0 / Schema 1.4**: Six-axis Agentic maturity base, `agentic_system` formal axis, recovery advancement misjudgment fix.
- **v0.6.0 / Schema 1.3**: Training lookback, period-over-period delta, CLI `status`, active clarification signals.
- **v0.5.0 / Schema 1.2**: Zero-deploy single-file interactive report, Scroll Spy, radar interaction, and gap linkage.
- **v0.4.2 / Schema 1.2**: Missing-metric normalization, anti-cache jitter, multi-machine isolation, lazy Placeholder parsing.
- **v0.4.0 / Schema 1.1**: Agentic Evidence Graph, Action Contract Generator, and three-stage diagnosis base.

---

## Revision History

- **2026-06-09**: Release **Product v1.0.0 / Cache Schema 1.0**; add Effective Task Contract, work_focus LLM synthesis, evidence-based Prompt Coach, keyword verification recognition, read-only reconnaissance exemption, and version linkage.
- **2026-06-08**: Sync current version to **Product v0.8.0 / Cache Schema 1.4**; add v0.8/v0.7/v0.6 design entries and report loop notes.
- **2026-06-06**: Refactor doc index; fix v1.2 mistaken as product version; standardize to **Product v0.4.2 / Schema 1.2**; add missing files; convert links to absolute `file://` format.
- **2026-06-04**: Add Agentic architecture core mechanism notes and reading entry.
- **2026-05-25**: Create first design index.
