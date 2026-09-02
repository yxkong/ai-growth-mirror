---
title: v1.0.1 Unified Trust Boundary and Resilient Persistence ADR
status: mirror
document_type: adr_mirror
canonical_path: docs/design/ADR-v1.0.1-trust-resilience.md
spec_id: SPEC-GROWTH-MIRROR-1.0.1-HARDENING
spec_version: 1.0.5
version: 1.0.4
decision_status: accepted
created: 2026-09-01
updated: 2026-09-02
related:
  - path: docs/design/ADR-v1.0.1-trust-resilience.md
    role: canonical_zh
---

# ADR: v1.0.1 Unified Trust Boundary and Resilient Persistence

Chinese canonical version: [ADR-v1.0.1-trust-resilience.md](../../design/ADR-v1.0.1-trust-resilience.md)

## Status

- DEC-001: unified outbound LLM user-prompt boundary — accepted
- DEC-002: one atomic I/O primitive and a hard snapshot ownership cut — accepted
- DEC-003: synthetic invariant calibration plus locked cross-platform CI — accepted
- DEC-004: canonical + checked mirror and one domain snapshot projection — accepted

## Context and decision

Per-call redaction, per-module temporary-write helpers, an infra module that assembles application views, and prose snapshot tests would create parallel sources of truth. We therefore choose:

1. The LLM execution layer sanitizes every user prompt exactly once. Call sites retain data minimization, request-local project aliases and explicit untrusted-evidence delimiters. Static system prompts are not rewritten.
2. One same-directory temporary-file/replace primitive owns text and JSON publication. POSIX also uses fsync; Windows uses flush+close+replace after runtime evidence showed an unacceptable per-file fsync delay. Snapshot view assembly moves to the application layer; infra retains persistence and loading. The old reverse dependency is removed without a compatibility shell.
3. A versioned synthetic fixture asserts scoring invariants through the sole `aggregate` entry point. CI uses locked uv installs on Ubuntu/Windows and Python 3.12/3.13, then runs unit + eval tests and builds distributions.
4. Existing owners remain authoritative: Chinese active contracts are canonical, English files are checked mirrors, snapshot business projection lives once in domain, and CI tests verify pin structure without copying the current SHA. No separate registry or compatibility alias is introduced.

These decisions prioritize trustworthy negative evidence and single extension points while preserving Product v1.0.1 / Cache Schema 1.0, public CLI commands, artifact shapes and cache paths.

## Alternatives rejected

- Per-call redaction: smaller patches but no provable coverage for future LLM features.
- Per-module atomic helpers: repeated Windows/error semantics and a second source of truth.
- Full report goldens on one Linux version: brittle prose coupling and no Windows/release protection.
- Dual canonical bilingual trees or a new truth registry: conflicts would have no unique owner, or the registry itself would become another projection.

## Security, observability and rollback

Raw-prompt fallback is forbidden. Provider diagnostics contain stable event codes and exception types, not exception/request text. Existing complete files survive failed replacement. Snapshot artifacts remain immutable and are indexed only after complete staging.

Redaction patterns or budgets may be tuned, CI jobs may be split for runtime, and application orchestration may be reverted as a unit, but the unified privacy boundary, atomic-write guarantee, zero infra-to-application allowlist, Windows/Python 3.13 coverage, locked install, calibration and build gates must remain.

## Validation

- AC-001 validates DEC-001.
- AC-004 and AC-005 validate DEC-002.
- AC-006, AC-007 and AC-009 validate DEC-003.
- AC-010 validates DEC-004.

## Revision history

- 2026-09-02: Added DEC-004 and marked this English document as a checked mirror of the Chinese canonical ADR.
- 2026-09-01: Decisions accepted after three design-review rounds.
