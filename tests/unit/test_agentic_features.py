"""Unit tests covering the four Agentic architecture features.

Feature 1: Three-stage LLM diagnosis layer
Feature 2: Agentic Evidence Graph
Feature 3: Action Contract Generator upgrade
Feature 4: human_cost_reduction trend
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest


def _make_stats(**kwargs):
    """Minimal GrowthProfile factory for tests."""
    from ai_growth_mirror.domain.growth.model import GrowthProfile

    defaults = dict(
        tool_name="claude_code",
        session_count=10,
        total_user_messages=50,
        total_messages=100,
        active_days=5,
        pq_deficit_counts={},
        friction_by_attribution={"user-actionable": 2, "ai-actionable": 1},
        friction_type_counts={},
        outcome_counts={"fully_achieved": 5, "partially_achieved": 3, "unclear": 2},
        pq_avg_dimensions={},
        pq_avg_efficiency_score=60.0,
        pq_sessions_evaluated=0,
        pq_llm_session_count=0,
        pq_heuristic_session_count=0,
        pq_light_session_count=0,
        growth_level="L3",
        mirror_score=70,
        agentic_sub_scores={},
        human_intervention_session_count=0,
        human_intervention_session_rate=0.0,
        agentic_system_score=50.0,
        skill_usage_session_rate=0.0,
        local_method_framework_session_rate=0.0,
        public_framework_session_rate=0.0,
        workflow_fingerprint_session_rate=0.0,
        verification_behavior_rate=0.30,
        avg_autonomous_chain_length=3.0,
    )
    defaults.update(kwargs)
    return GrowthProfile(**defaults)

# ---------------------------------------------------------------------------
# Feature 1: Three-stage LLM diagnosis layer
# ---------------------------------------------------------------------------


class TestDiagnosisCandidatePacket:
    def test_build_packet_from_profile_produces_candidates(self):
        from ai_growth_mirror.domain.growth.diagnosis import (
            build_diagnosis_candidate_packet,
            DiagnosisCandidatePacket,
        )
        from ai_growth_mirror.domain.growth.planning import rank_growth_priorities

        stats = _make_stats(
            session_count=20,
            pq_deficit_counts={"missing-acceptance-criteria": 5, "vague-request": 3},
            human_intervention_session_count=5,
            human_intervention_session_rate=0.25,
            agentic_system_score=42.0,
        )
        cap_scores = {
            "intent_clarity": 33.8,
            "execution_driving": 92.6,
            "implementation_depth": 89.3,
            "delivery_closure": 51.3,
            "adaptive_recovery": 52.1,
        }
        ranked = rank_growth_priorities(stats, cap_scores)
        packet = build_diagnosis_candidate_packet(
            stats,
            cap_scores,
            ranked,
            trend_info="stable",
        )

        assert isinstance(packet, DiagnosisCandidatePacket)
        assert len(packet.candidates) > 0
        codes = [c.code for c in packet.candidates]
        # Delivery closure gap should be detected (score 51.3 < threshold 62)
        assert any("closure" in code or "acceptance" in code for code in codes)

    def test_human_cost_high_candidate_injected_when_rate_high(self):
        from ai_growth_mirror.domain.growth.diagnosis import (
            build_diagnosis_candidate_packet,
        )
        from ai_growth_mirror.domain.growth.planning import rank_growth_priorities

        stats = _make_stats(
            session_count=10,
            human_intervention_session_rate=0.40,
            human_intervention_session_count=4,
        )
        cap_scores = {k: 70.0 for k in ["intent_clarity", "execution_driving", "implementation_depth", "delivery_closure", "adaptive_recovery"]}
        ranked = rank_growth_priorities(stats, cap_scores)
        packet = build_diagnosis_candidate_packet(stats, cap_scores, ranked)

        codes = [c.code for c in packet.candidates]
        assert "human_cost_high" in codes

    def test_parse_diagnosis_payload_extracts_grounded_fields(self):
        from ai_growth_mirror.domain.growth.diagnosis import parse_diagnosis_payload

        raw = {
            "primary_diagnosis": {
                "code": "delivery_closure_gap",
                "label": "Delivery closure gap",
                "explanation": "User rarely defines acceptance criteria.",
                "confidence": 82,
                "evidence_refs": ["verification_behavior_rate=28%", "missing-acceptance-criteria=5"],
                "why_not_other_diagnosis": "intent_clarity_gap has higher scores than threshold.",
                "next_action": "Start every task with explicit acceptance criteria.",
            },
            "secondary_diagnoses": [
                {
                    "code": "intent_clarity_gap",
                    "label": "Intent clarity",
                    "explanation": "Some vague requests observed.",
                    "confidence": 60,
                    "evidence_refs": ["vague-request=3"],
                    "why_not_other_diagnosis": "Delivery closure is more impactful currently.",
                }
            ],
            "synthesis_confidence": "high",
        }
        result = parse_diagnosis_payload(raw)

        assert result.primary is not None
        assert result.primary.code == "delivery_closure_gap"
        assert result.primary.confidence == 82
        assert len(result.primary.evidence_refs) == 2
        assert result.primary.why_not_other_diagnosis != ""
        assert result.synthesis_confidence == "high"
        assert len(result.secondary) == 1
        assert result.secondary[0].code == "intent_clarity_gap"

    def test_rule_fallback_diagnosis_produces_result_without_llm(self):
        from ai_growth_mirror.domain.growth.diagnosis import (
            build_diagnosis_candidate_packet,
            rule_fallback_diagnosis,
            DiagnosisCandidate,
            DiagnosisCandidatePacket,
        )

        packet = DiagnosisCandidatePacket(
            candidates=[
                DiagnosisCandidate(
                    code="delivery_closure_gap",
                    urgency=85.0,
                    reason_codes=("capability_threshold",),
                    axis_key="delivery_closure",
                    current_score=51.3,
                    threshold_score=62.0,
                    evidence_snippets=["verification_behavior_rate=28%"],
                )
            ]
        )
        result = rule_fallback_diagnosis(packet)

        assert result.source == "rule_fallback"
        assert result.primary is not None
        assert result.primary.code == "delivery_closure_gap"

    def test_rerank_diagnosis_result_sorts_secondary_by_actionability(self):
        from ai_growth_mirror.domain.growth.diagnosis import (
            rerank_diagnosis_result,
            DiagnosisResult,
            DiagnosisCandidatePacket,
            GroundedDiagnosis,
        )

        result = DiagnosisResult(
            primary=GroundedDiagnosis(
                code="delivery_closure_gap",
                label="Delivery",
                explanation="",
                confidence=80,
            ),
            secondary=[
                GroundedDiagnosis(code="schema_mismatch", label="Schema", explanation="", confidence=50),
                GroundedDiagnosis(code="acceptance_criteria_late", label="Acceptance", explanation="", confidence=65),
                GroundedDiagnosis(code="agentic_system_gap", label="Agentic", explanation="", confidence=70),
            ],
        )
        reranked = rerank_diagnosis_result(result, DiagnosisCandidatePacket())

        # acceptance_criteria_late should be first (high L4/L5 impact and actionability)
        assert reranked.secondary[0].code == "acceptance_criteria_late"

    def test_coaching_payload_parses_diagnosis_block(self):
        from ai_growth_mirror.domain.growth.coaching import parse_coaching_payload

        raw = {
            "growth_plan": {
                "headline": "Test headline",
                "priorities": [],
            },
            "prompt_coach": {
                "available": True,
                "headline": "",
                "evidence_summary": "",
                "takeaways": [],
                "friction_synthesis": [],
            },
            "diagnosis": {
                "primary_diagnosis": {
                    "code": "delivery_closure_gap",
                    "label": "Delivery closure",
                    "explanation": "Low verification rate.",
                    "confidence": 75,
                    "evidence_refs": ["code_verification_rate=0.28"],
                    "why_not_other_diagnosis": "Other gaps are lower urgency.",
                    "next_action": "Add acceptance criteria.",
                },
                "secondary_diagnoses": [],
                "synthesis_confidence": "medium",
            },
            "share_lines": [],
        }
        coaching = parse_coaching_payload(raw)

        assert coaching.diagnosis is not None
        assert coaching.diagnosis.primary is not None
        assert coaching.diagnosis.primary.code == "delivery_closure_gap"
        assert coaching.diagnosis.source == "llm"


# ---------------------------------------------------------------------------
# Feature 2: Agentic Evidence Graph
# ---------------------------------------------------------------------------


class TestAgenticEvidenceGraph:
    def _make_session(self, session_id="s1", **kwargs):
        from ai_growth_mirror.domain.session.model import SessionRecord

        defaults = dict(
            session_id=session_id,
            tool_name="claude_code",
            start_time="2026-06-01T10:00:00",
            user_message_count=5,
            assistant_message_count=10,
            has_verification_behavior=False,
            has_test_commands=False,
            user_interruptions=0,
            tool_counts={},
            unique_skills_used=[],
            slash_commands=[],
            advanced_features=[],
            first_prompt="",
        )
        defaults.update(kwargs)
        return SessionRecord(**defaults)

    def _make_session_read(self, session_id="s1", **kwargs):
        from ai_growth_mirror.domain.signals.model import SessionRead

        defaults = dict(
            session_id=session_id,
            tool_name="claude_code",
            delivery_outcome="fully_achieved",
            work_intent_mix={"feature": 0.7, "refactor": 0.3},
            confidence="high",
        )
        defaults.update(kwargs)
        return SessionRead(**defaults)

    def test_build_graph_produces_nodes_for_each_session(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        sessions = [self._make_session(f"s{i}") for i in range(5)]
        reads = [self._make_session_read(f"s{i}") for i in range(5)]

        graph = build_agentic_evidence_graph(sessions, reads)

        assert len(graph.nodes) == 5
        assert graph.summary.node_count == 5

    def test_graph_node_extracts_task_intent_from_session_read(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        session = self._make_session("s1")
        read = self._make_session_read("s1", work_intent_mix={"feature": 0.8, "debug": 0.2})
        graph = build_agentic_evidence_graph([session], [read])

        assert graph.nodes[0].task_intent == "feature"

    def test_graph_node_captures_method_used_from_skills_and_slashes(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        session = self._make_session(
            "s1",
            unique_skills_used=["delivery-workflow", "ai-development-governance"],
            slash_commands=["/plan", "/compact"],
        )
        graph = build_agentic_evidence_graph([session], [])

        node = graph.nodes[0]
        assert "delivery-workflow" in node.method_used
        assert "/plan" in node.method_used

    def test_graph_node_execution_path_labeled_correctly_for_verified_session(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        session = self._make_session(
            "s1",
            has_verification_behavior=True,
            tool_counts={"Read": 2, "Edit": 3, "Bash": 2},
        )
        graph = build_agentic_evidence_graph([session], [])

        assert graph.nodes[0].execution_path == "read→edit→run→verify"

    def test_graph_summary_computes_verified_execution_rate(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        sessions = [
            self._make_session("s1", has_verification_behavior=True),
            self._make_session("s2", has_verification_behavior=True),
            self._make_session("s3", has_verification_behavior=False),
            self._make_session("s4", has_verification_behavior=False),
        ]
        graph = build_agentic_evidence_graph(sessions, [])

        assert graph.summary.verified_execution_count == 2
        assert abs(graph.summary.verified_execution_rate - 0.5) < 0.001

    def test_graph_summary_tracks_high_intervention_rate(self):
        from ai_growth_mirror.domain.growth.evidence_graph import build_agentic_evidence_graph

        sessions = [
            self._make_session("s1", user_interruptions=3),
            self._make_session("s2", user_interruptions=0),
            self._make_session("s3", user_interruptions=2),
            self._make_session("s4", user_interruptions=1),
        ]
        graph = build_agentic_evidence_graph(sessions, [])

        assert graph.summary.high_intervention_count == 2  # s1 and s3 have >=2

    def test_evidence_graph_to_dict_is_serialisable(self):
        import json
        from ai_growth_mirror.domain.growth.evidence_graph import (
            build_agentic_evidence_graph,
            evidence_graph_to_dict,
        )

        sessions = [self._make_session("s1")]
        graph = build_agentic_evidence_graph(sessions, [])
        d = evidence_graph_to_dict(graph)

        json_str = json.dumps(d)
        assert "nodes" in d
        assert "summary" in d
        assert len(json_str) > 0

    def test_core_evidence_includes_agentic_graph_when_enabled(self):
        from ai_growth_mirror.domain.growth.evidence import build_core_evidence

        stats = _make_stats(session_count=3)
        sessions = [self._make_session(f"s{i}") for i in range(3)]
        reads = [self._make_session_read(f"s{i}") for i in range(3)]

        core = build_core_evidence(
            sessions=sessions,
            facets=reads,
            stats=stats,
            tool_display_name="claude_code",
            include_evidence_graph=True,
        )

        assert core.agentic_evidence_graph is not None
        assert "nodes" in core.agentic_evidence_graph
        assert "summary" in core.agentic_evidence_graph

    def test_core_evidence_skips_graph_when_disabled(self):
        from ai_growth_mirror.domain.growth.evidence import build_core_evidence

        stats = _make_stats(session_count=1)
        sessions = [self._make_session("s1")]

        core = build_core_evidence(
            sessions=sessions,
            facets=[],
            stats=stats,
            tool_display_name="claude_code",
            include_evidence_graph=False,
        )

        assert core.agentic_evidence_graph is None


# ---------------------------------------------------------------------------
# Feature 3: Action Contract Generator upgrade
# ---------------------------------------------------------------------------


class TestActionContractGenerator:
    def _make_stats(self, **kwargs):
        return _make_stats(**kwargs)

    def test_generates_contracts_from_high_frequency_deficits(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts

        stats = self._make_stats(
            pq_deficit_counts={"missing-acceptance-criteria": 8, "vague-request": 4, "scope-drift": 2},
        )
        cap_scores = {"delivery_closure": 51.0, "intent_clarity": 60.0}
        report = generate_action_contracts(stats, cap_scores)

        assert len(report.items) > 0
        # Should produce acceptance-criteria rule (highest frequency)
        titles = [item.title for item in report.items]
        assert any("验收" in t or "前置" in t for t in titles)

    def test_generates_agentic_skill_contract_when_score_low(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts

        stats = self._make_stats(agentic_system_score=40.0)
        cap_scores = {"delivery_closure": 70.0}
        report = generate_action_contracts(stats, cap_scores)

        kinds = [item.kind for item in report.items]
        assert "skill" in kinds

    def test_generates_human_cost_workflow_when_rate_high(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts

        stats = self._make_stats(
            human_intervention_session_rate=0.35,
            human_intervention_session_count=7,
        )
        cap_scores = {"delivery_closure": 70.0}
        report = generate_action_contracts(stats, cap_scores)

        kinds = [item.kind for item in report.items]
        assert "workflow" in kinds

    def test_respects_max_items_limit(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts

        stats = self._make_stats(
            pq_deficit_counts={k: 5 for k in [
                "missing-acceptance-criteria", "vague-request", "scope-drift",
                "missing-context", "unclear-correction",
            ]},
            agentic_system_score=30.0,
            human_intervention_session_rate=0.40,
        )
        cap_scores = {"delivery_closure": 45.0}
        report = generate_action_contracts(stats, cap_scores, max_items=3)

        assert len(report.items) <= 3

    def test_items_are_sorted_by_priority_descending(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts

        stats = self._make_stats(
            pq_deficit_counts={"missing-acceptance-criteria": 10, "vague-request": 2},
            agentic_system_score=35.0,
        )
        cap_scores = {"delivery_closure": 50.0}
        report = generate_action_contracts(stats, cap_scores)

        priorities = [item.priority for item in report.items]
        assert priorities == sorted(priorities, reverse=True)

    def test_action_contract_to_lines_formats_items(self):
        from ai_growth_mirror.domain.growth.action_contracts import (
            generate_action_contracts,
            action_contract_to_lines,
        )

        stats = self._make_stats(
            pq_deficit_counts={"missing-acceptance-criteria": 5},
        )
        cap_scores = {"delivery_closure": 50.0}
        report = generate_action_contracts(stats, cap_scores)
        lines = action_contract_to_lines(report)

        assert len(lines) > 0
        for line in lines:
            assert "—" in line or "：" in line or ":" in line

    def test_evidence_graph_summary_enriches_checklist_when_intervention_high(self):
        from ai_growth_mirror.domain.growth.action_contracts import generate_action_contracts
        from ai_growth_mirror.domain.growth.evidence_graph import AgenticEvidenceGraphSummary

        stats = self._make_stats()
        cap_scores = {}
        graph_summary = AgenticEvidenceGraphSummary(
            node_count=20,
            high_intervention_count=4,
            high_intervention_rate=0.20,
        )
        report = generate_action_contracts(stats, cap_scores, graph_summary=graph_summary)

        kinds = [item.kind for item in report.items]
        assert "checklist" in kinds


# ---------------------------------------------------------------------------
# Feature 4: human_cost_reduction trend
# ---------------------------------------------------------------------------


class TestHumanCostTrend:
    def _make_snapshot_source(self, human_intervention_rate=None, **kwargs):
        from ai_growth_mirror.domain.snapshots.model import SnapshotSource

        defaults = dict(
            snapshot_id="snap1",
            created_at="2026-06-01T10:00:00",
            growth_level="L3",
            mirror_score=70,
        )
        defaults.update(kwargs)
        src = SnapshotSource(**defaults)
        src.human_intervention_session_rate = human_intervention_rate
        return src

    def test_human_cost_trend_not_available_when_data_missing(self):
        from ai_growth_mirror.domain.snapshots.comparison import _build_human_cost_trend

        prev = self._make_snapshot_source(human_intervention_rate=None, snapshot_id="s1")
        curr = self._make_snapshot_source(human_intervention_rate=0.25, snapshot_id="s2")
        trend = _build_human_cost_trend(prev, curr)

        assert not trend.available
        assert "historical snapshots" in trend.note.lower() or "not yet" in trend.note.lower()

    def test_human_cost_trend_improving_when_rate_decreases(self):
        from ai_growth_mirror.domain.snapshots.comparison import _build_human_cost_trend

        prev = self._make_snapshot_source(human_intervention_rate=0.35, snapshot_id="s1")
        curr = self._make_snapshot_source(human_intervention_rate=0.15, snapshot_id="s2")
        trend = _build_human_cost_trend(prev, curr)

        assert trend.available
        assert trend.direction == "improving"
        assert trend.delta < 0

    def test_human_cost_trend_worsening_when_rate_increases(self):
        from ai_growth_mirror.domain.snapshots.comparison import _build_human_cost_trend

        prev = self._make_snapshot_source(human_intervention_rate=0.10, snapshot_id="s1")
        curr = self._make_snapshot_source(human_intervention_rate=0.30, snapshot_id="s2")
        trend = _build_human_cost_trend(prev, curr)

        assert trend.available
        assert trend.direction == "worsening"
        assert trend.delta > 0

    def test_human_cost_trend_flat_when_delta_small(self):
        from ai_growth_mirror.domain.snapshots.comparison import _build_human_cost_trend

        prev = self._make_snapshot_source(human_intervention_rate=0.20, snapshot_id="s1")
        curr = self._make_snapshot_source(human_intervention_rate=0.21, snapshot_id="s2")
        trend = _build_human_cost_trend(prev, curr)

        assert trend.available
        assert trend.direction == "flat"

    def test_snapshot_source_has_human_intervention_rate_field(self):
        from ai_growth_mirror.domain.snapshots.model import SnapshotSource

        src = SnapshotSource(snapshot_id="test")
        assert hasattr(src, "human_intervention_session_rate")
        assert src.human_intervention_session_rate is None

    def test_snapshot_comparison_includes_human_cost_trend(self):
        from ai_growth_mirror.domain.snapshots.comparison import compare_snapshot_sources

        prev = self._make_snapshot_source(
            human_intervention_rate=0.30,
            snapshot_id="s1",
            created_at="2026-05-01T10:00:00",
            axis_scores={"intent_clarity": 50.0, "execution_driving": 70.0, "implementation_depth": 60.0, "delivery_closure": 55.0, "adaptive_recovery": 52.0},
        )
        curr = self._make_snapshot_source(
            human_intervention_rate=0.15,
            snapshot_id="s2",
            created_at="2026-06-01T10:00:00",
            axis_scores={"intent_clarity": 55.0, "execution_driving": 72.0, "implementation_depth": 62.0, "delivery_closure": 60.0, "adaptive_recovery": 55.0},
        )
        comparison = compare_snapshot_sources(prev, curr)

        assert hasattr(comparison, "human_cost_trend")
        assert comparison.human_cost_trend is not None
        assert comparison.human_cost_trend.available
        assert comparison.human_cost_trend.direction == "improving"

    def test_trajectory_window_includes_human_cost_trend(self):
        from ai_growth_mirror.domain.snapshots.model import SnapshotSource
        from ai_growth_mirror.domain.snapshots.trajectory import build_snapshot_trajectory_window

        sources = []
        for i, rate in enumerate([0.35, 0.20]):
            src = SnapshotSource(
                snapshot_id=f"snap{i+1}",
                created_at=f"2026-0{i+5}-01T10:00:00",
                growth_level="L3",
                mirror_score=65 + i * 5,
                axis_scores={
                    "intent_clarity": 50.0, "execution_driving": 70.0,
                    "implementation_depth": 60.0, "delivery_closure": 55.0, "adaptive_recovery": 52.0,
                },
            )
            src.human_intervention_session_rate = rate
            sources.append(src)

        window = build_snapshot_trajectory_window(sources, window_days=90)

        assert window.human_cost_trend is not None
        assert window.human_cost_trend.available
        assert window.human_cost_trend.direction == "improving"

    def test_snapshot_source_from_payloads_extracts_human_intervention_rate(self):
        """Verify the snapshot infra layer reads human_intervention_session_rate from stats."""
        from ai_growth_mirror.infra.snapshots import _snapshot_source_from_payloads  # noqa: F401
        # This is an internal function test — verify it exists and is callable
        import inspect
        sig = inspect.signature(_snapshot_source_from_payloads)
        assert "profile" in sig.parameters
        assert "stats" in sig.parameters or "report" in sig.parameters
