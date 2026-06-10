# AI Growth Mirror (AI Collaboration Growth Mirror)

Chinese README: [README.md](../README.md)

[![Release](https://img.shields.io/badge/Release-v1.0.0-blue.svg)](../pyproject.toml)
[![Schema Version](https://img.shields.io/badge/Schema-v1.0-blue.svg)](../ai_growth_mirror/domain/cache_schema.py)
[![Python Version](https://img.shields.io/badge/python-3.12+-green.svg)](../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](../LICENSE)

> **Do you use Cursor, Claude Code, Trae, or other AI coding tools every day, yet delivery still feels inconsistent? Or do you often feel pulled along by the AI without knowing where the collaboration actually breaks down?**
>
> **AI Growth Mirror** is a **local-first** **Agentic operation maturity assessment system**. It quietly and safely reads AI coding session history already on your machine, then uses the **Four-Evidence Method** and **Six-Axis framework** to turn vague collaboration intuition into **observable, explainable, reviewable** growth reports. This is not a decorative "AI usage poster"; it is a product that helps you break collaboration bottlenecks and compound high-leverage technical habits.

---

## AI Tool Evolution in Three Stages: Where Are You?

AI tools are moving through three stages, and what matters for assessment shifts with them:

```
Stage 1 (Copilot)           Stage 2 (Agentic)            Stage 3 (Autonomous)
---------------------    -------------------------    --------------------------
Human writes, AI completes Human sets goals, AI executes Human sets strategy, AI finishes
Intent matters               Execution is the core        Alignment and control matter
"How good is your prompt?"   "Can you drive stable delivery?" "Can you build a trustworthy AI system?"
```

**Where AI Growth Mirror fits**: not a prompt scorer, but an **Agentic operation maturity assessment**.
Since v0.7, the evaluation focus has shifted from "how complete your first prompt is" to "whether you can turn AI into a stable, reusable productivity system."

---

## Assessment Methodology: The Four-Evidence Method

AI Growth Mirror rejects meaningless raw stats (message counts, lines typed) and instead maps real human-AI collaboration through the **Four-Evidence Method**:

* **Context Frame**: Do you establish clear goals, constraints, and acceptance criteria when starting and aligning on a task? (via a single precise turn or multi-turn clarification)
* **Flow Orchestration**: Do you drive AI through complex problems continuously, rather than taking over at every step?
* **Proof Loop**: Are build, test, and correction behaviors woven into the collaboration loop?
* **Method Asset**: Do you distill effective practices into high-leverage assets, such as Rules, Skills, and Workflows, and reuse them?

> **The Four-Evidence Method is the methodology entry (four memorable collaboration pillars); the Six-Axis Radar below is its measurable expansion.** Mapping:
> - Context Frame -> **Collaboration Framing**
> - Flow Orchestration -> **Execution Driving + Implementation Depth** (continuous push *and* real implementation depth)
> - Proof Loop -> **Delivery Closure + Adaptive Recovery** (build/test closure + course correction after drift)
> - Method Asset -> **Agentic Systemization**

---

## Six-Axis Agentic Maturity Radar (v1.0)

Each report projects your results onto a **six-axis collaboration radar** (the **Collaboration Index** is derived from it). It is the measurable expansion of the Four-Evidence Method above:

| Axis | Weight | What it measures |
|------|:------:|------------------|
| **Collaboration Framing** (`collaboration_framing`) | **14%** | Collaboration kickoff quality: goal-locking speed, proactive clarification rate, and Effective Task Contract (v1.0.0) |
| **Execution Driving** (`execution_driving`) | **25%** | Autonomous tool-chain length, sub-agent orchestration, and human-AI rhythm (the Agentic main battlefield) |
| **Implementation Depth** (`implementation_depth`) | **19%** | File change volume, code verification coverage, and implementation boundary control |
| **Delivery Closure** (`delivery_closure`) | **19%** | Task completion rate, verification behavior, test/build/script validation, and contract fulfillment |
| **Adaptive Recovery** (`adaptive_recovery`) | **10%** | Quality of correction and return-to-track when AI drifts or errors |
| **Agentic Systemization** (`agentic_system`) | **13%** | Method assetization: Skill, Workflow, MCP, Subagent, and related patterns |

> **Why these weights**: see [docs/design/v0.7.0-DESIGN.md](docs/design/v0.7.0-DESIGN.md), [docs/design/v0.8.0-DESIGN.md](docs/design/v0.8.0-DESIGN.md), [docs/design/v0.8.1-DESIGN.md](docs/design/v0.8.1-DESIGN.md), and [docs/design/v1.0.0-DESIGN.md](docs/design/v1.0.0-DESIGN.md)

---

## Core Highlights (v1.0.0)

### 1. Six-Axis Agentic Operation Maturity Assessment

Since v0.7, the system no longer judges "how good your prompt is" in isolation. It uses six axes - **Collaboration Framing, Execution Driving, Implementation Depth, Delivery Closure, Adaptive Recovery, Agentic Systemization** - to assess real collaboration maturity. v0.8 finalized `collaboration_framing` as a formal axis and extended kickoff quality from "first-turn completeness" to multi-turn goal locking.

### 2. Goal Locking Speed

v0.8 added `goal_locking_speed`: via `turns_until_first_file_write`, it observes how quickly you drive AI to lock goals, boundaries, and a deliverable path. Readers with fine-grained tool streams record user turns before the first write; sessions without tool streams use an explicit fallback so "no signal" is never disguised as a deep judgment.

### 3. Agentic Evidence Graph + Action Contract

Reports build a six-dimensional evidence graph: task intent, method usage, context, execution path, closure state, and human intervention. Training suggestions are not fixed copy; they are Action Contracts in Rule / Skill / Workflow / Checklist form, generated from real gaps, correction patterns, and the evidence graph.

From v1.0.0, the system distinguishes **user-explicit contracts**, **Skill/Rule/Workflow contracts**, **agent-derived contracts**, and **post-hoc correction contracts**, so "global rules exist but acceptance was not handwritten in turn one" is not misread as pure Collaboration Framing failure.

### 4. Training Loop + Period-over-Period Tracking

- **Action Contract lookback**: automatically detects how last period's suggestions improved this period (improved / partial / unchanged)
- **Growth trajectory**: per-period deltas on six-axis scores and friction changes, with SVG trend lines and change arrows
- **CLI `status`**: `ai-growth-mirror status` shows sample progress and this week's practice hint in under 100ms

### 5. One-Click Support for 9 Major AI Tools

Scan once; automatically detect and aggregate sessions from these **9** tools:
- **International**: Claude Code, Codex, Cursor, Gemini, Cline, Kilo Code
- **China ecosystem**: CodeBuddy, Trae, QCoder

### 6. Local-First, Privacy Under Your Control

Analysis runs offline with a local rules engine by default. Even in `llm` mode, only redacted session summaries, not full source code, are sent for semantic diagnosis. Run `generate --redact` to redact paths and code-sensitive content in HTML reports, sidecars, share cards, and snapshots.

---

## Report Preview

After generating `ai-growth-mirror.html`, open it locally with a double-click; no deployment required. The report is organized as **diagnosis -> training -> tracking**, with a sidebar for quick section jumps.

### This Period's Collaboration Evolution Report (Hero)

See at a glance: **level | Collaboration Index | what to practice next**. Light and dark themes supported.

| Light theme | Dark theme |
|:---:|:---:|
| ![Hero light theme]](../docs/assets/images/report-hero-light.png) | ![Hero dark theme]](../docs/assets/images/report-hero-dark.png) |

### Growth Signals Overview

Six-axis collaboration radar, Collaboration Index trend line, Top 3 gaps, and actionable next steps.

![Growth signals: six-axis radar, trend line, and gap ranking]](../docs/assets/images/report-growth-signals.png)

### Collaboration Style Lens

A four-dimension collaboration profile (kickoff / drive / closure / reuse): your AI collaboration *style*, not just scores.

![Collaboration style lens: four-dimension profile]](../docs/assets/images/report-style-lens.png)

### Work Focus & Collaboration Rhythm

What you worked on (projects, goal types, tools, languages) plus rhythm insights such as dual-mode switching.

![Work focus and collaboration rhythm]](../docs/assets/images/report-work-focus-rhythm.png)

### Methods Worth Keeping This Period

Reusable collaboration patterns distilled from high-scoring sessions (deep delegation, tool-chain orchestration, structured execution), ready to apply to similar tasks.

![Methods worth keeping: high-scoring session exemplars]](../docs/assets/images/report-exemplars.png)

---

## Quick Start

### Requirements
- Python **3.12+**

### 1. Install

```bash
# After cloning the repo, from the repository root:
pip install -e .

# OpenAI-compatible gateways work out of the box; claude / gemini need the extra:
pip install -e ".[llm]"
```

Or use [uv](https://github.com/astral-sh/uv) (aligned with `uv.lock`):

```bash
# Default install includes the OpenAI SDK (deepseek / openai / openai_compatible LLM diagnosis)
uv sync

# Add Anthropic / Gemini SDKs only when using claude or gemini providers
uv sync --extra llm
```

### 2. Initialize configuration (optional: API keys and asset roots)

```bash
cp config.example.yaml config.yaml
# Edit config.yaml: LLM provider, API key, local Agent asset scan roots
```

### 3. Generate your personal growth report

Pick one invocation style (run from **your workspace directory**, usually a project repo root):

```bash
cd /path/to/your/project-workspace

# Option A: after pip install -e . (CLI on PATH)
ai-growth-mirror generate

# Option B: Python module from the ai-growth-mirror repo root (no global CLI)
python -m ai_growth_mirror.cli generate

# Option C: uv (from the ai-growth-mirror repo root)
uv run python -m ai_growth_mirror.cli generate
```

Check version:

```bash
python -m ai_growth_mirror.cli --version
# or, when the CLI entry is installed:
ai-growth-mirror --version
```

After a successful run, your current directory will contain:
- `ai-growth-mirror.html`: interactive main report for personal Agentic maturity analysis.
- `ai-growth-mirror.json`: structured Evidence Sidecar (Agentic Evidence Graph, coverage, and statistical evidence).
- `ai-growth-mirror.summary.json`: stable summary contract for share cards, downstream use, and automation.
- `ai-growth-mirror-share.html`: redacted share card for external sharing.
- `ai-growth-mirror-archive/`: snapshot archive; from the second run, **growth trajectory comparison** (this period vs. last) activates automatically.

---

## Advanced CLI Options

Examples use the CLI entry. Without a global install, replace `ai-growth-mirror` with `python -m ai_growth_mirror.cli` (or `uv run python -m ai_growth_mirror.cli` with uv).

* **This week's sample progress**: `ai-growth-mirror status`
* **Filter by tools**: `ai-growth-mirror generate --tools cursor,trae`
* **Lock a time window**: `ai-growth-mirror generate --since 2026-01-01 --until 2026-06-30`
* **Offline rules engine** (no external network calls or API cost): `ai-growth-mirror generate --session-read-mode heuristic`
* **Scope analysis** (filter by repository, directory, or keyword): `ai-growth-mirror generate --repo app-repo --dir ~/projects/app`
* **Compare historical snapshots manually**: `ai-growth-mirror compare <left_snapshot_id> <right_snapshot_id>`
* **Prune stale cache**: `ai-growth-mirror cache prune`

---

## Developer Documentation

For customization, new adapters, or algorithm debugging, see the canonical docs (Chinese versions linked from each English page):
* [Layering, dependencies, and architecture](../docs/en/design/ARCHITECTURE_PRINCIPLES.md)
* [Product roadmap](../docs/en/design/PRODUCT_ROADMAP.md)
* [v1.0.0 Effective Task Contract and Agentic report calibration](../docs/en/design/v1.0.0-DESIGN.md)
* [v0.8.1 collaboration fairness and cold-start performance](../docs/en/design/v0.8.1-DESIGN.md)
* [v0.8.0 Collaboration Framing and goal locking speed](../docs/en/design/v0.8.0-DESIGN.md)
* [v0.7.0 Agentic architecture redesign](../docs/en/design/v0.7.0-DESIGN.md)
* [v0.6.0 training loop design](../docs/en/design/v0.6.0-DESIGN.md)
* [Product tone, naming, and redaction guidelines](../docs/en/design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)
* [Full docs index](../docs/en/README.md) | [Design index](../docs/en/design/README.md)
* [Contributing guide](../CONTRIBUTING.md)

---

## License

This project is released under the [MIT License](../LICENSE).
