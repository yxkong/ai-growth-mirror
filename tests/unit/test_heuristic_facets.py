from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.infra.extractors.heuristic import (
    build_heuristic_session_read_for_session,
    build_heuristic_session_reads_batch,
)


def test_build_heuristic_session_read_for_session_populates_growth_signals():
    session = SessionRecord(
        session_id="codex-1",
        tool_name="codex",
        project_path="D:/repo/demo-workspace",
        start_time="2026-05-20T10:00:00+00:00",
        first_prompt="请先做规划，再实现并验证，相关文件是 src/app.py，验收标准是测试通过。",
        user_message_count=6,
        assistant_message_count=8,
        tool_counts={"read_file": 4, "edit_file": 2, "run_terminal_cmd": 2},
        files_modified=3,
        lines_added=80,
        lines_removed=12,
        has_verification_behavior=True,
        has_test_commands=True,
        prompt_word_count=28,
        prompt_has_constraint=True,
        prompt_has_code_context=True,
        slash_commands=["/plan"],
        top_user_messages=["请先做规划，再实现并验证。"],
        message_hours=[10, 11],
    )

    facets = build_heuristic_session_read_for_session(session, language="zh")

    assert facets.delivery_outcome == "fully_achieved"
    assert facets.support_value == "very_helpful"
    assert facets.work_style == "plan_driven"
    assert facets.key_gain == "verified_delivery"
    assert facets.prompt_lens is not None
    assert facets.prompt_lens.context_provision >= 70
    assert any(point.category == "verify-loop" for point in facets.momentum_signals)


def test_build_heuristic_session_reads_batch_skips_low_signal_sessions():
    eligible = SessionRecord(
        session_id="eligible-1",
        tool_name="codex",
        start_time="2026-05-20T10:00:00+00:00",
        first_prompt="帮我排查 src/main.py 的异常，并在修复后运行 pytest。",
        user_message_count=5,
        assistant_message_count=6,
        prompt_word_count=18,
        prompt_has_code_context=True,
        prompt_has_constraint=True,
        message_hours=[10],
    )
    low_signal = SessionRecord(
        session_id="low-1",
        tool_name="codex",
        start_time="2026-05-20T11:00:00+00:00",
        first_prompt="test",
        user_message_count=1,
        assistant_message_count=1,
        prompt_word_count=1,
        message_hours=[11],
    )

    facets, attempted = build_heuristic_session_reads_batch([eligible, low_signal], language="zh")

    assert attempted == 1
    assert [item.session_id for item in facets] == ["eligible-1"]


def test_build_heuristic_session_read_for_short_session_still_emits_proxy_pq():
    session = SessionRecord(
        session_id="codex-short",
        tool_name="codex",
        start_time="2026-05-20T11:00:00+00:00",
        first_prompt="帮我看下这个报错。",
        user_message_count=1,
        assistant_message_count=1,
        prompt_word_count=8,
        prompt_has_code_context=False,
        prompt_has_constraint=False,
        message_hours=[11],
    )

    facets = build_heuristic_session_read_for_session(session, language="zh")

    assert facets.prompt_lens is not None
    assert facets.prompt_lens.source == "heuristic"
    assert facets.prompt_lens.coverage == "light"
    assert facets.prompt_lens.evaluated_user_messages == 1
