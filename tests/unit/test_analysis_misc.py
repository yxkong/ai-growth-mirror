from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.domain.signals.model import SessionRead
from ai_growth_mirror.domain.growth.highlights import surface_highlights
from ai_growth_mirror.domain.signals.taxonomy import ModelCapabilityTier
from ai_growth_mirror.domain.signals.tooling import infer_tool_tier
from tests.conftest import make_session


def test_surface_highlights_limit():
    sessions: list[SessionRecord] = []
    session_reads: list[SessionRead] = []
    for i in range(10):
        sid = str(i)
        sessions.append(
            SessionRecord(
                session_id=sid,
                tool_name="demo",
                user_message_count=2,
                files_modified=1,
                autonomous_chain_lengths=[5],
                uses_subagent=False,
                unique_skills_used=[],
                has_verification_behavior=True,
                has_test_commands=True,
                prompt_has_code_context=True,
                prompt_word_count=100,
                prompt_has_constraint=False,
                first_prompt="hello world " * 5,
                entrypoint="cli",
                tool_counts={"read": 12},
            )
        )
        session_reads.append(
            SessionRead(
                session_id=sid,
                tool_name="demo",
                delivery_outcome="fully_achieved",
                support_value="very_helpful",
                confidence="high",
            )
        )
    ex = surface_highlights(sessions, session_reads, limit=3, include_ungrouped=True)
    assert len(ex) == 3


def test_load_native_claude_session_read_prefers_canonical_keys(tmp_path, monkeypatch):
    import json

    from ai_growth_mirror.infra.extractors import llm as llm_mod

    reads_dir = tmp_path / "usage-data" / "facets"
    reads_dir.mkdir(parents=True)
    session_id = "native-read-1"
    (reads_dir / f"{session_id}.json").write_text(
        json.dumps(
            {
                "work_summary": "Fix auth bug",
                "work_intent_mix": {"debugging": 1},
                "outcome": "fully_achieved",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(llm_mod, "_CLAUDE_NATIVE_READS_DIR", reads_dir)
    meta = SessionRecord(session_id=session_id, tool_name="claude_code")
    read = llm_mod._load_native_claude_session_read(meta)
    assert read is not None
    assert read.work_summary == "Fix auth bug"
    assert read.work_intent_mix == {"debugging": 1}
    assert read.delivery_outcome == "fully_achieved"


def test_load_native_claude_session_read_accepts_session_focus_alias(tmp_path, monkeypatch):
    import json

    from ai_growth_mirror.infra.extractors import llm as llm_mod

    reads_dir = tmp_path / "usage-data" / "facets"
    reads_dir.mkdir(parents=True)
    session_id = "native-read-2"
    (reads_dir / f"{session_id}.json").write_text(
        json.dumps({"session_focus": "Refactor cache layer", "outcome": "mostly_achieved"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(llm_mod, "_CLAUDE_NATIVE_READS_DIR", reads_dir)
    meta = SessionRecord(session_id=session_id, tool_name="claude_code")
    read = llm_mod._load_native_claude_session_read(meta)
    assert read is not None
    assert read.work_summary == "Refactor cache layer"
    assert read.delivery_outcome == "mostly_achieved"

def test_infer_model_tier_alias():
    assert infer_tool_tier("opus-4") == ModelCapabilityTier.TIER_3_PRO
    assert infer_tool_tier("claude-3-5-sonnet") == ModelCapabilityTier.TIER_2_STANDARD
    assert infer_tool_tier("gpt-4o-mini") == ModelCapabilityTier.TIER_1_QUICK
