---
title: AI Growth Mirror Personal Detailed Design
domain: growth_mirror
status: canonical
updated_at: 2026-06-06
score_target: 9.9
---

Chinese version: [AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md](../../design/AI_GROWTH_MIRROR_PERSONAL_DETAILED_DESIGN.md)

# AI Growth Mirror Personal Detailed Design

## 1. Product Positioning

The personal edition is not an "employee analysis report" but a sustainable personal AI collaboration growth product.

Value to users must be expressed as:

- Help me see my collaboration habits
- Help me improve questioning and workflow quality
- Help me solidify high-quality methods

Not:

- Assess whether I am a good employee
- Calculate whether I deserve performance review

## 2. Product Naming

Product name:

- `AI Growth Mirror` (AI 成长镜)

Page main title:

- `Collaboration Evolution Report (This Period)` (本期协作进化报告)

Default export filename:

- `ai-growth-mirror.html`

## 3. Information Architecture

Home main-chain sections (aligned with `report_view._build_report_sections` nav order):

1. **Hero summary** (Hero + Usage cards, `#section-summary`)
2. **Growth signals overview** (six-axis radar + "Collaboration Capability Map" sub-block, `#section-growth-signals`)
3. **Stage assessment** (`#section-level-evidence`)
4. **Collaboration level guide** (`#section-level-guide`)
5. **Prompt growth coach** (`#section-prompt-coach`)
6. **Friction root-cause map** (`#section-friction`)
7. **Methods worth keeping this period** (`#section-exemplars`)
8. **Next-phase training sprint** (2 items, `#section-growth-plan`)
9. **What you are working on** (`#section-focus`)
10. **Collaboration rhythm** (`#section-rhythm`)
11. **Highlights this period** (`#section-wins`)

Conditional / appendix sections:

- **AI asset footprint** (`#section-agent-asset`, requires hub / asset config)
- **Growth trajectory** (`#section-growth-delta`, requires historical snapshot before current generate; usually from 2nd generate)
  - Top: **last 30 days trend conclusion**; metrics at least `mirror_score`, `growth_level`, six axes, Prompt Quality five dimensions, five action friction types
  - Same-day multiple generates: page shows last snapshot of day; sidecar JSON keeps full `window_points` and display `daily_points`
  - When `daily_points < 3`: show available points and "insufficient data"; no forced long-term trend claim
  - Old capability axes (`delegation / verification / breadth / authorship / outcome / workflow`) or missing six axes: trend and latest-vs-previous low confidence, schema mismatch; no strong trend across scoring model changes
  - If prior snapshot exists: lower half **current vs previous change diagnosis**
  - Diagnosis top: 5 summary cards: current stage, Collaboration Index change, max improvement axis, current gap axis, confidence/sample notes
  - Diagnosis middle: six-axis compare, growth waterfall, Prompt Quality source notes, friction/recovery change, method asset solidification
  - Diagnosis bottom: key evidence cards and next-phase priority training; all conclusions map to sidecar JSON fields
- **Collaboration style lens** (`#section-style-lens`, appendix, not in main nav)

Constraints:

- Hero: "where you are, why this judgment, what to practice next"; no share-card duplication.
- Share page: one external sentence, 3 key facts, stage/score; no internal "shareable one-page summary" product copy.
- Main report full quick nav; order matches anchor order.
- Growth trajectory main view: last 30 days; "current vs snapshot before this generate" auxiliary at block bottom only.
- No historical snapshot: no empty charts; first generate archives only.
- Compare block Prompt Quality, usage, sample size must show confidence boundaries; no heuristic or low sample as certainty.

## 4. Copy Strategy

## 4.1 Forbidden Words

- employee
- enterprise
- performance review (考核)
- performance (绩效)
- ranking
- portrait scoring
- work rhythm (external: **collaboration rhythm**, see `#section-rhythm`)

## 4.2 Preferred Words

- growth
- evolution
- collaboration
- mirror
- method
- training
- style
- collaboration rhythm

## 4.3 Implementation Naming (aligned with UI)

Main chain uses `collaboration_rhythm`:

- Domain: `GrowthProfile.collaboration_rhythm_type`
- View: `CollaborationRhythmSectionView`, `PersonalReportView.collaboration_rhythm`
- i18n: `view_model_*.yaml` -> `collaboration_rhythm`
- Sidecar: `summary.json` -> `collaboration_rhythm`

Anchor `#section-rhythm` unchanged for bookmarks and tests.

## 5. Data Mapping

## 5.1 Stage Positioning

Backend fields:

- `growth_level`
- `mirror_score`

Frontend:

- `growth_level` -> "current stage"
- `mirror_score` -> Collaboration Index

## 5.2 Six-Axis Growth Base

Backend:

- `radar_axes` (six-axis scores and reasons)
- `growth_stage` (`strongest_axis` / `primary_gap` / `next_breakthrough`)
- Six-axis sub-score dict: `collaboration_framing`, `execution_driving`, `implementation_depth`, `delivery_closure`, `adaptive_recovery`, `agentic_system`

Frontend labels (zh product copy preserved in i18n):

- Collaboration Framing (协作框定)
- Execution Driving (协作驱动)
- Implementation Depth (实现下潜)
- Delivery Closure (交付收口)
- Adaptive Recovery (恢复推进)
- Agentic Systemization

Section names:

- Growth signals overview
- Collaboration capability map

Constraints:

- Radar or equivalent main chart: these six axes only
- `mirror_score` / `growth_level` retained but from six axes + confidence correction
- User must see `strongest_axis`, `primary_gap`, `next_breakthrough`

## 5.3 Style / Gaps / Stage

Backend:

- `style_traits`
- `gap_rankings`
- `summary.growth_stage`

Frontend:

- `style_traits`: how you usually collaborate
- `gap_rankings`: current biggest gaps
- `growth_stage`: overall growth band

Do not mix these; do not call stage gaps personality defects.

## 5.3.1 Agentic System Maturity

`growth_level` expresses whether the user can stably operate an Agentic operating system: real usage, tool orchestration, context engineering, verification loop, drift recovery, method asset downstream reuse.

Primary capabilities:

- `Intent Framing`: goals, boundaries, constraints, acceptance upfront.
- `Workflow Orchestration`: plan / spec / tdd / delivery workflow multi-stage advance.
- `Tool & Skill Leverage`: skill, slash, MCP, subagent, multi-model in real sessions.
- `Context Engineering`: files, rules, docs, error logs, history in tasks.
- `Execution Depth`: real implementation and complex boundaries.
- `Verification Closure`: test / build / smoke / replay / golden / commit verifiable states.
- `Adaptive Recovery`: recover with new evidence after drift, error, or block.
- `Method Assetization`: skill / rule / prompt / script / checklist / ADR solidified and reused.

Evidence priority:

- `Observed Usage` highest: real session skill / slash / workflow / tool / verification.
- `Local Method Framework Match` very high: `report.local_method_frameworks` or `asset_roots` hub private methods hit in `unique_skills_used` / `slash_commands`.
- `Repeated Pattern` next: same method/skill/workflow fingerprint across sessions.
- `Authored Asset` medium: create or edit skill / rule / prompt / script / governance asset.
- `Inventory Context` lowest: asset_root / hub files as background only.

Product constraints:

- User directory layout not hardcoded as universal standard; report prioritizes real use and reuse.
- `local_method_frameworks`: configurable, hub-extractable, aggregated; exact match to session skills/slash; unmatched candidates context only, not level evidence.
- Skill/rule/prompt file count alone cannot push L4/L5; use/reuse/orchestration/verification in real tasks required.
- `level_evidence` must show Agentic system maturity with usage rate, workflow fingerprint, public framework hits, local method hits, reuse, asset authoring, high-leverage features.
- `human_intervention_session_rate`: v1 "reduce human intervention cost" factual metric; trend only with comparable history.
- Insufficient data: "not observed" or blank; no static template or inventory inventing capability portrait.

## 5.4 Prompt Module

Backend:

- `pq_avg_dimensions`
- `pq_deficit_counts`
- `pq_top_takeaways`
- `pq_sessions_evaluated`
- `pq_llm_session_count` / `pq_heuristic_session_count` / `pq_light_session_count` (compat)
- `pq_llm_evaluated_count` / `pq_insufficient_count` / `pq_llm_failed_count` / `pq_llm_unavailable_count` (by `evaluation_status`)
- `PromptLensScores.evaluation_status`: `llm_evaluated | insufficient_input | llm_failed | llm_unavailable | not_applicable`

Frontend block:

- Prompt growth coach

Goals:

- Not model mechanism explanation
- "How to ask better next" at a glance
- Prefer `pq_top_takeaways`, real prompt snippets, rewrite examples over abstract advice
- Generate from evidence or leave blank; no static template posing as "this is how you are now"
- Prompt coach must cover **full PQ main chain**; no silent gap on short sessions or no LLM
- `heuristic` only as proxy source; not a separate "Prompt Quality product"
- Prompt input copy: `evidence packet` / `period summary packet`; neutral tone
- System prompts: behavior evidence + trainable next step; no org evaluation or tool marketing tone

Source disclosure:

- Report must state: LLM semantic count (`llm_evaluated`), short-session proxy (`insufficient_input`), LLM failed (`llm_failed`), no LLM configured (`llm_unavailable`)
- `session_read_mode=heuristic` = current source mode, not alternate PQ definition
- Human-readable non-zero clauses only; forbid `LLM n / heuristic n / light n` columns

## 5.4.2 Prompt Growth Coach Upgrade Boundary

Upgraded from "explain scores" to **AI requirement diagnosis engine**:

1. `top_deficits`: main request deficits with problem, impact, source boundary, confidence, evidence summary
2. `rewrite_cards`: 2-4 "original vs better" training cards
3. `prompt_style`: `explicit_requirement_prompt / indexed_prompt / mixed_prompt / under_specified_prompt`
4. `suggested_next_prompt`: only from real `rewrite_cards` / LLM coaching / grounded takeaway; empty if no personalized rewrite
5. `closure_guidance`: correct closure by task type; `mode` (`open_ended | engineered`); open for explore/design/analysis/copy; engineered for code/config/SQL/structured gen
6. `friction_synthesis`: label synthesis; LLM growth_coach when configured (evidence_refs guardrail); else `domain/growth/prompting.py`; linked `growth_plan.linked_friction_synthesis_ids`
7. `preflight_checklist` / `recommended_training_inputs`
8. `universal_template` / `scenario_templates`: reference assets only; cannot replace `rewrite_cards` or `suggested_next_prompt` on main chain

Additional constraints:

- `indexed_prompt` positive method signal; not equivalent to `missing-context`
- Static templates knowledge assets only; not "how you should ask this time"
- Full `seven_day_training_plan` not in Prompt coach; unified under next-phase training sprint

Hard constraints:

- Original user phrasing only when real `PromptLensTakeaway.original` exists
- Rewrite examples only with real `better_prompt` / grounding; else blank
- Heuristic-only must mark proxy source
- Short sessions: show source notes and checklist; do not hide module

## 5.4.3 Next-Phase Training Sprint Linkage

Must consume:

- `growth_trajectory`: 30-day weak axes, latest regression axes, latest evidence
- `prompt_coach`: top deficits, rewrite cards, templates
- `agentic_system_score / human_intervention_session_rate`

Rules:

- Weak Prompt dimension -> `prompt:*` tasks; no static template replacing personalized evidence
- `agentic_system_score < 75` or high correction rate -> Action Contract for rule/skill/workflow and natural-language trigger
- `collaboration_framing + missing-context / vague-request` -> requirement expression training
- `delivery_closure + missing-acceptance-criteria` -> acceptance criteria training
- Each task: `evidence_refs`, `action_contract`, `linked_prompt_deficit_ids / linked_template_ids / linked_rewrite_card_ids / linked_growth_trend_refs / linked_closure_guidance_ids`

## Three-Stage LLM Diagnosis Layer

### Architecture

```
Stage 1 (Rule)   ->  DiagnosisCandidatePacket
Stage 2 (LLM)    ->  GroundedDiagnosis (evidence_refs + confidence + why_not_other_diagnosis)
Stage 3 (Rule)   ->  rerank_diagnosis_result()
```

### Key Contracts

| Object | Location | Description |
|------|------|------|
| `DiagnosisCandidate` | `domain/growth/diagnosis.py` | Single candidate: code / urgency / reason_codes / evidence_snippets |
| `DiagnosisCandidatePacket` | same | Stage-1: candidates + intervention rate + gap counts + session evidence |
| `GroundedDiagnosis` | same | Stage-2: label / explanation / confidence / evidence_refs / why_not_other_diagnosis |
| `DiagnosisResult` | same | primary + secondary + synthesis_confidence + source |

### Hard Constraints
- LLM `evidence_refs` must cite Stage-1 packet snippets, min 1
- `why_not_other_diagnosis` must explain why not candidate 2
- `synthesis_confidence` "high" only with >=2 strong evidence
- LLM unavailable: `rule_fallback_diagnosis()` from Stage-1 candidates

## Agentic Evidence Graph

### Six Dimensions

| Dimension | Field | Source |
|------|------|------|
| Task intent | `task_intent` | `SessionRead.work_intent_mix` primary key |
| Method used | `method_used` | `unique_skills_used + slash_commands + advanced_features` |
| Context used | `context_used` | prompt features + tool_counts.Read |
| Execution path | `execution_path` | tool_counts labels (read->edit->run->verify, etc.) |
| Closure state | `closure_state` | `SessionRead.delivery_outcome` map |
| Human intervention | `human_intervention` | `user_interruptions` count |

`build_agentic_evidence_graph(sessions, session_reads)`; `evidence_graph_to_dict()` serializes to report sidecar (schema 1.2).

## Action Contract Generator

Replaces fixed 5-item `growth_plan._priority_action_contract`.

`generate_action_contracts(stats, cap_scores, graph_summary, ...)` rules:
1. Top `pq_deficit_counts` -> `_DEFICIT_RULE_TEMPLATES` rule/skill drafts
2. `agentic_system_score < 65` -> method routing Skill draft
3. `human_intervention_session_rate >= 0.20` -> human correction automation Workflow draft
4. `verification_rate < 0.40 or delivery_closure < 60` -> delivery closure Workflow draft
5. `graph_summary.high_intervention_rate >= 0.15` -> five-item Checklist draft

Output by priority desc, deduped, max max_items.

## human_cost_reduction Trend

`SnapshotSource.human_intervention_session_rate` from `stats.human_intervention_session_rate` in snapshot summary.

`HumanCostTrend` (`domain/snapshots/model.py`):
- `available: bool` - both snapshots have data
- `direction: str` - "improving" | "worsening" | "flat" | "unknown"
- `delta: float` - current - previous (negative = improving)
- `note: str` - e.g. "human correction rate reduced from 35.0% -> 15.0% (-20.0pp)"

In `SnapshotComparison` and `SnapshotTrajectoryWindow`.

## 5.4.1 usage Module

Backend:

- `total_input_tokens`, `total_output_tokens`, cache tokens, `total_cost_usd`, `avg_cost_per_session`, `avg_cache_hit_rate`, `subagent_session_count`, `mcp_session_rate`, `avg_autonomous_chain_length`, `median_session_duration_minutes`, `heavy_session_count`

Frontend:

- AI usage overview (Hero Usage cards + coverage; not separate nav)

Goals:

- "How much used, intensity, leverage" at a glance
- `memory` not collected; explicit label
- Real data only; no empty narrative

## 5.5 Friction Module

Backend: `friction_by_attribution`, `friction_type_counts`

Frontend: Friction root-cause map

Emphasis: where problems come from; what user can do next.

## 5.6 exemplar Module

Backend: `mine_exemplars(...)`

Frontend: Methods worth keeping this period

Emphasis: why worth keeping; how to migrate next time; no duplicate patterns; split "why keep" and "how migrate."

## 5.7 persona / style traits Module

Backend: `CollaborationStyleResult`, `style_traits`

Frontend: Collaboration style lens; growth signals overview

Emphasis: style preference and growth blind spots; not psychology test feel.

## 5.8 growth plan Module

Backend: `build_growth_plan(...)`

Frontend: Next two-week training sprint (nav copy; 2 items `#section-growth-plan`)

Output: training theme, why practice, Week 1, Week 2, practice Prompt.

## 5.9 Cache and Performance Base (v0.4.2 / Schema 1.2)

- **Missing-metric normalization**: `implementation_depth` strips `total_token_volume` (18%) when `has_token_data` false; remaining weights scale to 1.0.
- **Per-Session DB Revision**: `get_vscdb_mtime` on AI-related `state.vscdb` rows; hash change only invalidates cache.
- **Cross-machine cache isolation**: `(source_machine, session_id)` dedup; `{cache_dir}/records/{tool_name}/{source_machine}/{session_id}.json`.
- **Lazy Placeholder**: scan Placeholder with `project_path` only; `orchestrator` filter/sample then `ensure_parsed`.

## 6. Interaction Principles

- Default personal use
- Default positive feedback
- Default no horizontal comparison
- Default no org labels
- Default "how to improve"

## 7. Engineering Design

Personal edition follows **strict layered personal main chain** (architecture: `ARCHITECTURE_PRINCIPLES.md`).

Boundaries:

- Freeze boundaries: `ai-growth-mirror-dev` -> `references/value_recovery_inventory.md`
- No removal of frozen main-chain without new explicit user confirmation

### 7.1 Layer Placement

| Layer | Key Files | Role |
|---|---|---|
| Adapter | `cli.py` | Parse CLI; call application |
| Application | `orchestrator.py`, `personal_report_service.py`, `report_view.py`, `html_render.py`, `growth_plan.py`, `summary_payload.py`, `label_catalogs.py` | Full personal report pipeline |
| Domain | `domain/common/contracts.py`, `domain/session/*`, `domain/ingestion/*`, `domain/signals/*`, `domain/growth/*` | Pure models, enums, parsers, aggregate |
| Infrastructure | `infra/readers/*`, `infra/extractors/*`, `infra/llm/*`, `infra/cache/store.py`, `infra/snapshots.py`, `infra/i18n/catalog.py`, `infra/enrichers/asset.py` | I/O, LLM, cache, snapshots, i18n adapter |
| Assets | `assets/templates/*.j2`, `assets/i18n/*.yaml`, `assets/prompts/*` | Templates, UI labels, LLM prompts |

### 7.2 Main Chain File Index

- `application/orchestrator.py` - `generate_report_artifacts` / `collect_sessions`
- `domain/common/contracts.py` - gateways and DTOs
- `domain/session/scope.py`, `domain/session/tool_registry.py`
- `domain/ingestion/model.py`
- `domain/growth/coaching.py`, `domain/growth/planning.py`
- `domain/signals/payloads.py`
- `application/report_view.py`, `application/summary_payload.py`, `application/html_render.py`
- `infra/i18n/catalog.py`
- `assets/templates/report.html.j2`
- `assets/i18n/*.yaml`
- `cli.py`

### 7.3 Static Asset Constraints

- Prompts: `assets/prompts/` (`session_read`, `prompt_lens`, `growth_coach`)
- Partials: `assets/prompts/_partials/`
- UI labels: `assets/i18n/`
- HTML: `assets/templates/`
- i18n via `label_catalogs.py` + `infra/i18n/catalog.py`; `html_render.py` preloaded catalog only
- Prompt JSON -> explicit DTO first (`domain/signals/payloads.py`, etc.)
- `assets/prompts/**/bak/` local backup only

### 7.4 Main Chain Boundaries

1. `collect_sessions`: `SessionRecord` only
2. `extract_session_reads_batch` / heuristic batch: `SessionRead` only
3. `aggregate`: pure `GrowthProfile`
4. `generate_growth_guidance`: LLM coaching -> `CoachingContent`
5. `report_view.py`: display DTO and sections; `html_render.py`: HTML only
6. Write, sidecar, share, snapshot: `personal_report_service.py` + infra

### 7.5 Layer Convergence (ongoing)

1. Product naming and page semantics (done)
2. Application owns write and coaching orchestration (done)
3. Label catalog injected; html_render no direct YAML (done)
4. Six-axis radar + style + gaps + trend (done main chain)
5. Domain without display copy; application i18n (ongoing)
6. Share surface (done: `ai-growth-mirror-share.html`)
7. HTML in `html_render.py` (done)
8. Unit tests (ongoing: `pytest tests/unit -q --tb=no`)
9. redact / escaping four outputs (done)

## 8. Acceptance Criteria

- No employee / enterprise / performance / review semantics on page
- Default output `ai-growth-mirror.html`
- Page title AI Growth Mirror
- Main report title Collaboration Evolution Report (This Period)
- Exemplar block "method retention" semantics
- Persona block "style lens" semantics
- CLI personal growth mirror main chain only
- Prompt dirs: `session_read / prompt_lens / growth_coach` only
- Unit tests pass

## Revision History
- 2026-05-25: Initial personal growth detailed design authority.
- 2026-05-27: Stage/index fields align `growth_level` / `mirror_score`; five-axis field cleanup.
- 2026-05-27: Strict layering; application orchestrates personal report; i18n via `label_catalogs.py` + `infra/i18n/catalog.py`.
- 2026-06-07: Growth base aligned v0.8 **six axes** (`intent_clarity` -> `collaboration_framing`, add `agentic_system`); Section 5.2, trend/compare, deficit merge keys synced.
- 2026-05-27: Share card external-ready; main report full nav; Prompt coach real samples and rewrites.
- 2026-05-27: HTML in `html_render.py`; nav order matches README; remove old product surface wording.
- 2026-05-29: Public Wrapped Hero/usage/rhythm copy and color semantics aligned; doc governance backup update.
