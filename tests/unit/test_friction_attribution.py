"""Tests for environmental-recovery misclassification fixes."""
from __future__ import annotations

import pytest
from ai_growth_mirror.domain.session.model import SessionRecord
from ai_growth_mirror.infra.extractors.heuristic import build_heuristic_session_read_for_session
from ai_growth_mirror.domain.session.heuristics import is_recovery_continuation


def test_is_recovery_continuation_patterns():
    assert is_recovery_continuation("继续") is True
    assert is_recovery_continuation("go on") is True
    assert is_recovery_continuation("retry") is True
    assert is_recovery_continuation("重试一下") is True
    assert is_recovery_continuation("做个好玩的东西") is False


def test_recovery_continuation_blocks_off_track():
    # If user_interruptions is high, but they are all recovery continuations
    session = SessionRecord(
        session_id="test-session-1",
        tool_name="claude_code",
        user_message_count=3,
        assistant_message_count=3,
        user_interruptions=2,
        first_prompt="开发一个新功能",
        top_user_messages=["继续", "go on", "测试一下"]
    )
    
    # We build the heuristic session read
    session_read = build_heuristic_session_read_for_session(session, language="zh")
    
    # Verify off-track blocker is NOT present, but environmental-recovery IS present
    categories = [sig.category for sig in session_read.resistance_signals]
    assert "off-track" not in categories
    assert "environmental-recovery" in categories
    
    # Verify attribution of environmental-recovery is environmental
    env_sig = next(sig for sig in session_read.resistance_signals if sig.category == "environmental-recovery")
    assert env_sig.attribution == "environmental"
    assert env_sig.severity == "low"
