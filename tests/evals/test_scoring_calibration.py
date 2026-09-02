"""Versioned scorer invariants over synthetic, reviewable evidence."""

from __future__ import annotations

import json
from pathlib import Path

from ai_growth_mirror.domain.growth.scorer import aggregate
from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.signals.model import SessionRead

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "scoring_calibration_v1.json"


def _load_cases() -> dict[str, dict]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["calibration_schema_version"] == "1.0"
    return {case["id"]: case for case in payload["cases"]}


def _profile(case_id: str):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    case = _load_cases()[case_id]
    base_session = payload.get("base_session", {})
    base_read = payload.get("base_session_read", {})
    sessions = [
        SessionRecord.from_dict({**base_session, **item})
        for item in case.get("sessions", [])
    ]
    reads = [
        SessionRead.from_dict({**base_read, **item})
        for item in case.get("session_reads", [])
    ]
    return aggregate(sessions, reads, tool_name="calibration")


def _axis(profile, key: str) -> float:
    return float(profile.agentic_sub_scores.get(key, 0.0))


def test_empty_evidence_does_not_fabricate_scores() -> None:
    profile = _profile("empty-evidence")
    assert profile.session_count == 0
    assert profile.radar_axes == []
    assert profile.mirror_score == 0


def test_effective_contract_improves_collaboration_framing() -> None:
    baseline = _profile("contract-baseline")
    effective = _profile("effective-contract")
    assert effective.effective_contract_rate == 1.0
    assert _axis(effective, "collaboration_framing") > _axis(
        baseline, "collaboration_framing"
    )


def test_verification_evidence_improves_delivery_closure() -> None:
    unverified = _profile("unverified-delivery")
    verified = _profile("verified-delivery")
    assert verified.verification_behavior_rate == 1.0
    assert _axis(verified, "delivery_closure") > _axis(unverified, "delivery_closure")


def test_missing_usage_is_not_scored_as_explicit_zero_usage() -> None:
    missing = _profile("missing-usage")
    explicit_zero = _profile("explicit-zero-usage")
    assert _axis(missing, "implementation_depth") >= _axis(
        explicit_zero, "implementation_depth"
    )


def test_environmental_recovery_is_not_off_track() -> None:
    profile = _profile("environmental-recovery")
    assert profile.friction_type_counts.get("environmental-recovery") == 1
    assert profile.friction_type_counts.get("off-track", 0) == 0
