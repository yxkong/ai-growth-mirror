---
title: Growth Mirror Design Index
domain: growth_mirror
status: mirror
canonical_path: docs/design/README.md
updated_at: 2026-09-02
---

Chinese design index: [docs/design/README.md](../../design/README.md)

# AI Growth Mirror Design Document Index

> This directory collects core architecture and detailed design documents for AI Growth Mirror.

## Checked Mirror Index

| Document | Status | Primary Use / Coverage |
|------|--------------|-------------------|
| **[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)** | **mirror - canonical in `docs/design/`** | System layering principles, metric weight logic, anti-jitter and lazy-parse stability hard rules. |
| **[AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](./AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)** | **mirror** | Personal report information architecture, copy forbidden-word boundaries, module data mapping (six-axis radar, Prompt coach, collaboration rhythm, etc.). |
| **[PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md)** | **mirror** | Product evolution roadmap; product version to cache Schema version mapping; technical and feature direction from v0.4.2 to v1.5.0. |
| **[v1.0.2-DESIGN.md](./v1.0.2-DESIGN.md)** | **mirror - current version design** | DDD boundaries, explainable assessment policy 2.0, root-task semantics, and DeepSeek Harness/ZCode ACLs. |
| **[ADR-v1.0.2-assessment-policy-and-root-task.md](./ADR-v1.0.2-assessment-policy-and-root-task.md)** | **mirror - accepted architecture decision** | Single scoring policy, missing evidence, root-task, and privacy fail-closed decisions. |
| **[v1.0.1-DESIGN.md](./v1.0.1-DESIGN.md)** | **mirror - historical version design** | Outbound LLM privacy, OpenCode snapshot parsing, atomic persistence, status/i18n, scoring calibration, and cross-platform release gates. |
| **[ADR-v1.0.1-trust-resilience.md](./ADR-v1.0.1-trust-resilience.md)** | **mirror - historical architecture decision** | Frozen decisions for privacy boundaries, content revisions, atomic writes, and snapshot layering. |
| **[v1.0.0-DESIGN.md](./v1.0.0-DESIGN.md)** | **mirror - historical version design** | Effective Task Contract, verification command keyword recognition, read-only reconnaissance exemption, version and PowerShell collaboration rules. |
| **[v0.8.0-DESIGN.md](./v0.8.0-DESIGN.md)** | **mirror - historical version design** | `collaboration_framing` four-dimensional structure, `goal_locking_speed` signal, and v0.8 scoring loop. |
| **[v0.7.0-DESIGN.md](./v0.7.0-DESIGN.md)** | **mirror - Agentic refactor design** | Six-axis Agentic maturity, `agentic_system` as a formal axis, recovery advancement correction. |
| **[v0.6.0-DESIGN.md](./v0.6.0-DESIGN.md)** | **mirror - training loop design** | Action Contract lookback, period-over-period delta, CLI status, and active clarification signals. |
| **[AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md](./AI_GROWTH_MIRROR_OUTPUT_ROOT_CAUSE_ANALYSIS.md)** | **mirror - supporting root cause analysis** | Why tools like AI Growth Mirror are needed; necessity of quantifying collaboration habits; Four-Evidence Method main line. |
| **[OPEN_SOURCE_GOVERNANCE.md](../config/OPEN_SOURCE_GOVERNANCE.md)** | **mirror - governance** | Open-source scope, local cache privacy rules, and code security redaction standards. |

> [!NOTE]
> Suggested reading order:
> **1. Root cause analysis** (product pain points and Four-Evidence Method) -> **2. Architecture principles** (dev layering and hard rules) -> **3. Detailed design** (report structure and copy) -> **4. Product roadmap** (evolution and roadmap)

---

## Core Evolution and Version Alignment

For R&D version control, the project strictly separates:
- **Product Version**: Follows SemVer; represents user-facing feature and interaction upgrades.
- **Cache Schema Version**: Evolves independently; controls local/remote serialized cache file format compatibility.

### 1. Current Version: v1.0.2 (Cache Schema 1.0)
*This release separates Session Observation, Growth Assessment, and Learning Loop through DDD and moves scoring semantics to versioned, explainable policy 2.0.*
- **Single truth owners**: assessment policy, calculation, reader catalog, and report orchestration each have one owner.
- **Trustworthy metrics**: missing evidence is unavailable with visible coverage; raw activity volume does not directly earn maturity.
- **Root-task semantics**: DeepSeek Harness and ZCode child evidence rolls up once to the user-visible task.
- **Privacy and observability**: unsupported schemas fail closed; ZCode model-I/O is forbidden as a fallback; diagnostics contain no transcript content.
- **Learning loop**: reports show score causes, gaps, and next verification actions; cross-policy snapshots do not emit false-precision deltas.

### 2. Recent Version Timeline
- **v1.0.2 / Schema 1.0**: DDD assessment policy 2.0, root-task aggregation, and DeepSeek Harness/ZCode readers.
- **v1.0.1 / Schema 1.0**: Trust and resilience hardening.
- **v1.0.0 / Schema 1.0**: Effective Task Contract, keyword verification recognition, read-only reconnaissance exemption, version and PowerShell collaboration rules.
- **v0.7.0 / Schema 1.4**: Six-axis Agentic maturity base, `agentic_system` formal axis, recovery advancement misjudgment fix.
- **v0.6.0 / Schema 1.3**: Training lookback, period-over-period delta, CLI `status`, active clarification signals.
- **v0.5.0 / Schema 1.2**: Zero-deploy single-file interactive report, Scroll Spy, radar interaction, and gap linkage.
- **v0.4.2 / Schema 1.2**: Missing-metric normalization, anti-cache jitter, multi-machine isolation, lazy Placeholder parsing.
- **v0.4.0 / Schema 1.1**: Agentic Evidence Graph, Action Contract Generator, and three-stage diagnosis base.

---

## Revision History

- **2026-09-02**: Implementation candidate **Product v1.0.2 / Cache Schema 1.0**; add DDD assessment boundaries, policy 2.0, root-task normalization, DeepSeek Harness/ZCode readers, and explainable evidence coverage.
- **2026-09-02**: Release candidate **Product v1.0.1 / Cache Schema 1.0**; add trust boundary, OpenCode/status correctness, atomic persistence, strict layering, scoring calibration, and cross-platform CI.
- **2026-06-09**: Release **Product v1.0.0 / Cache Schema 1.0**; add Effective Task Contract, work_focus LLM synthesis, evidence-based Prompt Coach, keyword verification recognition, read-only reconnaissance exemption, and version linkage.
- **2026-06-08**: Sync current version to **Product v0.8.0 / Cache Schema 1.4**; add v0.8/v0.7/v0.6 design entries and report loop notes.
- **2026-06-06**: Refactor doc index; fix v1.2 mistaken as product version; standardize to **Product v0.4.2 / Schema 1.2**; add missing files; convert links to absolute `file://` format.
- **2026-06-04**: Add Agentic architecture core mechanism notes and reading entry.
- **2026-05-25**: Create first design index.
