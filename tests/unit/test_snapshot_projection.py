"""Single-source contracts for runtime and archived snapshot projections."""

from __future__ import annotations

import ast
from pathlib import Path

from ai_growth_mirror.domain.snapshots.projection import (
    build_actionable_friction_counts,
    topic_from_friction,
)
from ai_growth_mirror.infra.snapshots import snapshot_source_from_payloads


ROOT = Path(__file__).resolve().parents[2]


def test_actionable_friction_projection_covers_all_canonical_aliases() -> None:
    assert build_actionable_friction_counts(
        pq_deficits={
            "vague-request": 1,
            "missing-context": 2,
            "scope-drift": 3,
            "missing-acceptance-criteria": 4,
            "unclear-correction": 5,
        },
        friction_type_counts={
            "fuzzy-intent": 10,
            "ambiguous-request": 20,
            "missing-context": 30,
            "context-gap": 40,
            "context-confusion": 50,
            "scope-creep": 60,
            "goal-drift": 70,
            "missing-acceptance-criteria": 80,
            "incomplete-output": 90,
            "off-track": 100,
            "outdated-context": 110,
            "recurring-pattern": 120,
        },
    ) == {
        "vague_request": 31,
        "missing_context": 122,
        "scope_drift": 133,
        "missing_acceptance_criteria": 174,
        "unclear_correction": 335,
    }


def test_friction_topic_projection_has_one_canonical_mapping() -> None:
    assert topic_from_friction("goal-drift") == "adaptive_recovery"
    assert topic_from_friction("scope-creep") == "execution_driving"
    assert topic_from_friction("unknown") == ""


def test_snapshot_payload_projection_is_a_public_infra_api() -> None:
    source = snapshot_source_from_payloads(
        profile={},
        summary={},
        report={"stats": {"pq_deficit_counts": {"scope-drift": 2}}},
        normalized_summary={},
    )
    assert source.actionable_friction_counts["scope_drift"] == 2


def test_snapshot_projection_rules_are_not_redefined_in_consumers() -> None:
    forbidden = {"_build_actionable_friction_counts", "_topic_from_friction"}
    definitions: list[str] = []
    for relative in (
        "ai_growth_mirror/application/growth_trajectory.py",
        "ai_growth_mirror/infra/snapshots.py",
    ):
        path = ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden:
                definitions.append(f"{relative}:{node.name}")
    assert definitions == []
