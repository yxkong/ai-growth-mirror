from pathlib import Path

from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.infra.readers.base import DeferredSessionRecord
from ai_growth_mirror.domain.signals.model import SessionRead
from ai_growth_mirror.application.orchestrator import (
    GenerateReportRequest,
    _parse_placeholder_sessions,
    generate_report_artifacts,
)


def _make_session(session_id: str) -> SessionRecord:
    return SessionRecord(
        session_id=session_id,
        tool_name="codex",
        project_path="D:/repo/demo",
        start_time="2026-05-20T09:00:00+00:00",
        end_time="2026-05-20T10:00:00+00:00",
        duration_minutes=60,
        first_prompt="目标：修复接口错误。相关文件：handler.py。约束：不要改 API 契约。验收：pytest 通过。",
        user_message_count=6,
        assistant_message_count=8,
        tool_counts={"read": 8, "edit": 2, "bash": 3},
        files_modified=2,
        lines_added=20,
        lines_removed=3,
        languages={"Python": 2},
        user_message_timestamps=["2026-05-20T09:00:00+00:00"],
        message_hours=[9],
        uses_subagent=False,
        uses_mcp=False,
        uses_web_search=False,
        uses_web_fetch=False,
        autonomous_chain_lengths=[4, 3, 2],
        has_verification_behavior=True,
        has_test_commands=True,
        prompt_word_count=18,
        prompt_has_constraint=True,
        prompt_has_code_context=True,
    )


def _make_facets(session_id: str) -> SessionRead:
    from ai_growth_mirror.domain.signals.model import PromptLensScores

    return SessionRead(
        session_id=session_id,
        tool_name="codex",
        delivery_outcome="fully_achieved",
        support_value="very_helpful",
        confidence="high",
        session_takeaway="修复接口错误并完成验证。",
        work_intent_mix={"implement_feature": 1},
        key_gain="completed_implementation",
        prompt_lens=PromptLensScores(
            source="llm",
            coverage="full",
            evaluated_user_messages=6,
            context_provision=60,
            request_specificity=58,
            scope_management=62,
            information_timing=50,
            correction_quality=64,
            efficiency_score=59,
        ),
        capability_focus="none",
        capability_depth="incidental",
        work_style="plan_driven",
    )


def test_parse_placeholder_sessions_skips_only_broken_session(caplog):
    import logging

    class Adapter:
        @staticmethod
        def parse_session(raw):
            if raw == "broken":
                raise ValueError("invalid session payload")
            return _make_session(str(raw))

        @staticmethod
        def _enrich_prompt_signals(_session):
            pass

        @staticmethod
        def _enrich_agentic_signals(_session):
            pass

        @staticmethod
        def _enrich_advanced_features(_session):
            pass

        @staticmethod
        def _enrich_task_contract_signals(_session):
            pass

    sessions = []
    for session_id in ("valid", "broken"):
        session = DeferredSessionRecord(session_id=session_id, tool_name="codex")
        session._raw_ref = session_id
        session._adapter = Adapter()
        sessions.append(session)

    with caplog.at_level(logging.WARNING):
        parsed = _parse_placeholder_sessions(sessions, cache=None)

    assert [session.session_id for session in parsed] == ["valid"]
    assert "codex/broken" in caplog.text
    assert "invalid session payload" in caplog.text


def test_generate_report_artifacts_personal_heuristic(monkeypatch, tmp_path: Path):
    from ai_growth_mirror.application import orchestrator as service
    from ai_growth_mirror.domain.growth.scorer import aggregate
    from ai_growth_mirror.config import GrowthMirrorConfig
    from ai_growth_mirror.application.orchestrator import CollectionResult, CollectedAdapterView

    sessions = [_make_session(f"s{i}") for i in range(1, 6)]
    facets = [_make_facets(session.session_id) for session in sessions]
    stats = aggregate(sessions, facets, tool_name="codex")
    captured = {}

    def fake_collect_sessions(**_kwargs):
        return CollectionResult(
            sessions=sessions,
            adapters=[type("Adapter", (), {"tool_name": "codex", "display_name": "Codex CLI"})()],
            adapter_views=[CollectedAdapterView(tool_name="codex", display_name="Codex CLI", session_count=5)],
            display_name="Codex CLI",
        )

    def fake_generate_personal_report(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(service.GrowthMirrorConfig, "load", classmethod(lambda cls, path=None: GrowthMirrorConfig()))
    monkeypatch.setattr(service, "collect_sessions", fake_collect_sessions)
    monkeypatch.setattr(service, "build_heuristic_session_reads_batch", lambda sessions, language, max_sessions, min_quality="medium": (facets, len(sessions)))
    monkeypatch.setattr(service, "aggregate", lambda sessions, all_facets, tool_name, agent_asset=None: stats)
    monkeypatch.setattr(service, "generate_personal_report", fake_generate_personal_report)

    result = generate_report_artifacts(
        GenerateReportRequest(
            tools=["codex"],
            output_path=tmp_path / "ai-growth-mirror.html",
            session_read_mode="heuristic",
        )
    )

    assert result.display_name == "Codex CLI"
    assert result.session_count == 5
    assert result.session_read_count == 5
    assert result.session_read_mode == "heuristic"
    assert captured["tool_display_name"] == "Codex CLI"
    assert captured["output_path"].name == "ai-growth-mirror.html"
    assert captured["sources_summary"]
