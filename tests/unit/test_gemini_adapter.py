import json
from datetime import datetime, timezone
from pathlib import Path
from ai_growth_mirror.domain.session.model import SessionRef
from ai_growth_mirror.infra.readers.gemini import GeminiAdapter


def test_gemini_adapter_no_token_data(tmp_path):
    """Gemini transcript.jsonl does not embed real API usage.
    Token/cost fields must be None and tokens_estimated must be True
    so the report layer excludes them from aggregation and display.
    """
    # 1. Mock the brain directory structure for Antigravity
    brain_dir = tmp_path / "brain"
    conv_dir = brain_dir / "test-conversation-123"
    logs_dir = conv_dir / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 2. Write transcript.jsonl containing both user input and planner response
    transcript_path = logs_dir / "transcript.jsonl"

    steps = [
        # USER_INPUT
        {
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "created_at": "2026-06-06T10:00:00Z",
            "content": "<USER_REQUEST>帮我写一个快速排序算法，并且加上边界条件</USER_REQUEST>"
        },
        # PLANNER_RESPONSE with tool calls
        {
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "created_at": "2026-06-06T10:01:00Z",
            "tool_calls": [
                {
                    "name": "write_to_file",
                    "args": {
                        "TargetFile": "/Users/yxk/workspace/projects/github/ai-growth-mirror/qsort.py",
                        "CodeContent": "def qsort(arr): return arr"
                    }
                }
            ]
        },
        # USER_INPUT 2
        {
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "created_at": "2026-06-06T10:02:00Z",
            "content": "<USER_REQUEST>太简单了，写得更详细一些</USER_REQUEST>"
        },
        # PLANNER_RESPONSE with plain content (no tool calls)
        {
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "created_at": "2026-06-06T10:03:00Z",
            "content": "好的，这是更加详细的版本。这里是一个带有双指针的快速排序实现。"
        }
    ]

    with open(transcript_path, "w", encoding="utf-8") as f:
        for step in steps:
            f.write(json.dumps(step) + "\n")

    # 3. Instantiate the adapter and parse the session
    adapter = GeminiAdapter(data_root=tmp_path)

    # Verify availability detection
    assert adapter.is_available() is True

    # Verify session iteration
    sessions = list(adapter.iter_raw_sessions())
    assert len(sessions) == 1
    session_ref = sessions[0]
    assert session_ref.session_id == "test-conversation-123"

    # Parse the session into a SessionRecord
    record = adapter.parse_session(session_ref)

    # 4. Assert basic parsing correctness
    assert record.session_id == "test-conversation-123"
    assert record.user_message_count == 2
    assert record.assistant_message_count == 2  # One tool call + one plain text
    assert record.models_used == ["gemini"]

    # 5. Token/cost fields must be None — Gemini logs have no real usage data.
    #    The report layer uses tokens_estimated=True to exclude these sessions
    #    from token/cost aggregation and display.
    assert record.tokens_estimated is True
    assert record.input_tokens is None
    assert record.output_tokens is None
    assert record.cache_read_tokens is None
    assert record.cache_write_tokens is None
    assert record.total_cost_usd is None
