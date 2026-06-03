import json
from pathlib import Path

from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.signals.model import PromptLensFinding, PromptLensTakeaway, PromptLensScores, SessionRead
from ai_growth_mirror.application.prompt_coach import build_prompt_coach_view
from ai_growth_mirror.infra.readers.cursor import CursorAdapter
from ai_growth_mirror.domain.growth.scorer import aggregate
from ai_growth_mirror.domain.growth.model import GrowthProfile
from ai_growth_mirror.application.growth_plan import build_growth_plan
from ai_growth_mirror.application.personal_report_service import generate_personal_report
from ai_growth_mirror.application.summary_payload import build_personal_summary_payload
from ai_growth_mirror.application.report_view import build_personal_report_view, _build_level_evidence
from ai_growth_mirror.domain.snapshots.model import SnapshotCoverage, SnapshotMethodAssets, SnapshotPromptQuality, SnapshotSource
from ai_growth_mirror.domain.snapshots.trajectory import build_snapshot_trajectory_window
from tests.conftest import load_report_label_catalogs, run_workspace
from ai_growth_mirror.infra.snapshots import (
    SNAPSHOT_ARCHIVE_DIRNAME,
    build_snapshot_comparison,
    compare_snapshots,
    load_previous_snapshot_source,
)
from ai_growth_mirror.application.html_render import render_personal_report_html, render_share_card_html


def _make_session(
    session_id: str,
    project: str,
    *,
    with_subagent: bool = False,
    first_prompt: str | None = None,
) -> SessionRecord:
    prompt = first_prompt or "目标：修复接口错误。相关文件：handler.py, test_handler.py。约束：不要改 API 契约。验收：pytest 通过。"
    return SessionRecord(
        session_id=session_id,
        tool_name="codex",
        project_path=project,
        start_time="2026-05-20T09:00:00+00:00",
        end_time="2026-05-20T10:00:00+00:00",
        duration_minutes=60,
        first_prompt=prompt,
        user_message_count=6,
        assistant_message_count=8,
        tool_counts={"read": 8, "edit": 2, "bash": 3},
        files_modified=2,
        lines_added=20,
        lines_removed=3,
        languages={"Python": 2},
        user_message_timestamps=["2026-05-20T09:00:00+00:00"],
        message_hours=[9],
        uses_subagent=with_subagent,
        uses_mcp=False,
        uses_web_search=False,
        uses_web_fetch=False,
        autonomous_chain_lengths=[6, 4, 3],
        has_verification_behavior=True,
        has_test_commands=True,
        prompt_word_count=len(prompt.split()),
        prompt_has_constraint=("约束" in prompt or "constraints" in prompt.lower() or "验收" in prompt or "acceptance" in prompt.lower()),
        prompt_has_code_context=(".py" in prompt or ".ts" in prompt or "文件" in prompt or "file" in prompt.lower()),
    )


def _make_facets(session_id: str, *, score_bias: int = 0) -> SessionRead:
    from ai_growth_mirror.domain.signals.model import PromptLensScores

    return SessionRead(
        session_id=session_id,
        tool_name="codex",
        delivery_outcome="fully_achieved",
        support_value="very_helpful",
        confidence="high",
        session_takeaway="修复接口错误并完成验证。",
        work_intent_mix={"implement_feature": 1, "fix_bug": 1},
        key_gain="completed_implementation",
        prompt_lens=PromptLensScores(
            source="llm",
            coverage="full",
            evaluation_status="llm_evaluated",
            evaluated_user_messages=6,
            context_provision=55 + score_bias,
            request_specificity=52 + score_bias,
            scope_management=60 + score_bias,
            information_timing=48 + score_bias,
            correction_quality=63 + score_bias,
            efficiency_score=58 + score_bias,
        ),
        capability_focus="none",
        capability_depth="incidental",
        work_style="plan_driven",
    )


def _snapshot_index_entry(snapshot_id: str, created_at: str) -> dict[str, str]:
    prefix = f"snapshots/{snapshot_id}"
    return {
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "tool_display_name": "Codex CLI",
        "report_title": "test report",
        "date_range": "2026-05-01 – 2026-05-31",
        "report_path": f"{prefix}/report.html",
        "report_json_path": f"{prefix}/report.json",
        "profile_path": f"{prefix}/profile.json",
        "summary_path": f"{prefix}/summary.json",
        "normalized_summary_path": f"{prefix}/normalized-summary.json",
        "compare_hint": f"ai-growth-mirror compare {snapshot_id} <other_snapshot_id>",
    }


def test_build_growth_plan_returns_two_priorities():
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2", score_bias=-5)]
    stats = aggregate(sessions, facets, tool_name="codex")
    plan = build_growth_plan(
        stats=stats,
        capability_scores={
            "intent_clarity": 72,
            "execution_driving": 66,
            "implementation_depth": 43,
            "delivery_closure": 34,
            "adaptive_recovery": 40,
        },
        catalogs=load_report_label_catalogs("zh"),
    )
    assert len(plan.priorities) == 2
    assert plan.priorities[0].practice_prompt


def test_build_personal_report_view_contains_core_sections():
    sessions = [_make_session("s1", "\\\\?\\D:\\repo\\demo-platform", with_subagent=True), _make_session("s2", "D:/repo/demo-platform")]
    sessions[0].tool_counts = {"shell_command": 4, "apply_patch": 2, "update_plan": 1, "search": 1}
    sessions[1].tool_counts = {"bash": 3, "apply_patch": 1, "web_search_call": 1, "open_page": 1}
    facets = [_make_facets("s1"), _make_facets("s2", score_bias=-5)]
    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    assert view.summary.growth_level
    assert view.summary.subtitle == "Codex CLI"
    assert view.summary.share_title
    assert len(view.summary.share_lines) == 3
    assert view.sections
    assert any(item.id == "section-growth-plan" for item in view.sections)
    assert any(item.id == "section-summary" for item in view.sections)
    assert any(item.id == "section-level-evidence" for item in view.sections)
    assert all(item.id != "section-usage" for item in view.sections)
    assert all(item.id != "section-capability" for item in view.sections)
    assert len(view.capability.dimensions) == 5
    assert view.capability.dimensions[0].has_data is True
    assert view.radar_chart is not None
    assert view.radar_chart.polygon_points
    assert view.radar_axes
    assert view.gap_rankings
    assert view.level_guide.current_level
    assert len(view.level_guide.items) == 5
    assert view.level_evidence.metrics
    assert any(metric.target_value for metric in view.level_evidence.metrics)
    assert view.collaboration_rhythm.rhythm_label
    assert view.usage.stats
    assert "内存" in view.usage.memory_note
    assert view.work_focus.goal_mix
    assert view.work_focus.goal_mix[0].detail.endswith("%")
    assert view.work_focus.projects[0] == "demo-platform"
    assert view.work_focus.tools[0].label == "终端执行"
    assert all(item.label != "shell_command" for item in view.work_focus.tools)
    assert any(item.label == "页面查看" for item in view.work_focus.tools)
    assert all("\\" not in item for item in view.work_focus.projects)
    assert len(view.wins.wins) >= 2
    assert len(view.growth_plan.priorities) >= 1
    assert view.style_lens.archetype_name
    assert len(view.prompt_coach.takeaways) >= 2
    assert "LLM" in view.prompt_coach.source_note
    assert len({item.kind for item in view.prompt_coach.takeaways}) >= 2
    assert all(item.message != item.action for item in view.prompt_coach.takeaways if item.message and item.action)


def test_short_session_prompt_lens_gets_insufficient_input_status():
    from ai_growth_mirror.infra.extractors.heuristic import build_prompt_quality_proxy

    session = _make_session("s1", "D:/repo/a")
    session.user_message_count = 3

    proxy = build_prompt_quality_proxy(
        session,
        language="zh",
        evaluation_status="insufficient_input",
    )
    assert proxy.evaluation_status == "insufficient_input"
    assert proxy.coverage == "light"

    facet = SessionRead(
        session_id="s1",
        tool_name="codex",
        prompt_lens=proxy,
    )
    stats = aggregate([session], [facet], tool_name="codex")
    assert stats.pq_insufficient_count >= 1


def test_collaboration_rhythm_falls_back_to_session_start_when_message_timestamps_missing():
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    for index, session in enumerate(sessions):
        session.user_message_timestamps = []
        session.message_hours = []
        session.start_time = f"2026-05-2{index}T10:00:00+08:00"
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    rhythm_stats = {item.label: item.value for item in view.collaboration_rhythm.stats}
    assert rhythm_stats["高峰时段"] != "--"
    assert rhythm_stats["最常活跃日"] != "--"


def test_generate_personal_report_writes_html_and_sidecar(tmp_path: Path):
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    workspace_tmp = run_workspace(tmp_path, "personal_report")
    out = workspace_tmp / "personal.html"
    generate_personal_report(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        output_path=out,
        language="zh",
        redact=False,
        sources_summary={"local": {"codex": {"total": 2, "analyzed": 2}}},
        quality_eligible=2,
        extraction_failed=0,
        since_label="2026-05-01",
        until_label="2026-05-31",
    )
    html = out.read_text(encoding="utf-8")
    assert "section-growth-plan" in html
    assert "section-level-guide" in html
    assert "section-level-evidence" in html
    assert "section-rhythm" in html
    assert "section-focus" in html
    assert "section-wins" in html
    assert "section-style-lens" in html
    assert "AI 成长镜" in html
    assert "本期协作进化报告" in html
    assert 'href="#section-summary"' in html
    assert 'sidebar-brand-link' in html
    assert "github.com/yxkong/ai-growth-mirror" in html
    assert "5ycode@sina.com" in html
    assert html.count('href="#section-summary"') >= 1
    assert "7 天微训练" not in html
    assert out.with_suffix(".json").exists()
    assert out.with_name("personal.summary.json").exists()
    share_html = out.with_name("personal-share.html")
    assert share_html.exists()
    assert "这期协作结论" in share_html.read_text(encoding="utf-8")


def test_personal_summary_payload_contains_share_surface_fields():
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    payload = build_personal_summary_payload(view)

    assert payload["share_card"]["title"]
    assert payload["share_card"]["headline"]
    assert payload["share_card"]["stage"] == view.summary.growth_level
    assert payload["share_card"]["strongest_habit"] == view.summary.strongest_signal
    assert payload["share_card"]["current_breakthrough"] == view.summary.next_focus


def test_personal_summary_payload_exports_closed_loop_fields():
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    payload = build_personal_summary_payload(view)

    assert "growth_trajectory" in payload
    assert "prompt_coach" in payload
    assert "growth_plan" in payload
    assert payload["prompt_coach"]["source_summary"]["llm_session_count"] >= 0
    assert isinstance(payload["prompt_coach"]["rewrite_cards"], list)
    assert isinstance(payload["growth_plan"]["priorities"], list)
    assert "seven_day_training_plan" not in payload["prompt_coach"]
    assert "prompt_style" in payload["prompt_coach"]
    assert "closure_guidance" in payload["prompt_coach"]
    assert "recommended_training_inputs" in payload["prompt_coach"]
    assert "window_points" in payload["growth_trajectory"]
    assert "daily_points" in payload["growth_trajectory"]
    assert "linked_growth_trend_refs" in payload["growth_plan"]["priorities"][0]
    assert "linked_closure_guidance_ids" in payload["growth_plan"]["priorities"][0]


def test_prompt_coach_prefers_real_takeaway_examples():
    from ai_growth_mirror.domain.signals.model import PromptLensTakeaway

    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    stats.pq_top_takeaways = [
        PromptLensTakeaway(
            type="improve",
            category="context_provision",
            label="先把背景交代完整",
            original="帮我看看这个问题。",
            better_prompt="现象：接口 500\n相关文件：handler.py\n约束：不要改接口契约\n验收：pytest 通过",
            why="把现象、文件、约束和验收放在第一条消息里，AI 才能直接进入执行。",
        )
    ]

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.takeaways
    assert view.prompt_coach.takeaways[0].label == "先把背景交代完整"
    assert "帮我看看这个问题" in view.prompt_coach.takeaways[0].evidence
    assert "相关文件：handler.py" in view.prompt_coach.takeaways[0].better_prompt


def test_prompt_coach_mixed_prompt_message_aligns_with_acceptance_gap():
    session = _make_session(
        "s1",
        "D:/repo/a",
        first_prompt="按照 /delivery-workflow 执行。针对 ai_growth_mirror/application/prompt_coach.py，目标结果：修正当前判断卡文案，避免和首要短板打架。",
    )
    session.slash_commands = ["/delivery-workflow"]
    session.unique_skills_used = ["delivery-workflow"]
    facet = _make_facets("s1")
    stats = aggregate([session], [facet], tool_name="codex")
    stats.pq_deficit_counts = {
        "missing-acceptance-criteria": 4,
        "missing-context": 2,
    }

    coach = build_prompt_coach_view(
        stats=stats,
        sessions=[session],
        session_reads=[facet],
        session_read_mode="llm",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert coach.prompt_style is not None
    assert coach.prompt_style.type == "mixed_prompt"
    assert "完成定义和收口方式" in coach.prompt_style.coaching_message
    assert "上下文不足" not in coach.prompt_style.coaching_message
    assert coach.prompt_style.suggested_next_prompt == ""
    assert coach.rewrite_cards == []


def test_prompt_coach_prioritizes_task_variable_evidence_for_mixed_prompt():
    session = _make_session(
        "s1",
        "D:/repo/a",
        first_prompt="按照 /delivery-workflow 执行。针对 ai_growth_mirror/application/prompt_coach.py 和 tests/unit/test_personal_growth_report.py，目标结果：修正当前判断卡文案。",
    )
    session.slash_commands = ["/delivery-workflow"]
    session.unique_skills_used = ["delivery-workflow"]
    facet = _make_facets("s1")
    stats = aggregate([session], [facet], tool_name="codex")
    stats.pq_deficit_counts = {"missing-acceptance-criteria": 3}

    coach = build_prompt_coach_view(
        stats=stats,
        sessions=[session],
        session_reads=[facet],
        session_read_mode="llm",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert coach.prompt_style is not None
    visible_evidence = coach.prompt_style.evidence[:3]
    assert any("本次任务变量：已补" in item for item in visible_evidence)


def test_prompt_coach_does_not_fallback_to_template_without_grounded_rewrite():
    session = _make_session(
        "s1",
        "D:/repo/a",
        first_prompt="按照 /delivery-workflow 执行。针对 ai_growth_mirror/application/prompt_coach.py，目标结果：修正当前判断卡文案。",
    )
    session.slash_commands = ["/delivery-workflow"]
    session.unique_skills_used = ["delivery-workflow"]
    facet = _make_facets("s1")
    stats = aggregate([session], [facet], tool_name="codex")
    stats.pq_deficit_counts = {"missing-context": 3}

    view = build_personal_report_view(
        sessions=[session],
        session_reads=[facet],
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.prompt_style is not None
    assert view.prompt_coach.prompt_style.suggested_next_prompt == ""
    assert view.prompt_coach.rewrite_cards == []
    assert view.prompt_coach.universal_template is None
    assert view.prompt_coach.scenario_templates == []


def test_snapshot_trajectory_window_collapses_same_day_points():
    def _source(snapshot_id: str, created_at: str, score: int) -> SnapshotSource:
        return SnapshotSource(
            snapshot_id=snapshot_id,
            created_at=created_at,
            date_range="2026-05",
            tool_display_name="Codex CLI",
            growth_level="L3",
            mirror_score=score,
            headline="headline",
            next_focus="focus",
            strongest_axis_key="intent_clarity",
            weakest_axis_key="delivery_closure",
            axis_scores={
                "intent_clarity": float(score),
                "execution_driving": float(score - 2),
                "implementation_depth": float(score - 4),
                "delivery_closure": float(score - 6),
                "adaptive_recovery": float(score - 3),
            },
            prompt_quality_dimensions={"context_provision": float(score - 10)},
            actionable_friction_counts={
                "vague_request": 3,
                "missing_context": 2,
                "scope_drift": 1,
                "missing_acceptance_criteria": 1,
                "unclear_correction": 0,
            },
            prompt_quality=SnapshotPromptQuality(),
            friction_type_counts={},
            friction_by_attribution={},
            method_assets=SnapshotMethodAssets(),
            coverage=SnapshotCoverage(session_count=4, session_read_count=4, has_usage_data=True),
            evidence_by_topic={},
            sample_count=4,
            point_confidence="medium",
        )

    window = build_snapshot_trajectory_window(
        [
            _source("a", "2026-05-29 10:00:00", 50),
            _source("b", "2026-05-30 10:00:00", 58),
            _source("c1", "2026-05-31 09:00:00", 60),
            _source("c2", "2026-05-31 18:00:00", 68),
        ]
    )

    assert len(window.window_points) == 4
    assert len(window.daily_points) == 3
    assert window.daily_points[-1].snapshot_id == "c2"
    assert window.trend_summary.label in {"sustained_up", "volatile_up"}


def test_prompt_coach_classifies_indexed_prompt_without_treating_it_as_missing_context():
    sessions = [
        _make_session(
            "s1",
            "D:/repo/a",
            first_prompt="requirements_design / AGENTS.md / delivery workflow",
        ),
        _make_session(
            "s2",
            "D:/repo/a",
            first_prompt="code_review / rules / skill",
        ),
    ]
    sessions[0].unique_skills_used = ["delivery-workflow", "ai-growth-mirror-dev"]
    sessions[0].slash_commands = ["/requirements_design"]
    sessions[1].unique_skills_used = ["code-review-skill"]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.prompt_style is not None
    assert view.prompt_coach.prompt_style.type == "indexed_prompt"
    assert "索引式 Prompt" in view.prompt_coach.prompt_style.label
    assert any("技能路由" in item or "命令入口" in item for item in view.prompt_coach.prompt_style.evidence)
    payload = build_personal_summary_payload(view)
    assert "seven_day_training_plan" not in payload["prompt_coach"]


def test_prompt_coach_classifies_mixed_prompt():
    sessions = [
        _make_session(
            "s1",
            "D:/repo/a",
            first_prompt="按照 requirements_design，基于成长轨迹模块做需求设计，重点考虑 Prompt 教练和训练冲刺联动。",
        ),
        _make_session("s2", "D:/repo/a"),
    ]
    sessions[0].unique_skills_used = ["delivery-workflow"]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.prompt_style is not None
    assert view.prompt_coach.prompt_style.type == "mixed_prompt"


def test_prompt_coach_reframes_indexed_rule_blob_rewrite_card():
    session = _make_session(
        "s1",
        "D:/repo/a",
        first_prompt="requirements_design",
    )
    session.unique_skills_used = ["delivery-workflow", "ai-growth-mirror-dev"]
    session.slash_commands = ["/requirements_design"]
    facet = _make_facets("s1")
    facet.prompt_lens = PromptLensScores(
        source="llm",
        coverage="full",
        evaluated_user_messages=2,
        context_provision=58,
        request_specificity=54,
        scope_management=60,
        information_timing=56,
        correction_quality=62,
        efficiency_score=58,
        takeaways=[
            PromptLensTakeaway(
                type="improve",
                category="context_provision",
                label="indexed-entry",
                original="# AGENTS.md instructions\nfor D:/repo/a\n<INSTRUCTIONS>\n# Common Agent Rules",
                better_prompt="背景：...\n目标结果：...",
                why="补变量后更稳。",
            )
        ],
    )
    stats = aggregate([session], [facet], tool_name="codex")

    view = build_personal_report_view(
        sessions=[session],
        session_reads=[facet],
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.prompt_style is not None
    assert view.prompt_coach.prompt_style.type == "indexed_prompt"
    assert view.prompt_coach.rewrite_cards
    card = view.prompt_coach.rewrite_cards[0]
    assert card.original == ""
    assert "索引" in card.problem
    assert "索引入口摘要" in card.source_note


def test_prompt_coach_classifies_under_specified_prompt():
    sessions = [
        _make_session("s1", "D:/repo/a", first_prompt="帮我看下这个"),
        _make_session("s2", "D:/repo/b", first_prompt="帮我处理一下"),
    ]
    for session in sessions:
        session.prompt_has_constraint = False
        session.prompt_has_code_context = False
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.prompt_style is not None
    assert view.prompt_coach.prompt_style.type == "under_specified_prompt"


def test_prompt_coach_friction_synthesis_rule_path_without_llm():
    sessions = [
        _make_session("s1", "D:/repo/a", first_prompt="帮我看下这个"),
        _make_session("s2", "D:/repo/b", first_prompt="帮我处理一下"),
    ]
    for session in sessions:
        session.prompt_has_constraint = False
        session.prompt_has_code_context = False

    facets = []
    for session_id in ("s1", "s2"):
        facet = _make_facets(session_id)
        facet.prompt_lens.findings = [
            PromptLensFinding(
                type="deficit",
                category="vague-request",
                description="request too vague",
                impact="high",
            ),
            PromptLensFinding(
                type="deficit",
                category="missing-context",
                description="missing context",
                impact="medium",
            ),
        ]
        facets.append(facet)

    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_prompt_coach_view(
        stats=stats,
        sessions=sessions,
        session_reads=facets,
        session_read_mode="heuristic_only",
        catalogs=load_report_label_catalogs("zh"),
        coaching=None,
    )

    assert view.friction_synthesis
    assert view.friction_synthesis[0].generated_by == "rule"
    assert view.friction_synthesis[0].evidence_refs
    assert view.friction_synthesis[0].label


def test_closure_guidance_uses_task_type_instead_of_forcing_tests_on_design():
    sessions = [
        _make_session("s1", "D:/repo/a", first_prompt="请基于成长轨迹模块做需求设计，并给出验收清单和边界场景。"),
        _make_session("s2", "D:/repo/a", first_prompt="请继续完善架构方案和交互说明。"),
    ]
    for session in sessions:
        session.prompt_has_code_context = False
        session.has_test_commands = False
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.closure_guidance is not None
    assert view.prompt_coach.closure_guidance.task_type == "design_or_requirements"
    assert all("测试" not in item for item in view.prompt_coach.closure_guidance.expected_closure_methods)


def test_closure_guidance_keeps_test_for_code_change():
    sessions = [
        _make_session("s1", "D:/repo/a", first_prompt="修复 handler.py 的 500 问题，并补最小验证。"),
        _make_session("s2", "D:/repo/a"),
    ]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert view.prompt_coach.closure_guidance is not None
    assert view.prompt_coach.closure_guidance.task_type == "code_change"
    assert any("测试" in item or "冒烟" in item for item in view.prompt_coach.closure_guidance.expected_closure_methods)

def test_exemplars_do_not_repeat_same_category():
    sessions = [
        _make_session("s1", "D:/repo/a", with_subagent=True),
        _make_session("s2", "D:/repo/b", with_subagent=True),
        _make_session("s3", "D:/repo/c"),
    ]
    sessions[2].git_commits = 1
    sessions[2].uses_subagent = False
    sessions[2].prompt_word_count = 120
    facets = [_make_facets("s1"), _make_facets("s2"), _make_facets("s3")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )

    assert len({item.category_label for item in view.exemplars}) == len(view.exemplars)
    assert all(item.why_keep for item in view.exemplars)
    assert all(item.technique for item in view.exemplars)


def test_snapshot_comparison_data_structure():
    left_profile = {
        "capability": {
            "dimensions": [
                {"key": "intent_clarity", "label": "任务表达", "score": 40},
                {"key": "execution_driving", "label": "协作驱动", "score": 30},
                {"key": "implementation_depth", "label": "实现下潜", "score": 20},
                {"key": "delivery_closure", "label": "交付收口", "score": 50},
                {"key": "adaptive_recovery", "label": "恢复推进", "score": 35},
            ]
        }
    }
    right_profile = {
        "capability": {
            "dimensions": [
                {"key": "intent_clarity", "label": "任务表达", "score": 55},
                {"key": "execution_driving", "label": "协作驱动", "score": 48},
                {"key": "implementation_depth", "label": "实现下潜", "score": 25},
                {"key": "delivery_closure", "label": "交付收口", "score": 62},
                {"key": "adaptive_recovery", "label": "恢复推进", "score": 46},
            ]
        }
    }
    left_summary = {
        "snapshot_id": "20260525-100000",
        "next_focus": "交付收口",
        "weakest_label": "实现下潜",
    }
    right_summary = {
        "snapshot_id": "20260526-100000",
        "next_focus": "恢复推进",
        "weakest_label": "协作驱动",
    }
    comparison = build_snapshot_comparison(
        left_profile=left_profile,
        right_profile=right_profile,
        left_summary=left_summary,
        right_summary=right_summary,
        language="zh",
    )
    assert comparison["current"]["mirror_score"] >= 0
    assert comparison["previous"]["next_focus"] == "交付收口"
    assert len(comparison["axis_deltas"]) == 5


def test_generate_personal_report_creates_snapshot_archive(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "snapshot")
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/b")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")
    out = workspace_tmp / "ai-growth-mirror.html"
    generate_personal_report(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        output_path=out,
        language="zh",
        redact=False,
        sources_summary={"local": {"codex": {"total": 2, "analyzed": 2}}},
        quality_eligible=2,
        extraction_failed=0,
        since_label="2026-05-01",
        until_label="2026-05-31",
    )
    archive_root = workspace_tmp / SNAPSHOT_ARCHIVE_DIRNAME
    assert (archive_root / "index.json").exists()
    snapshots_dir = archive_root / "snapshots"
    snapshot_dirs = [item for item in snapshots_dir.iterdir() if item.is_dir()]
    assert len(snapshot_dirs) == 1
    snapshot_dir = snapshot_dirs[0]
    assert (snapshot_dir / "report.html").exists()
    assert (snapshot_dir / "profile.json").exists()
    assert (snapshot_dir / "summary.json").exists()
    assert (snapshot_dir / "normalized-summary.json").exists()


def test_load_previous_snapshot_source_prefers_most_recent_snapshot(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "snapshot_prev_latest")
    archive_root = workspace_tmp / SNAPSHOT_ARCHIVE_DIRNAME
    snapshots_root = archive_root / "snapshots"
    snapshots_root.mkdir(parents=True)

    old_id = "20260528-230000"
    new_id = "20260529-120000"
    for snapshot_id, score in ((old_id, 12), (new_id, 66)):
        snapshot_dir = snapshots_root / snapshot_id
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "profile.json").write_text(json.dumps({}), encoding="utf-8")
        (snapshot_dir / "summary.json").write_text(
            json.dumps({"snapshot_id": snapshot_id, "created_at": "2026-05-29 12:00:00", "score": score}),
            encoding="utf-8",
        )

    index = {
        "schema_version": "1.0",
        "latest_snapshot_id": new_id,
        "snapshots": [
            _snapshot_index_entry(new_id, "2026-05-29 12:00:00"),
            _snapshot_index_entry(old_id, "2026-05-28 23:00:00"),
        ],
    }
    (archive_root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    source = load_previous_snapshot_source(archive_root)
    assert source is not None
    assert source.created_at == "2026-05-29 12:00:00"
    assert source.mirror_score == 66


def test_load_previous_snapshot_source_falls_back_to_legacy_snapshot_archive(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "snapshot_prev_legacy")
    legacy_root = workspace_tmp / "snapshot-archive"
    snapshot_id = "20260526-075444"
    snapshot_dir = legacy_root / "snapshots" / snapshot_id
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "profile.json").write_text(json.dumps({}), encoding="utf-8")
    (snapshot_dir / "summary.json").write_text(
        json.dumps({"snapshot_id": snapshot_id, "created_at": "2026-05-26 07:54:44", "score": 48}),
        encoding="utf-8",
    )
    (legacy_root / "index.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "latest_snapshot_id": snapshot_id,
                "snapshots": [
                    _snapshot_index_entry(snapshot_id, "2026-05-26 07:54:44"),
                ],
            }
        ),
        encoding="utf-8",
    )

    source = load_previous_snapshot_source(workspace_tmp / SNAPSHOT_ARCHIVE_DIRNAME)
    assert source is not None
    assert source.created_at == "2026-05-26 07:54:44"
    assert source.mirror_score == 48


def test_level_evidence_uses_level_specific_target_for_l5():
    stats = GrowthProfile(
        tool_name="codex",
        growth_level="L5",
        mirror_score=94,
        session_count=30,
        avg_autonomous_chain_length=6.4,
        heavy_session_count=9,
        subagent_session_count=2,
        total_subagent_invocations=3,
        verification_behavior_rate=0.52,
        test_run_rate=0.36,
        code_verification_rate=0.40,
        tier_diversity_count=5,
        advanced_feature_ratio=0.34,
        distinct_tool_count=2,
        distinct_model_count=2,
        fully_achieved_rate=0.64,
        workflow_structured_session_count=14,
        workflow_build_substantial_count=2,
        workflow_build_moderate_count=4,
        unique_skill_count=3,
        ai_authoring_distinct_categories=2,
    )
    section = _build_level_evidence(stats, {}, "heuristic", load_report_label_catalogs("zh"))
    assert section.current_level == "L5"
    assert section.target_level == "L5"
    assert section.target_caption == "L5 保持线"
    assert "L5" in section.progress_summary
    assert any("多工具、多模型、多路径协作" in metric.target_value for metric in section.metrics)


def test_level_evidence_moves_l3_to_l4_instead_of_showing_l3_floor():
    stats = GrowthProfile(
        tool_name="codex",
        growth_level="L3",
        mirror_score=74,
        session_count=18,
        avg_autonomous_chain_length=3.2,
        heavy_session_count=3,
        verification_behavior_rate=0.14,
        test_run_rate=0.10,
        tier_diversity_count=3,
        advanced_feature_ratio=0.08,
        distinct_tool_count=1,
        fully_achieved_rate=0.33,
        workflow_structured_session_count=3,
        workflow_build_substantial_count=0,
        workflow_build_moderate_count=1,
        unique_skill_count=1,
    )
    section = _build_level_evidence(stats, {}, "heuristic", load_report_label_catalogs("zh"))
    assert section.current_level == "L3"
    assert section.target_level == "L4"
    assert section.target_caption == "L4 进阶线"
    assert any("subagent、MCP、计划等高杠杆能力" in metric.target_value for metric in section.metrics)


def test_cursor_adapter_reads_beta_db(monkeypatch, tmp_path: Path):
    import sqlite3
    from ai_growth_mirror.infra.readers import cursor as cursor_reader

    workspace_tmp = run_workspace(tmp_path, "cursor_beta")
    root = workspace_tmp / ".cursor"
    db_dir = root / "ai-tracking"
    db_dir.mkdir(parents=True)
    db = db_dir / "ai-code-tracking.db"
    db.write_text("", encoding="utf-8")
    shared_uri = "file:cursor-beta-db?mode=memory&cache=shared"
    real_connect = sqlite3.connect
    shared_conn = real_connect(shared_uri, uri=True)
    monkeypatch.setattr(
        cursor_reader.sqlite3,
        "connect",
        lambda *args, **kwargs: real_connect(shared_uri, uri=True),
    )
    with shared_conn as conn:
        conn.executescript(
            """
            CREATE TABLE conversation_summaries (
              conversationId TEXT PRIMARY KEY,
              title TEXT,
              tldr TEXT,
              overview TEXT,
              summaryBullets TEXT,
              model TEXT,
              mode TEXT,
              updatedAt INTEGER NOT NULL
            );
            CREATE TABLE tracked_file_content (
              gitPath TEXT PRIMARY KEY,
              content TEXT NOT NULL,
              conversationId TEXT,
              model TEXT,
              fileExtension TEXT,
              createdAt INTEGER NOT NULL
            );
            CREATE TABLE ai_deleted_files (
              gitPath TEXT NOT NULL,
              composerId TEXT,
              conversationId TEXT,
              model TEXT,
              deletedAt INTEGER NOT NULL,
              PRIMARY KEY (gitPath, deletedAt)
            );
            """
        )
        conn.execute(
            "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Fix auth bug", "done", "overview", "[]", "gpt-4.1", "agent", 1760000000000),
        )
        conn.execute(
            "INSERT INTO tracked_file_content VALUES (?, ?, ?, ?, ?, ?)",
            ("D:/repo/handler.py", "print(1)", "c1", "gpt-4.1", ".py", 1759990000000),
        )
        conn.execute(
            "INSERT INTO tracked_file_content VALUES (?, ?, ?, ?, ?, ?)",
            ("D:/repo/test_handler.py", "print(2)", "c1", "gpt-4.1", ".py", 1759991000000),        )
        conn.commit()

    adapter = CursorAdapter(data_root=root)
    assert adapter.is_available() is True
    raw = next(adapter.iter_raw_sessions())
    parsed = adapter.parse_session(raw)
    assert parsed.session_id == "c1"
    assert parsed.files_modified == 2
    assert parsed.models_used == ["gpt-4.1"]
    assert parsed.project_path == "D:\\repo"


def test_cursor_adapter_reads_agent_transcripts(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "cursor_transcript")
    root = workspace_tmp / ".cursor"
    transcript_dir = (
        root / "projects" / "d-demo-repo" / "agent-transcripts" / "abc-123"
    )
    transcript_dir.mkdir(parents=True)
    jsonl = transcript_dir / "abc-123.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "<user_query>Fix auth bug in handler.py</user_query>",                                }
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "StrReplace",
                                    "input": {"path": "D:/repo/handler.py"},
                                },
                                {
                                    "type": "tool_use",
                                    "name": "Shell",
                                    "input": {"command": "pytest tests/test_handler.py"},
                                },
                            ]
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    adapter = CursorAdapter(data_root=root)
    assert adapter.is_available() is True
    sessions = list(adapter.iter_sessions())
    assert len(sessions) == 1
    parsed = sessions[0]
    assert parsed.session_id == "abc-123"
    assert parsed.first_prompt == "Fix auth bug in handler.py"
    assert parsed.user_message_count == 1
    assert parsed.has_verification_behavior is True
    assert parsed.has_test_commands is True
    assert parsed.tool_counts.get("strreplace") == 1
    assert parsed.tool_counts.get("shell") == 1


def test_render_personal_report_html_escapes_untrusted_content():
    xss_payload = '<script>alert("xss")</script>'
    sessions = [_make_session("s1", "D:/repo/a")]
    facets = [_make_facets("s1")]
    facets[0].session_takeaway = xss_payload
    stats = aggregate(sessions, facets, tool_name="codex")
    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    html = render_personal_report_html(view=view, language="zh", redact=False)
    assert xss_payload not in html
    assert "&lt;script&gt;" in html


def test_render_personal_report_html_compacts_prompt_coach_surface():
    sessions = [
        _make_session("s1", "D:/repo/a", first_prompt="requirements_design / AGENTS.md / delivery workflow"),
        _make_session("s2", "D:/repo/a", first_prompt="按照 requirements_design，基于成长轨迹模块做需求设计，重点考虑 Prompt 教练和训练冲刺联动。"),
    ]
    sessions[0].unique_skills_used = ["delivery-workflow", "ai-growth-mirror-dev"]
    sessions[0].slash_commands = ["/requirements_design"]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    html = render_personal_report_html(view=view, language="zh", redact=False)
    assert "场景化模板" not in html
    assert "section_score_waterfall" not in html
    assert "LLM" in html or "heuristic" in html
    assert "下次可以这样问" not in html
    assert "AI Growth Mirror logo" in html


def test_report_sections_keep_five_primary_chain():
    sessions = [_make_session("s1", "D:/repo/a"), _make_session("s2", "D:/repo/a")]
    facets = [_make_facets("s1"), _make_facets("s2")]
    stats = aggregate(sessions, facets, tool_name="codex")

    view = build_personal_report_view(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        catalogs=load_report_label_catalogs("zh"),
    )
    visible_ids = [item.id for item in view.sections if item.nav_visible]
    assert visible_ids == [
        "section-growth-signals",
        "section-level-evidence",
        "section-prompt-coach",
        "section-growth-plan",
    ]
    assert any(item.id == "section-summary" and not item.nav_visible for item in view.sections)
    assert "section-level-guide" not in visible_ids


def test_generate_personal_report_redact_hides_project_names(tmp_path: Path):
    secret_project = "redacted-demo-repo"
    secret_prompt = "Fix auth in secret-module.py with token sk-demo-not-real"
    secret_synopsis = "Deployed hotfix to staging cluster demo-east-01"
    workspace_tmp = run_workspace(tmp_path, "redact")
    sessions = [_make_session("s1", f"D:/work/{secret_project}")]
    sessions[0].first_prompt = secret_prompt
    facets = [_make_facets("s1")]
    facets[0].session_takeaway = secret_synopsis
    stats = aggregate(sessions, facets, tool_name="codex")
    out = workspace_tmp / "personal-redact.html"
    generate_personal_report(
        sessions=sessions,
        session_reads=facets,
        stats=stats,
        tool_display_name="Codex CLI",
        output_path=out,
        language="zh",
        redact=True,
        sources_summary={"local": {"codex": {"total": 1, "analyzed": 1}}},
        quality_eligible=1,
        extraction_failed=0,
        since_label="2026-05-01",
        until_label="2026-05-31",
    )
    html = out.read_text(encoding="utf-8")
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    summary = json.loads(out.with_name(f"{out.stem}.summary.json").read_text(encoding="utf-8"))
    share_html = out.with_name(f"{out.stem}-share.html").read_text(encoding="utf-8")
    leaked = (secret_project, secret_prompt, secret_synopsis)
    for blob in (html, json.dumps(sidecar, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), share_html):
        for secret in leaked:
            assert secret not in blob
    assert sidecar["stats"]["top_projects"] == []
    assert sidecar["session_examples"][0]["project"] == ""
    assert sidecar["session_examples"][0]["first_prompt"] == ""
    assert sidecar["session_read_summaries"][0]["session_takeaway"] == ""
    assert summary["work_focus"]["projects"] == []
    assert "脱敏" in html or "label_redact_note" in html


def test_report_assembly_imports_from_application_layer():
    from ai_growth_mirror.application.growth_plan import build_growth_plan
    from ai_growth_mirror.application.label_catalogs import load_report_label_catalogs
    from ai_growth_mirror.application.report_view import build_personal_report_view
    from ai_growth_mirror.application.summary_payload import build_personal_summary_payload

    assert callable(build_personal_report_view)
    assert callable(build_growth_plan)
    assert callable(load_report_label_catalogs)
    assert callable(build_personal_summary_payload)


def test_render_share_card_html_escapes_untrusted_content():
    xss_payload = '<script>alert("xss")</script>'
    payload = {
        "share_card": {
            "headline": xss_payload,
            "lines": [xss_payload],
            "stage": "L3",
            "score_display": "70",
            "strongest_habit": xss_payload,
            "current_breakthrough": xss_payload,
        }
    }
    html = render_share_card_html(
        summary_payload=payload,
        template_labels=load_report_label_catalogs("zh").template_labels,
        language="zh",
    )
    assert xss_payload not in html
    assert "&lt;script&gt;" in html


def test_snapshot_compare_html_escapes_untrusted_summary_fields(tmp_path: Path):
    workspace_tmp = run_workspace(tmp_path, "snapshot_escape")
    archive_root = workspace_tmp / SNAPSHOT_ARCHIVE_DIRNAME
    left_id = "20260527-120000"
    right_id = "20260527-130000"
    xss_focus = '<img src=x onerror="alert(1)">'
    for snapshot_id, focus in ((left_id, "交付收口"), (right_id, xss_focus)):
        snapshot_dir = archive_root / "snapshots" / snapshot_id
        snapshot_dir.mkdir(parents=True)
        profile = {
            "capability": {
                "dimensions": [
                    {"key": "intent_clarity", "label": "任务表达", "score": 40},
                ]
            }
        }
        summary = {
            "snapshot_id": snapshot_id,
            "next_focus": focus,
            "weakest_label": "实现下潜",
        }
        (snapshot_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
        (snapshot_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    out = compare_snapshots(
        archive_root=archive_root,
        left_snapshot_id=left_id,
        right_snapshot_id=right_id,
        language="zh",
    )
    html = out.read_text(encoding="utf-8")
    assert xss_focus not in html
    assert "&lt;img" in html
    payload = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["current"]["next_focus"] == xss_focus
