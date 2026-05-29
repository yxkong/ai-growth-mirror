from pathlib import Path

from ai_growth_mirror.config import GrowthMirrorConfig, ToolConfig
from ai_growth_mirror.application.orchestrator import collect_sessions, resolve_requested_tools


def test_resolve_requested_tools_maps_aliases():
    resolved = resolve_requested_tools(["claude", "codex", "cursor"])
    assert "claude_code" in resolved
    assert "codex" in resolved
    assert "cursor" in resolved


def test_collect_sessions_returns_empty_when_tool_disabled(tmp_path: Path):
    cfg = GrowthMirrorConfig()
    cfg.tools["codex"] = ToolConfig(enabled=False, data_root=tmp_path / ".missing-codex")
    result = collect_sessions(
        cfg=cfg,
        tool_names=["codex"],
        cache=None,
        since=None,
        until=None,
        force_refresh=False,
    )
    assert result.adapters == []
    assert result.sessions == []
