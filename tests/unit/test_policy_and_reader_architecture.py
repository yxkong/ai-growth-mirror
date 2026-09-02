"""Architecture guards for the v1.0.2 DDD and single-truth contracts."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from ai_growth_mirror.domain.growth.assessment_policy import AXIS_WEIGHTS
from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.infra.readers.catalog import (
    ADAPTER_BY_NAME,
    TOOL_ALIASES,
    TOOL_CHOICES,
)
from ai_growth_mirror.infra.readers.diagnostics import ReaderDiagnostics


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_domain_session_record_has_no_infrastructure_state() -> None:
    field_names = {field.name for field in fields(SessionRecord)}
    assert field_names.isdisjoint({"_adapter", "_raw_ref", "_cache", "_is_placeholder"})
    assert not hasattr(SessionRecord, "ensure_parsed")
    source = _source("ai_growth_mirror/domain/session/model.py")
    assert all(token not in source for token in ("_adapter", "_raw_ref", "_is_placeholder"))


def test_capability_projection_contains_no_second_scoring_formula() -> None:
    source = _source("ai_growth_mirror/domain/growth/capability.py")
    tree = ast.parse(source)
    referenced_attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    raw_volume_fields = {
        "total_token_volume",
        "total_files_modified",
        "total_commits",
        "total_tool_calls",
        "subagent_session_count",
    }
    assert referenced_attributes.isdisjoint(raw_volume_fields)
    assert "agentic_sub_scores" in referenced_attributes
    assert "radar_axes" in referenced_attributes


def test_snapshot_comparison_imports_policy_weights() -> None:
    source = _source("ai_growth_mirror/domain/snapshots/comparison.py")
    tree = ast.parse(source)
    assignments = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }
    assert "AXIS_WEIGHTS" not in assignments
    assert "from ..growth.assessment_policy import AXIS_WEIGHTS" in source


def test_reader_choices_and_aliases_project_one_catalog() -> None:
    assert TOOL_CHOICES == ("all", *TOOL_ALIASES)
    assert {value for value in TOOL_ALIASES.values()} == set(ADAPTER_BY_NAME)
    assert set(AXIS_WEIGHTS) == {
        "collaboration_framing",
        "execution_driving",
        "implementation_depth",
        "delivery_closure",
        "adaptive_recovery",
        "agentic_system",
    }


def test_reader_diagnostics_projection_is_structured_and_content_free() -> None:
    payload = ReaderDiagnostics(detected=2, parsed=1, corrupt=1).as_dict()
    assert payload == {
        "detected": 2,
        "parsed": 1,
        "skipped": 0,
        "corrupt": 1,
        "schema_mismatch": 0,
        "orphan": 0,
        "unreadable": 0,
    }
