---
title: v1.0.2 Single Assessment Policy and Root-Task ACL ADR
status: mirror
canonical_path: docs/design/ADR-v1.0.2-assessment-policy-and-root-task.md
document_type: adr
spec_id: SPEC-GROWTH-MIRROR-1.0.2-DDD-EXPLAINABLE-ASSESSMENT
spec_version: 1.0.0
version: 1.0.0
decision_status: accepted
created: 2026-09-02
updated: 2026-09-02
related:
  - path: docs/design/ADR-v1.0.2-assessment-policy-and-root-task.md
    role: canonical
---

# ADR: v1.0.2 Single Assessment Policy and Root-Task ACL

Chinese canonical version: [ADR-v1.0.2-assessment-policy-and-root-task.md](../../design/ADR-v1.0.2-assessment-policy-and-root-task.md)

This is a checked English mirror; the linked Chinese ADR is the decision owner.

## Accepted decisions

1. One versioned assessment policy owns axis semantics. Scorer, capability
   projection, snapshot comparison, and reports consume it without copying it.
2. Missing evidence is unavailable. Available evidence is dynamically
   renormalized, and coverage remains user-visible.
3. Raw activity volume does not earn maturity. Verified outcomes, effective
   structure, and opportunity-conditioned recovery do.
4. The analysis unit is the user-visible root task. Descendant sessions roll up
   once rather than becoming independent score samples.
5. DeepSeek Harness and ZCode use versioned, read-only anti-corruption layers.
   Unsupported schemas fail closed and private model-I/O is not a fallback.
6. Reports explain each result through policy version, coverage, component
   contribution, evidence reason codes, and next review action.

Rejected alternatives are parallel formulas, aliases or dual writes, guessing
unknown fields, scoring child sessions independently, parsing reasoning, and
using ZCode model-I/O payloads. Any semantic policy change requires a new policy
version, an ADR, invariance tests, and explicit cross-version comparison rules.
