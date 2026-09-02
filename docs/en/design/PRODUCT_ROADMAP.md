---
title: AI Growth Mirror Product Roadmap
domain: growth_mirror
status: mirror
canonical_path: docs/design/PRODUCT_ROADMAP.md
updated_at: 2026-09-02
---

Chinese canonical version: [PRODUCT_ROADMAP.md](../../design/PRODUCT_ROADMAP.md)

# AI Growth Mirror - Product Roadmap

> This document defines AI Growth Mirror core positioning, current stage, and medium/long-term product evolution roadmap.

---

## 1. Product Positioning and Core Value

**One-line definition**: Help AI coding users see and improve collaboration blind spots, assess **Agentic operating maturity**, and provide executable growth training plans.

> **Core positioning (v0.7+ explicit)**: AI Growth Mirror is not a Prompt scorer but an **Agentic operating maturity assessment system**. It does not score "how complete your Prompt is" but "whether you can turn AI into a stable, reusable productivity system."

* **Diagnosis**: Where is my collaboration weak? (From Prompt completeness to full Agentic systemization chain)
* **Training**: How to improve? (2 clear, actionable two-week training plans and Action Contracts per generate)
* **Tracking**: Am I improving? (Auto 30-day growth trajectory, compare analysis, human correction cost trends)

**Six product design principles**:
1. **Diagnosis before score**: Users care most about "how to improve," not abstract 65 vs 70.
2. **Actionable before comprehensive**: Only 2 core training points per run; avoid information overload.
3. **Honest disclosure**: Clear confidence boundaries; weaken proxy analysis; do not fake LLM depth.
4. **Developer aesthetic**: High information density; no flashy halos; refined, compact data presentation.
5. **Data sovereignty**: All data parsed locally; no upload to centralized servers; privacy preserved.
6. **Incremental evolution**: Each core version solves 1-2 collaboration experience gaps.

---

## 2. Version Management System

Product version line follows cache Schema for stable iteration:

* **Product Version**: SemVer. `MAJOR.MINOR` aligns with cache Schema, e.g. `CACHE_SCHEMA_VERSION=1.0` -> `v1.0.x`.
* **Cache Schema Version**: Compatibility of `SessionRecord` / `SessionRead` / `CoreEvidence` serialization in cache. Schema upgrades only on protocol change; product line upgrades in sync.
* **Patch strategy**: Unchanged schema -> patch only, e.g. `v1.0.1`, `v1.0.2`; schema change -> new `vX.Y.0`.
* **Linkage requirement**: Version bumps must sync `pyproject.toml`, `ai_growth_mirror/__init__.py`, `uv.lock`, `README.md`, `docs/design/README.md`, this roadmap, and current design docs.

| Product Version | Cache Schema | Core Focus | Status |
|----------------------------|-----------------|-----------|------|
| **v0.4.0** | 1.1 | Agentic core diagnosis architecture and evidence graph | Released |
| **v0.4.2** | 1.2 | Missing-metric normalization, anti-jitter cache, multi-endpoint isolation | Released |
| **v0.5.0** | 1.2 | Zero-deploy single-file interactive report (Scroll Spy / Deficit linkage) | Released |
| **v0.6.0** | 1.3 | Training lookback and period delta loop (Practice Feedback Loop) | Released |
| **v0.7.0** | 1.4 | **Agentic maturity system refactor** (six axes + three-layer model + environmental-recovery) | Released |
| **v0.8.0** | 1.4 | `collaboration_framing` redefinition + `goal_locking_speed` signal | Released |
| **v1.0.0** | 1.0 | Effective Task Contract, read-only recon exemption, keyword verification, work_focus LLM synthesis, evidence-based Prompt Coach; product and Schema restart from 1.0 | Released |
| **v1.0.1** | 1.0 | LLM privacy boundary, OpenCode/status correctness, atomic persistence, strict layering, scoring calibration, and cross-platform CI | Release candidate |
| **v1.0.2** | 1.0 | DDD explainable assessment policy 2.0, root-task normalization, DeepSeek Harness/ZCode readers | Implementation candidate |
| **v1.0.3+** | 1.0 | Multi-device snapshot aggregation and team aggregate dashboard | Planned |
| **v2.0.0+** | 2.0 | Plugin market and open platform API | Long-term |

---

## 3. Completed Milestones

### 3.1 v0.4.0 (Schema 1.1) - Agentic Diagnosis Base
* **Three-stage LLM diagnosis**: Stage-1 candidates -> Stage-2 LLM depth + counterexample -> Stage-3 rule rerank.
* **Agentic Evidence Graph**: Six-dimension session fact graph (task intent, method, context, execution path, closure, human intervention) in Sidecar archive.
* **Action Contract Generator**: Dynamic Rule/Skill/Workflow draft suggestions; replaces fixed text cards.
* **Human correction cost trend**: Tracks `human_intervention_session_rate` Improving/Worsening/Flat in snapshots.

### 3.2 v0.4.2 (Schema 1.2) - Performance and Scoring Refactor
* **Dynamic metric normalization**: When Cursor/Trae lack Token metrics, [scorer.py](../../ai_growth_mirror/domain/growth/scorer.py) strips Token weight and redistributes others; fixes zero-penalty gap.
* **Per-Session DB Revision**: AI chat core row hash prevents unrelated IDE state from cache jitter invalidation.
* **Multi-machine physical isolation**: `(source_machine, session_id)` dedup; machine subdirectories in cache.
* **Lazy Placeholder parsing**: Initial scan only extracts `project_path` Placeholder; deep parse after filter/sample; ~100x throughput gain.

---

## 4. Mid-Term Plan (v0.5.0 ~ v0.8.0)

> **Evolution logic**: Diagnosis (v0.4) -> Readable interaction (v0.5) -> Training loop (v0.6) -> **Agentic assessment refactor (v0.7)** -> Collaboration framing redefine (v0.8) -> Effective Task Contract and version baseline (v1.0) -> Cross-endpoint aggregation (v1.0.x) -> Platform (v2.0). Each version solves 1-2 gaps; later versions depend on prior snapshot/sidecar contracts without overturning main chain.

### Report Content Version Closed-Loop Plan

> Each version must close-loop from "what users see in the report," not only feature bullets.

| Version | Report Add/Change | What Users See | Closed-Loop Basis |
|------|-----------------|--------------|---------|
| **v0.5** | Five-axis radar interaction + Scroll Spy + Deficit linkage | Click gap -> rewrite card; radar hover shows sub-dimension facts | Report usability |
| **v0.6** | Training lookback fold + period delta cards + CLI status | Prior suggestions landed (improved/partial/unchanged); Collaboration Index trend line | Coach advice trackable |
| **v0.7** | **Hexagon radar** (+ agentic_system) + environmental-recovery fix | Sixth axis Agentic Systemization; recovery no longer misjudged as user fault | Agentic assessment completeness |
| **v0.8** | `collaboration_framing` rename + goal_locking_speed | Radar label from task expression to Collaboration Framing; tooltip shows goal lock speed | Multi-turn collaboration recognition |
| **v1.0** | Effective Task Contract + Proof Loop keyword verification | Task contract source distribution; custom build/script verification not missed; read-only recon not penalized as slow lock | General Agentic report calibration |
| **v1.0.x** | Cross-machine merged view | Multi-PC sessions in one report; device capability comparison | Multi-endpoint worker needs |
| **v1.0** | Community benchmark + plugin extension axes | "Your Agentic Systemization in global top 30%"; third-party custom axes | Platform openness |

### 4.1 v0.5.0 - Zero-Deploy Interactive Report (SPA-like Single-File HTML)
* **Goal**: Stronger report UX without breaking "double-click local, zero server."
* **Approach**: Avoid React/Vue SSR local bundle (CORS on `file://`); **pure native JS + refined CSS single-file interaction**.
* **Features**:
  - **Scroll Spy & Sidebar Sticky**: Sidebar follows scroll; section viewport highlight.
  - **Deficit-to-Card Linking**: Click hero Deficit -> matching Rewrite Card.
  - **Radar hover**: Five-axis radar hover shows score factors and sub-dimension facts.
  - **Native Dark Mode**: System dark theme + manual toggle.

### 4.2 v0.6.0 - Practice Feedback Loop

> Detail: [v0.6.0-DESIGN.md](v0.6.0-DESIGN.md)

**Shipped progress** (as of 2026-06-07):
- Active clarification detection + `intent_clarity` boost (heuristic + scorer, single-source `_intent_clarity_boost`)
- Action Contract period evaluation + in-report "Prior Period Training Lookback" fold
- Radar Collaboration Index trend line + delta badge
- CLI `status` (weekly sample progress + prior contract hints), `test_cli_status.py` with/without history
- Schema 1.3; LLM and heuristic share `detect_active_clarification`; `active_clarification` field aligned
- Boost transparent in five-axis radar tooltip; `summary.json` outputs `active_clarification_rate` / `intent_clarity_boost`

* **Goal**: Trackable, evaluable coach advice; fix multi-turn interaction scoring paradox.
* **Features**:
  - **Action Contract tracking**: Auto-detect prior `action_contracts` improvement (improved / partial / unchanged) with confidence correction; no prior data -> "no prior data," no empty cards.
  - **Period delta**: Five-axis + friction period delta; SVG trend + arrow cards; hidden when only one snapshot.
  - **Active clarification fix**: Recognize multi-turn high-quality task mode (`active_clarification`); up to +8 on `intent_clarity`; transparent in tooltip.
  - **CLI `status`**: `ai-growth-mirror status` sample progress (< 100ms, no full recompute) + weekly Action Contract practice hints.
  - **In-report lookback**: Collapsible "Prior Period Training Lookback" below `#section-growth-plan`.

### 4.3 v0.7.0 - Agentic Maturity System Refactor

> Detail: [v0.7.0-DESIGN.md](v0.7.0-DESIGN.md)

**Core judgment**: `intent_clarity` too high for Agentic maturity; `agentic_system` was gate not continuous contributor; "continue/resume" misclassified as user fault - three defects fixed together.

**Three-layer maturity model** (replaces implicit single-layer view):

```
Layer 3: Reusable AI work system  -> agentic_system (new formal axis, 10%)
Layer 2: AI driven to real work   -> execution + impl + delivery + recovery
Layer 1: Human starts collaboration -> intent_clarity (down to 15%)
```

**Main changes**:
- **Six axes**: `agentic_system` sixth formal axis (10%), radar and gap_rankings
- **Weight redistribution**: `intent_clarity` 20%->15%, `execution_driving` 22%->24%, `agentic_system` gate->10%
- **environmental-recovery fix**: "Continue/retry/resume" -> `environmental`, no `off-track`
- **Hexagon radar**: SVG pentagon -> hexagon

### 4.4 v0.8.0 - `collaboration_framing` Redefinition

* **Goal**: `intent_clarity` -> `collaboration_framing` (Collaboration Framing); from first-turn completeness to multi-turn startup quality.
* **Changes**:
  - `active_clarification_rate` from patch boost to `collaboration_framing` largest sub-item (0.34)
  - New `goal_locking_speed`: speed to align goals, boundaries, deliverable path; engineering sessions use first file write as proxy
  - `tool_leverage_bonus` and `workflow_maturity_bonus` merged into `agentic_system`

### 4.5 v1.0.0 - Effective Task Contract and Agentic Report Calibration (Released)

> Detail: [v1.0.0-DESIGN.md](v1.0.0-DESIGN.md)

**Goal**: Fix general Agentic report misjudgment for highly rule-driven users: existing Skill/Rule/Workflow contracts should not fail Collaboration Framing for missing hand-written first-turn acceptance.

**Changes**:
- Effective Task Contract signal: user explicit, Skill/Rule/Workflow, Agent-derived, post-hoc correction contracts.
- Verification: keyword/script-suffix matching for build, compile, test, custom `.ps1` / `.bat`.
- All read-only before first write: no ordinary delay penalty on `goal_locking_speed`.
- Version line enters `v1.0.x`, aligned with `CACHE_SCHEMA_VERSION=1.0`.
- "What you are doing" uses `work_focus/` cross-session LLM synthesis; rules retain stats rollups and output guardrails only.
- Prompt Coach / coaching prompts and i18n drop fixed training copy; personalized conclusions must be evidence-generated.

---

## 5. Current Hardening and Long-Term Plan (v1.0.2+)

### 5.1 v1.0.1 - Trust and Resilience Hardening (Release Candidate)
* **Goal**: Close privacy, correctness, persistence, layering, and release-evidence gaps while keeping Cache Schema 1.0 and public CLI names stable.
* **Features**: Unified outbound LLM redaction and prompt-injection isolation; OpenCode content revisions and one-pass collection; multi-machine `status`; atomic cache/report/snapshot writes; scoring calibration fixtures; Windows/Linux and Python 3.12/3.13 CI.
* **Design authority**: [v1.0.1-DESIGN.md](v1.0.1-DESIGN.md) and [ADR-v1.0.1-trust-resilience.md](ADR-v1.0.1-trust-resilience.md).

### 5.2 v1.0.2 - DDD Explainable Assessment and New Readers (Implementation Candidate)
* **Goal**: place scoring, session reading, and the learning loop in explicit bounded contexts; remove duplicate formulas, missing-as-perfect behavior, raw-volume rewards, and child-session double counting.
* **Features**: versioned assessment policy 2.0; coverage and reason explanations; read-only DeepSeek Harness and ZCode ACLs; root-task roll-up; cross-policy comparison rejection.
* **Design authority**: [v1.0.2-DESIGN.md](v1.0.2-DESIGN.md) and [ADR-v1.0.2-assessment-policy-and-root-task.md](ADR-v1.0.2-assessment-policy-and-root-task.md).

### 5.3 v1.0.3+ - Cross-Machine Snapshot Aggregation and Team Aggregate
* **Goal**: Remove multi-device barriers; unified view for multi-endpoint developers and teams.
* **Features**:
  - **Cross-Machine CLI Aggregator**: `--sources` multiple machine cache paths; merged cross-device profile.
  - **Manager Dashboard**: Fully local, anonymous, redacted merge of user snapshot Sidecars; team Top 3 pain points and capability baseline.

### 5.4 v2.0.0 - AI Coding Coach Platform
* **Open Platform API**: Third-party AI tools (IDE scripts, VS Code plugins) submit session packets via API.
* **Plugin Market**: Custom rules/LLM plugins on six-dimension Agentic Evidence Graph facts; extend six-axis scoring.
* **Community Benchmark**: Voluntary anonymous sidecar upload; benchmarking (e.g. "Agentic Systemization in global top 30%").

### 5.5 v1.5.0 - IDE Real-Time Preflight Plugin
*(v1.5.0 is a planned feature version, independent of cache Schema)*
* **Real-time preflight**: IDE Chat "Preflight Check" before send; intercept diagnosis.
* **Drift prediction**: From recent gaps, predict missing context or drift risk in current Prompts.

---

## 6. Revision History

| Date | Product Version | Cache Schema | Summary |
|------|---------|-------------|---------|
| 2026-09-02 | v1.0.2 | 1.0 | **DDD explainable assessment and reader expansion (implementation candidate)**: policy 2.0 single truth, missing=unavailable, root-task roll-up, DeepSeek Harness/ZCode ACLs, coverage explanations, and cross-policy rejection; team aggregation moves to v1.0.3+. |
| 2026-09-02 | v1.0.1 | 1.0 | **Trust and resilience hardening (release candidate)**: unified LLM privacy boundary, OpenCode/status correctness, atomic persistence, snapshot layering, scoring calibration, and locked cross-platform CI; team aggregation moves to v1.0.2+. |
| 2026-06-09 | v1.0.0 | 1.0 | **Effective Task Contract and version strategy (release candidate)**: report task contract source/fulfillment; keyword verification; read-only recon exemption; work_focus LLM cross-session synthesis; evidence-based Prompt Coach / i18n; product and cache schema baseline 1.0; run `cache prune` or regenerate after upgrade. |
| 2026-06-07 | v0.8.0 (release) | 1.4 | **v0.7/v0.8 release alignment**: roadmap tables v0.7/v0.8 planned -> released; six-axis weights finalized 14/25/19/19/10/13; sync README, ARCHITECTURE_PRINCIPLES, DETAILED_DESIGN. |
| 2026-06-07 | v0.7.0 (plan) | 1.4 | **Agentic maturity refactor plan**: positioning "Agentic operating maturity"; three-layer model; `agentic_system` sixth axis (10%); `intent_clarity` 20%->15%; `execution_driving` 22%->24%; environmental-recovery fix; v0.8.0 collaboration_framing reserved; add [v0.7.0-DESIGN.md](v0.7.0-DESIGN.md). |
| 2026-06-07 | v0.6.0 (close) | 1.3 | **v0.6.0 release alignment**: active clarification boost in radar tooltip; `summary.json` adds rates; LLM/heuristic share detector; Schema 1.3; `test_cli_status.py`; checklist all done. |
| 2026-06-06 | v0.5.0 | 1.2 | **v0.5.0 release**: interactive report released; v0.5->v0.6->v0.7 logic; v0.6.0 progress checklist. |
| 2026-06-06 | v0.6.0 (plan) | 1.3 | **v0.6.0 detailed design**: Action Contract tracking, period delta, active clarification, CLI status; add [v0.6.0-DESIGN.md](v0.6.0-DESIGN.md). |
| 2026-06-06 | v0.4.2 | 1.2 | **Roadmap refactor**: decouple product and cache versions; v0.4.2/v0.4.0 milestones; v0.5 single-file approach; v0.6/v0.7 detail. |
| 2026-06-03 | v0.4.0 | 1.1 | Nav/DOM alignment, scroll highlight, Scope config, five-axis ratios, evaluation status, etc. |
| 2026-06-02 | v0.1.0 | 1.0 | Initial product roadmap. |
