import json
from pathlib import Path

from ai_growth_mirror.infra.readers.json_reader import JsonSessionAdapter
from ai_growth_mirror.application.personal_report_service import generate_personal_report


def test_json_adapter_roundtrip(tmp_path: Path):
    payload = {"meta": {"session_id": "x", "tool": "json_dump"}, "turns": [{"role": "user", "content": "hi"}]}
    workspace_tmp = tmp_path / "json_adapter"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    p = workspace_tmp / "s.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    s = JsonSessionAdapter().load(p)
    assert s.session_id == "x"
    assert s.tool_name == "json_dump"


def test_generate_personal_report_is_callable():
    assert callable(generate_personal_report)
